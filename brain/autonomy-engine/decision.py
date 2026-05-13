"""
decision.py — Autonomy Engine v1.2
Routes tasks to ACT / PROPOSE / ASK / DEFER.
"""

FINANCIAL_KEYWORDS = {"payment", "invoice", "contract", "billing", "price", "cost", "budget", "revenue", "salary", "wire", "transfer"}
IRREVERSIBLE_KEYWORDS = {"delete", "drop", "remove", "destroy", "wipe", "purge", "terminate", "shutdown"}
REFUSAL_KEYWORDS = {"skip", "ignore", "refuse", "decline"}

VERDICTS = ("ACT", "PROPOSE", "ASK", "DEFER")


def route(task: dict, mode: str = "solo") -> dict:
    """
    Route a single task to a verdict.

    Returns:
        {"verdict": str, "reason": str}
    """
    title = (task.get("title") or "").lower()
    tags = [t.upper() for t in (task.get("tags") or [])]
    assignee = (task.get("people") or {}).get("assignedTo") or ""

    # Wrong assignee — defer immediately
    if assignee and assignee not in ("Brain", "Kha'an", "brain"):
        return {"verdict": "DEFER", "reason": f"Assigned to {assignee}, not Brain"}

    # Financial / contract — block before EXECUTE check for safety
    if any(kw in title for kw in FINANCIAL_KEYWORDS):
        return {"verdict": "DEFER", "reason": "Financial/contract keyword detected — requires human review"}

    # Irreversible actions
    if any(kw in title for kw in IRREVERSIBLE_KEYWORDS):
        return {"verdict": "DEFER", "reason": "Irreversible action detected — requires human review"}

    # VERIFY / NEW — Justs-only decisions
    if "VERIFY" in tags or "NEW" in tags:
        return {"verdict": "DEFER", "reason": "VERIFY/NEW tags require Justs review"}

    # PROJECT — project pipeline handles
    if "PROJECT" in tags:
        return {"verdict": "DEFER", "reason": "PROJECT tag — handled by project pipeline"}

    # EXECUTE — Justs promoted it, trust the promotion
    if "EXECUTE" in tags:
        return {"verdict": "ACT", "reason": "EXECUTE tag — Justs promoted, no second-guessing"}

    # PLAN — propose the plan
    if "PLAN" in tags:
        return {"verdict": "PROPOSE", "reason": "PLAN tag — propose execution approach"}

    # PENDING — already decided, act
    if "PENDING" in tags:
        return {"verdict": "ACT", "reason": "PENDING tag — queued for execution"}

    # Default: act
    return {"verdict": "ACT", "reason": "No blocking conditions — proceed"}
