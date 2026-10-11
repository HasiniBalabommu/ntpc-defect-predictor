"""
query_router.py

Fixes the root cause found during LLM evaluation: server.py's old chat
route ran fuzzy matching against the ENTIRE user sentence for every
keyword-containing message, so broad questions ("what is the most
vulnerable equipment", "rank the top 5") got silently pinned to one
arbitrary, unrelated piece of equipment and answered as if that resolved
the question.

This module:
  1. Classifies the query into one of: comparison, history, single_equipment,
     or unclear -- BEFORE deciding how (or whether) to fetch grounding data.
  2. For single_equipment, uses a stricter match than plain fuzzy-matching
     the whole sentence: requires a high score AND a clear margin over the
     second-best candidate, so a generic sentence can't confidently "win"
     against an unrelated equipment name.
"""
import re
from fuzzywuzzy import fuzz

COMPARISON_KEYWORDS = [
    "compare", " vs ", "versus", "rank", "top 5", "top5", "top ", "most vulnerable",
    "most urgent", "highest risk", "highest failure", "which equipment",
    "which cooling", "which pump", "which fan", "best equipment", "worst equipment",
    "list all", "all high risk", "all equipment", "improved the most",
]
HISTORY_KEYWORDS = [
    "history", "past", "previous", "recurring", "how many defects",
    "last recorded", "notification", "defect trend", "logged", "how often",
]


def classify_intent(message):
    m = message.lower()
    if any(k in m for k in COMPARISON_KEYWORDS):
        return "comparison"
    if any(k in m for k in HISTORY_KEYWORDS):
        return "history"
    return "maybe_single_equipment"


def extract_equipment(message, equipment_names, min_score=82, min_margin=10):
    """Stricter than the original find_equipment(): requires the best match
    to clearly beat the runner-up, not just clear a fixed threshold. This
    prevents a generic sentence from confidently "matching" an unrelated
    equipment name just because it's the least-bad option among 388
    candidates."""
    if not equipment_names:
        return None, 0
    scored = [(name, fuzz.partial_ratio(message.upper(), name.upper())) for name in equipment_names]
    scored.sort(key=lambda x: -x[1])
    best_name, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0
    if best_score >= min_score and (best_score - second_score) >= min_margin:
        return best_name, best_score
    return None, best_score


def extract_top_n(message, default_n=5):
    m = re.search(r"top\s*(\d+)", message.lower())
    return int(m.group(1)) if m else default_n


def extract_zone_filter(message):
    """Very simple: if the message mentions 'unit N' or a specific area
    word, use it to filter the comparison table. Extend as needed."""
    m = re.search(r"unit\s*(\d+)", message.lower())
    if m:
        return f"UNIT {m.group(1)}"
    return None
