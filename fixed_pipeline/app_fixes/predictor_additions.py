"""
predictor_additions.py

Two new functions to ADD to app/predictor.py (paste them in, don't
replace the file -- they're new capabilities, not fixes to existing ones).

They require ONE new file to exist: model/history.csv, containing the
per-notification raw history (equipment name + date + resolution_days).
Generate it from your corrected pipeline like this:

    import pandas as pd
    df = pd.read_csv("fixed_pipeline/out/raw_history_with_labels.csv")
    df[["equipment", "Notif.date", "resolution_days"]].to_csv("model/history.csv", index=False)

Without this file, get_history() returns None and the chat route will
correctly tell the user history isn't available, instead of inventing it.
"""
import os
import pandas as pd

# Add near the top of predictor.py, alongside the other pickle loads:
HISTORY_PATH = os.path.join(MODEL_DIR, "history.csv")  # noqa: F821 (MODEL_DIR already defined in predictor.py)
try:
    _history_df = pd.read_csv(HISTORY_PATH, parse_dates=["Notif.date"])
except FileNotFoundError:
    _history_df = None


def get_history(equipment_name, n=5):
    """Real per-equipment notification history, or None if unavailable.
    Returns a list of formatted strings (most recent first), or an empty
    list if the equipment exists but has no recorded history, or None if
    the history file itself isn't present at all."""
    if _history_df is None:
        return None
    subset = _history_df[_history_df["equipment"] == equipment_name]
    subset = subset.sort_values("Notif.date", ascending=False).head(n)
    if subset.empty:
        return []
    lines = []
    for _, row in subset.iterrows():
        res = row.get("resolution_days", None)
        res_str = f"{int(res)} days" if pd.notna(res) else "unknown duration"
        lines.append(f"- {row['Notif.date'].date()}: resolved in {res_str}")
    return lines


def predict_top_n(n=5, zone_filter=None):
    """Real top-N ranking, reusing the existing predict_all_equipment()
    (already sorted HIGH -> MEDIUM -> LOW, then by days ascending)."""
    results = predict_all_equipment()  # noqa: F821 (already defined in predictor.py)
    if zone_filter:
        results = [r for r in results if zone_filter.upper() in r["equipment"].upper()]
    return results[:n]
