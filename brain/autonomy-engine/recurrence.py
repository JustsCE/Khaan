"""
recurrence.py — Autonomy Engine v1.2
Detects recurring task patterns using fuzzy title matching.
Flags at N>=3 occurrences for automation proposal.
"""

import json
import datetime
from difflib import SequenceMatcher
from pathlib import Path

PATTERNS_PATH = Path(__file__).parent / "patterns.json"
SIMILARITY_THRESHOLD = 0.7
FLAG_AT = 3


def _load() -> dict:
    if not PATTERNS_PATH.exists():
        return {"version": "1.0", "patterns": []}
    return json.loads(PATTERNS_PATH.read_text())


def _save(data: dict):
    PATTERNS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def check(task: dict, record: bool = True) -> dict:
    """
    Check if task title matches an existing pattern.
    If record=True, adds an occurrence to the matching pattern (or creates new).

    Returns:
        {
            "recurring": bool,
            "count": int,          # how many times seen
            "flag_automation": bool,  # True if count >= FLAG_AT
            "matched_pattern": str | None,
        }
    """
    title = (task.get("title") or "").strip()
    if not title:
        return {"recurring": False, "count": 0, "flag_automation": False, "matched_pattern": None}

    data = _load()
    patterns = data.get("patterns", [])

    # Find best matching pattern
    best_match = None
    best_score = 0.0
    for p in patterns:
        score = _similar(title, p["canonical"])
        if score > best_score:
            best_score = score
            best_match = p

    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if best_match and best_score >= SIMILARITY_THRESHOLD:
        if record:
            best_match["occurrences"].append({"title": title, "ts": now})
            _save(data)
        count = len(best_match["occurrences"])
        return {
            "recurring": True,
            "count": count,
            "flag_automation": count >= FLAG_AT,
            "matched_pattern": best_match["canonical"],
        }
    else:
        if record:
            new_pattern = {
                "canonical": title,
                "occurrences": [{"title": title, "ts": now}],
            }
            patterns.append(new_pattern)
            data["patterns"] = patterns
            _save(data)
        return {
            "recurring": False,
            "count": 1,
            "flag_automation": False,
            "matched_pattern": None,
        }
