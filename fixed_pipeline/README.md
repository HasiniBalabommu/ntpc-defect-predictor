# Corrected pipeline — run order

These 4 scripts replace `STEP2_CLEANING.ipynb`, `STEP_3_MODEL.ipynb`, and
`scripts/retrain.py`. Run them **on your machine**, where the data folder is
(nothing here needs the raw data to be shared with me).

## 0. Setup
```
pip install pandas numpy scikit-learn scipy xgboost lightgbm catboost
```
(xgboost/lightgbm/catboost are optional — the scripts skip them gracefully
if not installed, but for the paper's Table 2a you want all of them.)

## 1. Clean + split (replaces STEP2_CLEANING.ipynb)
```
python 01_clean_and_split.py --input korba_defects.csv --outdir out
```
This prints everything you need for the paper's Table 4/5 and Section 3.5
(total records, cleaned records, unique equipment/locations, one consistent
train/test split with the actual date cutoff). **Copy the full console
output** — that's what I need back.

Produces in `out/`: `train.csv`, `test.csv`, `label_encoders.pkl`,
`feature_columns.pkl`, `raw_history_with_labels.csv`.

## 2. Train + evaluate (replaces STEP_3_MODEL.ipynb)
```
python 02_train_and_evaluate.py --indir out --outdir out
```
This produces, all from internally-consistent data:
- `table2a_benchmark.csv` — 8 algorithms, all lightly tuned the same way
- `table9_classification_report.csv` / `table10_confusion_matrix.csv` —
  guaranteed consistent with each other (the script asserts this and will
  error out loudly if they ever aren't)
- `table6a_feature_importance.csv` — all 9 features, including `hour`
- `table_ablation.csv` — accuracy with each feature removed one at a time
- McNemar's test + bootstrap CI for RF vs. majority baseline (real
  significance test, replaces the old seed-CI argument)
- `results_report.txt` — everything above in one text file
- `model.pkl`, `avg_days.pkl` — updated model files for the app

**Send me `results_report.txt` and the `table*.csv` files** — that's what
I'll use to rewrite the Results section with real numbers.

## 3. Retraining pipeline fix (replaces scripts/retrain.py)
Only run this once you have new records to add. It needs new rows in a CSV
with raw (unencoded) columns: `equipment, Functional Loc., Priority,
Notifictn type, Notif.date, Notif. Time, Completn date, Completion time`.
```
python 03_retrain_fixed.py --raw_history out/raw_history_with_labels.csv \
    --encoders out/label_encoders.pkl --feature_cols out/feature_columns.pkl \
    --new_records new_records.csv --outdir out
```
Also copy `scripts/excel_to_db.py` and `app/server.py`'s bulk-upload route
so they write new rows to `new_records.csv` in this same raw format instead
of the DB schema the old `retrain.py` expected — happy to patch those too
once you confirm this script works.

## 4. LLM evaluation (no equivalent existed before)
Requires Ollama running locally with `llama3.2:1b` pulled.
```
python 04_llm_eval.py --outdir out
```
Edit the `QUESTIONS` dict at the top of the script first — put in your real
question set, at least 10+ per category (ideally 20-30, since n=10 makes
percentages like "95%" impossible to interpret, as the reviewer noted).
Produces `llm_eval_config.json` (model tag, Ollama version, temperature/
top_p — reviewer asked for this) and `llm_eval_results.json` (every
question, response, and verdict, auditable).

**Send me both JSON files.**

---

## Also worth fixing in `app/predictor.py` (not run as a script — just a
heads up before you redeploy)
Right now every prediction uses **hardcoded** `Priority: 'Priority A'`,
`Notifictn type: 'M2'`, `Functional Loc.: classes_[0]` for every piece of
equipment — only `equipment` and the current date actually vary. That's a
train/serve mismatch: the model learned from real varying values but never
sees them at inference. Once you send me the retrained `avg_days.pkl` /
`model.pkl`, I'll patch `predictor.py` to pull each equipment's most recent
real Priority/NotifType/FuncLoc from its history instead of hardcoding one
value for everyone.
