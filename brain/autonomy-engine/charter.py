"""
charter.py — Autonomy Engine v1.2
Verifies task alignment against the 6 Brain Charter tenets.
"""

import json
from pathlib import Path

CHARTER_PATH = Path(__file__).parent / "charter.json"


def _load_charter() -> list:
    return json.loads(CHARTER_PATH.read_text())["tenets"]


def check(task: dict, mode: str = "solo") -> dict:
    """
    Check task against all 6 charter tenets.

    Returns:
        {
            "aligned": bool,        # False only if any tenet BLOCKs
            "blockers": list[str],  # tenet names that block
            "warnings": list[str],  # tenet names with warn-level hits
            "info": list[str],      # tenet names with info-level notes
        }
    """
    tenets = _load_charter()
    title = (task.get("title") or "").lower()
    description = (task.get("description") or "").lower()
    text = title + " " + description

    blockers = []
    warnings = []
    info_notes = []

    for t in tenets:
        gate = t["gate"]
        check_type = t["check"]
        name = t["name"]

        if check_type == "always":
            # Info-level: always note, never block
            info_notes.append(name)
            continue

        if check_type == "mode" and gate == "block":
            # Tenet 3: vericity_solo — block if vericity keyword present in non-solo mode
            kws = t.get("keywords", [])
            if any(kw in text for kw in kws):
                if mode != "solo":
                    blockers.append(name)
                else:
                    info_notes.append(name)  # Solo mode: vericity is fine
            continue

        if check_type == "keywords" and gate == "warn":
            # Tenet 6: automate_never_refuse — warn only, NEVER block
            kws = t.get("keywords", [])
            if any(kw in text for kw in kws):
                warnings.append(name)
            continue

    aligned = len(blockers) == 0
    return {
        "aligned": aligned,
        "blockers": blockers,
        "warnings": warnings,
        "info": info_notes,
    }
