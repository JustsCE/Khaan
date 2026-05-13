"""
integrate.py - Autonomy Engine v1.2
Full triage pipeline: charter check -> decision routing -> recurrence tracking.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import charter as _charter
import decision as _decision
import recurrence as _recurrence

# Tags that bypass the engine handled by other systems
_SKIP_TAGS = {"VERIFY", "PROJECT"}


def triage_tasks(tasks: list, mode: str = "solo", record_patterns: bool = True) -> dict:
    """
    Run full triage pipeline on a list of dashboard tasks.

    Args:
        tasks: list of task dicts from dashboard
        mode: "solo" (Brain alone) or "joint" (with Justs)
        record_patterns: False in tests to avoid polluting patterns.json

    Returns dict with keys ACT, PROPOSE, ASK, DEFER.
    Each entry: {task, verdict, reason, charter_result, recurrence_result}
    """
    result = {"ACT": [], "PROPOSE": [], "ASK": [], "DEFER": []}

    for task in tasks:
        tags = [t.upper() for t in (task.get("tags") or [])]

        # Pre-filter: skip tags handled by other systems
        if any(t in _SKIP_TAGS for t in tags):
            entry = {
                "task": task,
                "verdict": "DEFER",
                "reason": "Pre-filtered: VERIFY/PROJECT handled outside autonomy-engine",
                "charter_result": None,
                "recurrence_result": None,
            }
            result["DEFER"].append(entry)
            continue

        # Step 1: Charter check
        charter_result = _charter.check(task, mode=mode)
        if not charter_result["aligned"]:
            entry = {
                "task": task,
                "verdict": "DEFER",
                "reason": f"Charter block: {', '.join(charter_result['blockers'])}",
                "charter_result": charter_result,
                "recurrence_result": None,
            }
            result["DEFER"].append(entry)
            continue

        # Step 2: Decision routing
        decision_result = _decision.route(task, mode=mode)
        verdict = decision_result["verdict"]
        reason = decision_result["reason"]

        # Attach charter warnings if any
        if charter_result["warnings"]:
            reason += f" [charter warnings: {', '.join(charter_result['warnings'])}]"

        # Step 3: Recurrence tracking
        rec_result = _recurrence.check(task, record=record_patterns)
        if rec_result["flag_automation"]:
            reason += f" [recurring x{rec_result['count']}: consider automating]"

        entry = {
            "task": task,
            "verdict": verdict,
            "reason": reason,
            "charter_result": charter_result,
            "recurrence_result": rec_result,
        }
        result[verdict].append(entry)

    return result
