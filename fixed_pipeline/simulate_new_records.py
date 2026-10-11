"""
simulate_new_records.py

You don't have a genuinely new SAP export yet, so this creates a realistic
test case from your existing data: it takes the most recent N rows (by
date) out of raw_history_with_labels.csv and treats them as if they just
arrived as new records, while the remaining rows become the "history before
the new data". This lets you verify 03_retrain_fixed.py actually works
end-to-end before you have real new data.

Run:
    python simulate_new_records.py --history out/raw_history_with_labels.csv --outdir out --n 20
"""
import argparse
import os

import pandas as pd

RAW_COLS_FOR_NEW_RECORDS = [
    "equipment", "Functional Loc.", "Priority", "Notifictn type",
    "Notif.date", "Notif. Time", "Completn date", "Completion time",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="out/raw_history_with_labels.csv")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--n", type=int, default=20, help="how many of the most recent rows to hold out as 'new'")
    args = ap.parse_args()

    df = pd.read_csv(args.history, parse_dates=["Notif.date"])
    df = df.sort_values("Notif.date").reset_index(drop=True)

    held_out = df.tail(args.n)
    remaining = df.iloc[:-args.n]

    cols_present = [c for c in RAW_COLS_FOR_NEW_RECORDS if c in held_out.columns]
    new_records = held_out[cols_present]

    new_records_path = os.path.join(args.outdir, "new_records.csv")
    history_before_path = os.path.join(args.outdir, "history_before_new.csv")

    new_records.to_csv(new_records_path, index=False)
    remaining.to_csv(history_before_path, index=False)

    print(f"Held out {len(held_out)} most recent rows as simulated 'new records' -> {new_records_path}")
    print(f"Remaining {len(remaining)} rows saved as pre-existing history -> {history_before_path}")
    print(f"Date range of simulated new records: {held_out['Notif.date'].min().date()} to {held_out['Notif.date'].max().date()}")
    print("\nNow run:")
    print(f"  python 03_retrain_fixed.py --raw_history {history_before_path} "
          f"--encoders out/label_encoders.pkl --feature_cols out/feature_columns.pkl "
          f"--new_records {new_records_path} --outdir out")


if __name__ == "__main__":
    main()
