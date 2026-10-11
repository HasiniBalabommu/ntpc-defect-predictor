"""
02_train_and_evaluate.py

Fixes vs. the original STEP_3_MODEL.ipynb:
  1. Table 9 (per-class precision/recall/F1) and Table 10 (confusion
     matrix) are now computed from the SAME y_test/y_pred in the SAME
     place, so they can never contradict each other again.
  2. All candidate algorithms get light, consistent hyperparameter tuning
     via RandomizedSearchCV with TimeSeriesSplit on the TRAINING set only
     (previously all 8 algorithms used untuned defaults, which unfairly
     favored/disfavored some).
  3. Replaces the invalid "seed CI vs baseline" significance claim with
     McNemar's test (paired, appropriate for two classifiers evaluated on
     the same held-out samples) and a bootstrap CI on the accuracy
     difference. The 10-seed run is kept but relabeled as an algorithmic
     stability check, not a significance test.
  4. Adds an ablation study: drop one feature at a time, retrain, report
     the accuracy delta -- lets you see whether 'equipment'/'Functional
     Loc.' are doing legitimate work or just memorizing identity.
  5. Feature importance table now includes all 9 features (hour was
     missing before).
  6. avg_days lookup (used for the "expected date" in the UI) is computed
     from the TRAINING set only, not the full dataset.

Run (after 01_clean_and_split.py):
    python 02_train_and_evaluate.py --indir out --outdir out
"""
import argparse
import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                              classification_report, confusion_matrix,
                              f1_score, roc_auc_score)
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler, label_binarize
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

RISK_ORDER = ["HIGH", "MEDIUM", "LOW"]


def get_risk(days):
    if days <= 30:
        return "HIGH"
    elif days <= 90:
        return "MEDIUM"
    return "LOW"


def mcnemar_test(y_true, pred_a, pred_b):
    """Paired test: is classifier A significantly different from B on the
    SAME test samples? Uses the standard McNemar chi-square with
    continuity correction."""
    correct_a = np.array(pred_a) == np.array(y_true)
    correct_b = np.array(pred_b) == np.array(y_true)
    n01 = int(np.sum(correct_a & ~correct_b))  # A right, B wrong
    n10 = int(np.sum(~correct_a & correct_b))  # A wrong, B right
    if n01 + n10 == 0:
        return {"n01": n01, "n10": n10, "statistic": 0.0, "p_value": 1.0}
    statistic = (abs(n01 - n10) - 1) ** 2 / (n01 + n10)
    p_value = 1 - stats.chi2.cdf(statistic, df=1)
    return {"n01": n01, "n10": n10, "statistic": float(statistic), "p_value": float(p_value)}


def bootstrap_accuracy_diff_ci(y_true, pred_a, pred_b, n_boot=2000, seed=42):
    """Bootstrap CI on (accuracy_a - accuracy_b), resampling test rows with
    replacement. If the CI excludes 0, the difference is significant."""
    rng = np.random.default_rng(seed)
    y_true = np.array(y_true)
    pred_a = np.array(pred_a)
    pred_b = np.array(pred_b)
    n = len(y_true)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        acc_a = np.mean(pred_a[idx] == y_true[idx])
        acc_b = np.mean(pred_b[idx] == y_true[idx])
        diffs.append(acc_a - acc_b)
    diffs = np.array(diffs)
    return {
        "mean_diff": float(diffs.mean()),
        "ci_lower": float(np.percentile(diffs, 2.5)),
        "ci_upper": float(np.percentile(diffs, 97.5)),
    }


def tune(model, param_dist, x_train, y_train, n_iter=15, seed=42):
    """Light, time-aware tuning. TimeSeriesSplit keeps validation folds
    chronologically after training folds within the training set, so we
    don't leak future information even during tuning."""
    tscv = TimeSeriesSplit(n_splits=3)
    search = RandomizedSearchCV(
        model, param_dist, n_iter=n_iter, cv=tscv,
        scoring="accuracy", random_state=seed, n_jobs=-1,
    )
    search.fit(x_train, y_train)
    return search.best_estimator_, search.best_params_


def run_benchmark(x_train, y_train, x_test, y_test):
    import time
    results = {}
    le_temp = LabelEncoder()
    y_train_num = le_temp.fit_transform(y_train)
    y_test_num = le_temp.transform(y_test)

    # Scaling helps LR/SVM/MLP converge much faster on integer-coded
    # categorical features (e.g. 'equipment' ranging 0-387) -- fit on
    # train only, applied to both.
    scaler = StandardScaler()
    x_train_scaled = pd.DataFrame(scaler.fit_transform(x_train), columns=x_train.columns, index=x_train.index)
    x_test_scaled = pd.DataFrame(scaler.transform(x_test), columns=x_test.columns, index=x_test.index)

    def record(name, model, ytr, yte, xtr, xte):
        pred_tr = model.predict(xtr)
        pred_te = model.predict(xte)
        results[name] = {
            "train_acc": accuracy_score(ytr, pred_tr) * 100,
            "test_acc": accuracy_score(yte, pred_te) * 100,
            "best_params": getattr(model, "_tuned_params", "default"),
        }
        return pred_te

    def step(name, fn):
        print(f"\n--- Tuning {name} ---", flush=True)
        t0 = time.time()
        out = fn()
        print(f"--- {name} done in {time.time() - t0:.1f}s ---", flush=True)
        return out

    # Logistic Regression (scaled -> converges without warnings)
    m, p = step("Logistic Regression", lambda: tune(
        LogisticRegression(max_iter=1000, random_state=42),
        {"C": [0.01, 0.1, 1, 10, 100]}, x_train_scaled, y_train))
    m._tuned_params = p
    record("Logistic Regression", m, y_train, y_test, x_train_scaled, x_test_scaled)

    # SVM (scaled + capped max_iter so it can't hang; small n_iter for speed)
    m, p = step("SVM", lambda: tune(
        SVC(random_state=42, max_iter=5000),
        {"C": [0.1, 1, 10], "kernel": ["rbf", "linear"]}, x_train_scaled, y_train, n_iter=4))
    m._tuned_params = p
    record("SVM", m, y_train, y_test, x_train_scaled, x_test_scaled)

    # Decision Tree
    m, p = step("Decision Tree", lambda: tune(
        DecisionTreeClassifier(random_state=42),
        {"max_depth": [4, 6, 8, 10, 15, None], "min_samples_leaf": [1, 5, 10, 20]},
        x_train, y_train))
    m._tuned_params = p
    record("Decision Tree", m, y_train, y_test, x_train, x_test)

    # MLP (scaled -> converges faster; capped iterations)
    m, p = step("Neural Network (MLP)", lambda: tune(
        MLPClassifier(random_state=42, max_iter=500),
        {"hidden_layer_sizes": [(50,), (100,), (50, 25)], "alpha": [0.0001, 0.001, 0.01]},
        x_train_scaled, y_train, n_iter=4))
    m._tuned_params = p
    record("Neural Network (MLP)", m, y_train, y_test, x_train_scaled, x_test_scaled)

    # Random Forest
    m, p = step("Random Forest", lambda: tune(
        RandomForestClassifier(random_state=42),
        {"n_estimators": [100, 200, 300], "max_depth": [8, 12, 16, None],
         "min_samples_leaf": [1, 3, 5]}, x_train, y_train))
    m._tuned_params = p
    rf_pred_test = record("Random Forest", m, y_train, y_test, x_train, x_test)
    rf_model = m

    # XGBoost / LightGBM / CatBoost (optional deps)
    for lib_name, import_fn, param_dist in [
        ("XGBoost", lambda: __import__("xgboost", fromlist=["XGBClassifier"]).XGBClassifier(
            random_state=42, eval_metric="mlogloss"),
         {"n_estimators": [100, 200], "max_depth": [3, 5, 7], "learning_rate": [0.01, 0.05, 0.1]}),
        ("LightGBM", lambda: __import__("lightgbm", fromlist=["LGBMClassifier"]).LGBMClassifier(
            random_state=42, verbose=-1),
         {"n_estimators": [100, 200], "max_depth": [3, 5, 7, -1], "learning_rate": [0.01, 0.05, 0.1]}),
        ("CatBoost", lambda: __import__("catboost", fromlist=["CatBoostClassifier"]).CatBoostClassifier(
            random_state=42, verbose=0),
         {"iterations": [100, 200], "depth": [4, 6, 8], "learning_rate": [0.01, 0.05, 0.1]}),
    ]:
        try:
            base = import_fn()
        except ImportError:
            print(f"\n{lib_name} not installed, skipping (pip install {lib_name.lower()})")
            continue
        m, p = step(lib_name, lambda base=base, param_dist=param_dist: tune(
            base, param_dist, x_train, y_train_num, n_iter=8))
        m._tuned_params = p
        record(lib_name, m, y_train_num, y_test_num, x_train, x_test)

    return results, rf_model, rf_pred_test


def ablation_study(x_train, y_train, x_test, y_test, feature_cols):
    print("\n=== ABLATION STUDY (drop one feature at a time) ===")
    base_model = RandomForestClassifier(n_estimators=200, random_state=42)
    base_model.fit(x_train, y_train)
    base_acc = accuracy_score(y_test, base_model.predict(x_test)) * 100
    print(f"Full model ({len(feature_cols)} features): {base_acc:.2f}%")

    rows = []
    for col in feature_cols:
        cols_wo = [c for c in feature_cols if c != col]
        m = RandomForestClassifier(n_estimators=200, random_state=42)
        m.fit(x_train[cols_wo], y_train)
        acc = accuracy_score(y_test, m.predict(x_test[cols_wo])) * 100
        rows.append({"dropped_feature": col, "test_acc_without": round(acc, 2),
                      "delta_vs_full": round(acc - base_acc, 2)})
        print(f"  without '{col}': {acc:.2f}%  (delta {acc - base_acc:+.2f})")
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--indir", default="out")
    ap.add_argument("--outdir", default="out")
    args = ap.parse_args()

    train_df = pd.read_csv(os.path.join(args.indir, "train.csv"))
    test_df = pd.read_csv(os.path.join(args.indir, "test.csv"))
    feature_cols = pickle.load(open(os.path.join(args.indir, "feature_columns.pkl"), "rb"))

    x_train, y_train = train_df[feature_cols], train_df["days_to_next_defect"].apply(get_risk)
    x_test, y_test = test_df[feature_cols], test_df["days_to_next_defect"].apply(get_risk)

    report_lines = []

    def log(s=""):
        print(s)
        report_lines.append(str(s))

    # --- Benchmark all algorithms with consistent tuning ---
    log("=== ALGORITHM BENCHMARK (tuned, same train/test split) ===")
    results, rf_model, rf_pred_test = run_benchmark(x_train, y_train, x_test, y_test)
    bench_df = pd.DataFrame(results).T.sort_values("test_acc", ascending=False)
    log(bench_df.to_string())
    bench_df.to_csv(os.path.join(args.outdir, "table2a_benchmark.csv"))

    # --- Majority baseline ---
    majority_class = y_train.value_counts().idxmax()
    baseline_pred = [majority_class] * len(y_test)
    baseline_acc = accuracy_score(y_test, baseline_pred) * 100
    log(f"\nMajority-class baseline ({majority_class}): {baseline_acc:.2f}%")

    # --- Classification report + confusion matrix from the SAME predictions ---
    log("\n=== TABLE 9 -- Per-class precision/recall/F1 (final RF model) ===")
    report = classification_report(y_test, rf_pred_test, labels=RISK_ORDER, target_names=RISK_ORDER, output_dict=True)
    report_df = pd.DataFrame(report).transpose().round(3)
    log(report_df.to_string())
    report_df.to_csv(os.path.join(args.outdir, "table9_classification_report.csv"))

    log("\n=== TABLE 10 -- Confusion matrix (same predictions as Table 9) ===")
    cm = confusion_matrix(y_test, rf_pred_test, labels=RISK_ORDER)
    cm_df = pd.DataFrame(cm, index=[f"Actual {c}" for c in RISK_ORDER],
                          columns=[f"Pred. {c}" for c in RISK_ORDER])
    log(cm_df.to_string())
    cm_df.to_csv(os.path.join(args.outdir, "table10_confusion_matrix.csv"))

    # sanity check: recall from confusion matrix must equal recall in report
    for i, c in enumerate(RISK_ORDER):
        recall_from_cm = cm[i, i] / cm[i].sum()
        recall_from_report = report[c]["recall"]
        assert abs(recall_from_cm - recall_from_report) < 1e-6, \
            f"Table 9/10 mismatch for {c}! This should be impossible now -- check for a bug."
    log("\n[OK] Table 9 and Table 10 are internally consistent (verified programmatically).")

    # --- Feature importance (all 9 features) ---
    log("\n=== TABLE 6a -- Feature importance (all features) ===")
    imp_df = pd.DataFrame({"Feature": feature_cols, "Importance": rf_model.feature_importances_})
    imp_df = imp_df.sort_values("Importance", ascending=False)
    log(imp_df.to_string(index=False))
    imp_df.to_csv(os.path.join(args.outdir, "table6a_feature_importance.csv"), index=False)

    # --- Statistical significance: McNemar + bootstrap CI, RF vs majority baseline ---
    log("\n=== STATISTICAL SIGNIFICANCE: RF vs majority baseline (paired, same test set) ===")
    mcnemar = mcnemar_test(y_test, rf_pred_test, baseline_pred)
    log(f"McNemar's test: n01={mcnemar['n01']}, n10={mcnemar['n10']}, "
        f"stat={mcnemar['statistic']:.3f}, p={mcnemar['p_value']:.5f}")
    boot = bootstrap_accuracy_diff_ci(y_test, rf_pred_test, baseline_pred)
    log(f"Bootstrap 95% CI on (RF acc - baseline acc): "
        f"mean={boot['mean_diff']*100:.2f}pp, CI=[{boot['ci_lower']*100:.2f}, {boot['ci_upper']*100:.2f}]pp")
    log("(If the CI excludes 0 and p < 0.05, RF is significantly better than the baseline "
        "on THIS test set -- this replaces the invalid 'seed CI vs baseline' argument.)")

    # --- 10-seed stability (relabeled -- NOT a significance test) ---
    log("\n=== ALGORITHMIC STABILITY across 10 random seeds (RF only; not a significance test) ===")
    seed_acc, seed_bal, seed_f1 = [], [], []
    for seed in range(1, 11):
        m = RandomForestClassifier(n_estimators=100, random_state=seed)
        m.fit(x_train, y_train)
        pred = m.predict(x_test)
        seed_acc.append(accuracy_score(y_test, pred) * 100)
        seed_bal.append(balanced_accuracy_score(y_test, pred))
        seed_f1.append(f1_score(y_test, pred, average="macro"))
    log(f"Mean test acc: {np.mean(seed_acc):.2f}% (std {np.std(seed_acc):.2f}) "
        f"-- variation due to RF's internal randomness, same train/test split every time.")
    log(f"Mean balanced acc: {np.mean(seed_bal):.3f}, mean macro F1: {np.mean(seed_f1):.3f}")

    # --- Ablation study ---
    ablation_df = ablation_study(x_train, y_train, x_test, y_test, feature_cols)
    ablation_df.to_csv(os.path.join(args.outdir, "table_ablation.csv"), index=False)

    # --- ROC / AUC ---
    log("\n=== ROC-AUC (one-vs-rest) ===")
    y_test_bin = label_binarize(y_test, classes=RISK_ORDER)
    y_prob = rf_model.predict_proba(x_test)
    model_classes = list(rf_model.classes_)
    aucs = {}
    for i, cls in enumerate(RISK_ORDER):
        idx = model_classes.index(cls)
        aucs[cls] = roc_auc_score(y_test_bin[:, i], y_prob[:, idx])
    log(f"Per-class AUC: {aucs}")
    log(f"Macro AUC: {np.mean(list(aucs.values())):.3f}")

    # --- avg_days lookup computed from TRAIN ONLY (not full dataset) ---
    train_df["risk"] = train_df["days_to_next_defect"].apply(get_risk)
    avg_days = train_df.groupby(["equipment", "risk"])["days_to_next_defect"].mean().round().astype(int)
    avg_days_dict = {}
    for (equipment, risk), days in avg_days.items():
        avg_days_dict.setdefault(equipment, {})[risk] = days
    pickle.dump(avg_days_dict, open(os.path.join(args.outdir, "avg_days.pkl"), "wb"))

    pickle.dump(rf_model, open(os.path.join(args.outdir, "model.pkl"), "wb"))

    with open(os.path.join(args.outdir, "results_report.txt"), "w") as f:
        f.write("\n".join(report_lines))

    print(f"\nAll tables + model written to {args.outdir}/. "
          f"Send back results_report.txt and the table*.csv files.")


if __name__ == "__main__":
    main()
