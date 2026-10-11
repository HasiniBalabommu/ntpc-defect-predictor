"""
01_clean_and_split.py

Fixes vs. the original STEP2_CLEANING.ipynb:
  1. Uses a REAL chronological (temporal) split instead of a random 80/20
     split, and reports ONE consistent split (train/test) instead of the
     conflicting 80/20-vs-three-period description in the paper.
  2. Fits LabelEncoders on the TRAINING portion only (previously they were
     fit on the full dataset before any split -> leakage).
  3. Explicitly handles categories in the test set that were never seen in
     training (previously this would silently crash or was never tested).
  4. Keeps ALL 9 engineered features (the paper's Table 6a was missing
     'hour').
  5. Prints every count needed for the paper's Table 4/5 and Section 3.5,
     computed once, in one place, so they can't drift apart again.

Run:
    python 01_clean_and_split.py --input korba_defects.csv --outdir out

Expects the same raw columns as your original file:
  Notif.date, Planner group, Functional Loc., equipment, Created On,
  Notif. Time, Completion time, Completn date, Planning plant, Priority,
  Notifictn type, Plnt WorkCenter
"""
import argparse
import os
import pickle
import warnings

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

FEATURE_COLS = [
    "equipment", "Functional Loc.", "Priority", "Notifictn type",
    "month", "day_of_week", "hour", "shift", "year",
]
CATEGORICAL_COLS = ["equipment", "Functional Loc.", "Priority", "Notifictn type", "shift"]
UNSEEN_TOKEN = "__UNSEEN__"


def get_risk(days):
    if days <= 30:
        return "HIGH"
    elif days <= 90:
        return "MEDIUM"
    return "LOW"


def clean(df):
    print(f"Raw shape: {df.shape}")

    # Parse dates (same formats as original)
    df["Notif.date"] = pd.to_datetime(df["Notif.date"], format="%Y%m%d", errors="coerce")
    df["Created On"] = pd.to_datetime(df["Created On"], format="%d/%m/%Y", errors="coerce")
    df["Completn date"] = pd.to_datetime(df["Completn date"], format="mixed", dayfirst=True, errors="coerce")

    # Temporal features
    df["year"] = df["Notif.date"].dt.year
    df["month"] = df["Notif.date"].dt.month
    df["day_of_week"] = df["Notif.date"].dt.dayofweek
    df["hour"] = pd.to_datetime(df["Notif. Time"], format="%H:%M:%S", errors="coerce").dt.hour

    def get_shift(hour):
        if pd.isnull(hour):
            return "unknown"
        elif 6 <= hour <= 13:
            return "Morning"
        elif 14 <= hour <= 21:
            return "Afternoon"
        return "Night"

    df["shift"] = df["hour"].apply(get_shift)

    df["Completn date"] = pd.to_datetime(df["Completn date"], errors="coerce")
    df["resolution_days"] = (df["Completn date"] - df["Notif.date"]).dt.days
    df.loc[df["resolution_days"] < 0, "resolution_days"] = None

    df = df.drop(columns=["Planner group", "Planning plant", "Plnt WorkCenter"], errors="ignore")

    df["Priority"] = df["Priority"].fillna(df["Priority"].mode()[0])
    df["Notifictn type"] = df["Notifictn type"].fillna(df["Notifictn type"].mode()[0])
    df["resolution_days"] = df["resolution_days"].fillna(df["resolution_days"].median())

    df = df.drop(columns=["Created On"], errors="ignore")
    df = df.dropna(subset=["Completion time", "Completn date"])
    print(f"Shape after basic cleaning: {df.shape}")

    # Target: days until THIS equipment's next defect (computed on RAW,
    # un-encoded text categories, sorted chronologically per equipment)
    df = df.sort_values(["equipment", "Notif.date"]).reset_index(drop=True)
    df["next_defect_date"] = df.groupby("equipment")["Notif.date"].shift(-1)
    df["days_to_next_defect"] = (df["next_defect_date"] - df["Notif.date"]).dt.days
    df = df.dropna(subset=["days_to_next_defect"])
    df["days_to_next_defect"] = df["days_to_next_defect"].astype(int)
    df = df[df["days_to_next_defect"] > 0]
    print(f"After deriving target (last record per equipment dropped): {df.shape}")

    df = df[df["days_to_next_defect"] <= 365]
    print(f"After clipping outliers (>365 days): {df.shape}")

    return df


def temporal_split(df, test_frac=0.2):
    """Single, honest chronological split. All rows are sorted by
    Notif.date; the earliest (1-test_frac) go to train, the rest to test.
    No separate validation slice is fabricated — if you need one for
    hyperparameter tuning, use time-series cross-validation on the
    training set instead (done in 02_train_and_evaluate.py)."""
    df = df.sort_values("Notif.date").reset_index(drop=True)
    cutoff_idx = int(len(df) * (1 - test_frac))
    cutoff_date = df.iloc[cutoff_idx]["Notif.date"]

    train_df = df[df["Notif.date"] < cutoff_date].copy()
    test_df = df[df["Notif.date"] >= cutoff_date].copy()
    print(f"\nChronological split cutoff date: {cutoff_date.date()}")
    print(f"Train: {len(train_df)} rows ({train_df['Notif.date'].min().date()} - {train_df['Notif.date'].max().date()})")
    print(f"Test : {len(test_df)} rows ({test_df['Notif.date'].min().date()} - {test_df['Notif.date'].max().date()})")
    return train_df, test_df


def fit_encoders_on_train(train_df, cols):
    encoders = {}
    for col in cols:
        le = LabelEncoder()
        classes = sorted(train_df[col].astype(str).unique().tolist()) + [UNSEEN_TOKEN]
        le.classes_ = np.array(classes)
        encoders[col] = le
    return encoders


def apply_encoder(series, le):
    """Map values; anything not seen during training becomes UNSEEN_TOKEN
    rather than crashing. Prints how many rows were affected."""
    known = set(le.classes_)
    s = series.astype(str)
    n_unseen = (~s.isin(known)).sum()
    s = s.where(s.isin(known), UNSEEN_TOKEN)
    return le.transform(s), n_unseen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="korba_defects.csv")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--test_frac", type=float, default=0.2)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    if args.input.lower().endswith((".xls", ".xlsx")):
        raw = pd.read_excel(args.input)
    else:
        raw = pd.read_csv(args.input)
    clean_df = clean(raw)

    train_df, test_df = temporal_split(clean_df, args.test_frac)

    encoders = fit_encoders_on_train(train_df, CATEGORICAL_COLS)

    for split_name, split_df in [("train", train_df), ("test", test_df)]:
        for col in CATEGORICAL_COLS:
            encoded, n_unseen = apply_encoder(split_df[col], encoders[col])
            split_df[col] = encoded
            if n_unseen > 0:
                print(f"  [{split_name}] '{col}': {n_unseen} rows had a category unseen in training -> mapped to UNSEEN")

    train_out = train_df[FEATURE_COLS + ["days_to_next_defect"]]
    test_out = test_df[FEATURE_COLS + ["days_to_next_defect"]]

    train_out.to_csv(os.path.join(args.outdir, "train.csv"), index=False)
    test_out.to_csv(os.path.join(args.outdir, "test.csv"), index=False)
    pickle.dump(encoders, open(os.path.join(args.outdir, "label_encoders.pkl"), "wb"))
    pickle.dump(FEATURE_COLS, open(os.path.join(args.outdir, "feature_columns.pkl"), "wb"))

    # Save the full raw (pre-encoding, pre-split) labeled history too --
    # this is what the retraining script needs to correctly recompute
    # days_to_next_defect when new records arrive, instead of faking it
    # with resolution_days.
    clean_df.to_csv(os.path.join(args.outdir, "raw_history_with_labels.csv"), index=False)

    print("\n=== SUMMARY (use these numbers in the paper, Table 4/5, Section 3.5) ===")
    print(f"Total raw records: {raw.shape[0]}")
    print(f"Cleaned records: {clean_df.shape[0]}")
    print(f"Unique equipment: {clean_df['equipment'].nunique()}")
    print(f"Unique functional locations: {clean_df['Functional Loc.'].nunique()}")
    print(f"Features used: {len(FEATURE_COLS)} -> {FEATURE_COLS}")
    print(f"Train records: {len(train_out)}  ({len(train_out)/len(clean_df)*100:.1f}%)")
    print(f"Test records: {len(test_out)}  ({len(test_out)/len(clean_df)*100:.1f}%)")

    for name, d in [("Train", train_df), ("Test", test_df)]:
        risk = d["days_to_next_defect"].apply(get_risk)
        print(f"\n{name} risk distribution:")
        print((risk.value_counts(normalize=True) * 100).round(1))

    print(f"\nFiles written to: {args.outdir}/")


if __name__ == "__main__":
    main()
