"""
make_history_csv.py

Generates model/history.csv from the corrected pipeline's output, needed
by the new get_history() function in predictor.py. Without this file,
history questions will correctly say "not available" instead of inventing
an answer -- but WITH it, they can answer truthfully.

Run once (and again after every retrain, since retraining updates
raw_history_with_labels.csv):
    python make_history_csv.py --raw_history out/raw_history_with_labels.csv --model_dir ../model
"""
import argparse
import os

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw_history", default="out/raw_history_with_labels.csv")
    ap.add_argument("--model_dir", default="../model")
    args = ap.parse_args()

    df = pd.read_csv(args.raw_history, parse_dates=["Notif.date"])
    out = df[["equipment", "Notif.date", "resolution_days"]]
    os.makedirs(args.model_dir, exist_ok=True)
    out_path = os.path.join(args.model_dir, "history.csv")
    out.to_csv(out_path, index=False)
    print(f"Wrote {len(out)} history rows for {out['equipment'].nunique()} equipment to {out_path}")


if __name__ == "__main__":
    main()
