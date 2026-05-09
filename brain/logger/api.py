import json, time
from pathlib import Path

LOGGER_BASE = Path.home() / ".claude" / "brain" / "logger"
LOGGER_DIR = LOGGER_BASE / "decision"


def write_decision_log(event_type, data):
    p = LOGGER_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps({"event": event_type, **data}) + "\n")


def write_recall_log(event_type, data):
    p = LOGGER_BASE / "recall" / f"{time.strftime('%Y-%m-%d')}.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps({"event": event_type, **data}) + "\n")


def write_identity_log(event_type, data):
    p = LOGGER_BASE / "identity" / f"{time.strftime('%Y-%m-%d')}.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps({"event": event_type, **data}) + "\n")


def write_learning_log(event_type, data):
    d = LOGGER_BASE / "learning"
    if event_type == "cycle_ledger":
        cycle_id = data.get("cycle_id", 0)
        p = d / f"cycle-{cycle_id:04d}.json"
        with open(p, "w") as f:
            f.write(json.dumps({"event": event_type, **data}, indent=2))
    p = d / "events.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps({"event": event_type, **data}) + "\n")
