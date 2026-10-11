"""
03_retrain_fixed.py

Fixes vs. the original scripts/retrain.py:
  1. NEVER uses resolution_days as a stand-in for days_to_next_defect.
     A brand-new record has no "next defect" yet, so it CANNOT be given a
     real label. Instead this script appends the new raw record to
     raw_history_with_labels.csv (unlabeled, i.e. it becomes the CURRENT
     latest record for that equipment) and re-runs the same groupby-shift
     logic used in 01_clean_and_split.py over the whole history. This
     correctly back-fills the label for the PREVIOUS record of that same
     equipment (which now has a real "next defect" date), while the new
     record itself stays unlabeled until ITS next defect arrives. This is
     the honest answer to "how do you get a label for a record with no
     next-defect date yet": you don't, until there is one.
  2. Never silently drops unseen equipment. New equipment/category values
     are added to the encoder's class list (which is safe because we
     refit the RandomForest from scratch every retrain anyway).
  3. Functional Location is read from the new record itself instead of
     being hardcoded to 0.
  4. Uses relative paths throughout and fails loudly (not silently) if a
     required file is missing.
  5. Re-splits chronologically (not randomly) so retraining accuracy stays
     comparable to the original evaluation protocol.

Run:
    python 03_retrain_fixed.py --raw_history out/raw_history_with_labels.csv \\
        --encoders out/label_encoders.pkl --feature_cols out/feature_columns.pkl \\
        --new_records new_records.csv --outdir out
"""
import argparse
import os
import pickle
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

FEATURE_COLS_TEXT = ["equipment", "Functional Loc.", "Priority", "Notifictn type", "shift"]
UNSEEN_TOKEN = "__UNSEEN__"


def get_risk(days):
    if days <= 30:
        return "HIGH"
    elif days <= 90:
        return "MEDIUM"
    return "LOW"


def log(msg, log_path):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(log_path, "a") as f:
        f.write(line + "\n")


def extend_encoder(le, new_categories):
    """Safely add previously-unseen category values to an encoder's class
    list. Because we refit the whole RandomForest after this, the model
    always sees consistent codes -- unlike the original script, which
    just skipped unseen equipment entirely."""
    current = set(le.classes_.tolist())
    to_add = [c for c in new_categories if c not in current and c != UNSEEN_TOKEN]
    if to_add:
        le.classes_ = np.array(sorted(current | set(to_add)) + (
            [UNSEEN_TOKEN] if UNSEEN_TOKEN not in current else []))
    return le


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw_history", required=True,
                     help="raw_history_with_labels.csv produced by 01_clean_and_split.py")
    ap.add_argument("--encoders", required=True)
    ap.add_argument("--feature_cols", required=True)
    ap.add_argument("--new_records", required=True,
                     help="CSV of new rows with RAW (unencoded) columns: "
                          "equipment, Functional Loc., Priority, Notifictn type, "
                          "Notif.date, Notif. Time, Completn date, Completion time")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    log_path = os.path.join(args.outdir, "retrain_log.txt")

    for path, name in [(args.raw_history, "raw history"), (args.encoders, "encoders"),
                        (args.feature_cols, "feature columns"), (args.new_records, "new records")]:
        if not os.path.exists(path):
            log(f"FATAL: {name} file not found at {path}", log_path)
            raise SystemExit(1)

    log("Starting corrected retraining pipeline...", log_path)

    history = pd.read_csv(args.raw_history, parse_dates=["Notif.date"])
    new_rows = pd.read_csv(args.new_records, parse_dates=["Notif.date"])
    encoders = pickle.load(open(args.encoders, "rb"))
    feature_cols = pickle.load(open(args.feature_cols, "rb"))

    log(f"History rows: {len(history)}. New raw rows: {len(new_rows)}.", log_path)

    # NOTE: raw_history_with_labels.csv (from 01_clean_and_split.py) already
    # stores RAW TEXT category values (encoding is only applied to the
    # separate train.csv/test.csv), so no inverse_transform is needed here
    # -- we just concatenate the raw history directly with the new raw rows.
    combined = pd.concat([history, new_rows], ignore_index=True, sort=False)

    # 2. Recompute month/day_of_week/hour/shift/year + the target label from
    #    scratch over the FULL combined raw history -- this is the only
    #    correct way to get a label for records that now have a "next
    #    defect" because a newer record was just added.
    combined["year"] = combined["Notif.date"].dt.year
    combined["month"] = combined["Notif.date"].dt.month
    combined["day_of_week"] = combined["Notif.date"].dt.dayofweek
    if "Notif. Time" in combined.columns:
        combined["hour"] = pd.to_datetime(combined["Notif. Time"], format="%H:%M:%S", errors="coerce").dt.hour
    combined["hour"] = combined["hour"].fillna(combined["hour"].median())

    def get_shift(hour):
        if pd.isnull(hour):
            return "unknown"
        elif 6 <= hour <= 13:
            return "Morning"
        elif 14 <= hour <= 21:
            return "Afternoon"
        return "Night"

    combined["shift"] = combined["hour"].apply(get_shift)

    combined = combined.sort_values(["equipment", "Notif.date"]).reset_index(drop=True)
    combined["next_defect_date"] = combined.groupby("equipment")["Notif.date"].shift(-1)
    combined["days_to_next_defect"] = (combined["next_defect_date"] - combined["Notif.date"]).dt.days

    n_unlabeled = combined["days_to_next_defect"].isna().sum()
    log(f"{n_unlabeled} records (the latest record per equipment) have no "
        f"next-defect date yet and are correctly excluded from training, "
        f"not fake-labeled.", log_path)

    labeled = combined.dropna(subset=["days_to_next_defect"]).copy()
    labeled["days_to_next_defect"] = labeled["days_to_next_defect"].astype(int)
    labeled = labeled[(labeled["days_to_next_defect"] > 0) & (labeled["days_to_next_defect"] <= 365)]

    # 3. Extend encoders for any genuinely new category values, then encode.
    for col in FEATURE_COLS_TEXT:
        if col not in encoders:
            continue
        encoders[col] = extend_encoder(encoders[col], labeled[col].astype(str).unique().tolist())
        le = encoders[col]
        known = set(le.classes_.tolist())
        labeled[col] = labeled[col].astype(str).where(labeled[col].astype(str).isin(known), UNSEEN_TOKEN)
        labeled[col] = le.transform(labeled[col])

    # 4. Chronological re-split (same protocol as the original evaluation).
    labeled = labeled.sort_values("Notif.date").reset_index(drop=True)
    cutoff = int(len(labeled) * 0.8)
    train_df, test_df = labeled.iloc[:cutoff], labeled.iloc[cutoff:]

    x_train, y_train = train_df[feature_cols], train_df["days_to_next_defect"].apply(get_risk)
    x_test, y_test = test_df[feature_cols], test_df["days_to_next_defect"].apply(get_risk)

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(x_train, y_train)
    acc = accuracy_score(y_test, model.predict(x_test)) * 100
    log(f"Retrained on {len(train_df)} rows, tested on {len(test_df)} rows. "
        f"Test accuracy: {acc:.2f}%", log_path)

    # 5. Persist everything, including the updated raw history so the NEXT
    #    retrain starts from the correct, fully-labeled state.
    pickle.dump(model, open(os.path.join(args.outdir, "model.pkl"), "wb"))
    pickle.dump(encoders, open(os.path.join(args.outdir, "label_encoders.pkl"), "wb"))
    combined.to_csv(os.path.join(args.outdir, "raw_history_with_labels.csv"), index=False)

    log("Retraining complete.", log_path)


if __name__ == "__main__":
    main()
