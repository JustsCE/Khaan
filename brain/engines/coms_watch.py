"""
COMS Watcher — lightweight polling daemon for agent-to-agent messaging.

Polls GET /api/chat?after_id=<cursor> every few seconds.
Filters messages addressed to this brain.
Writes actionable items to queue/inbox.jsonl for always_on.py to drain.
Sets coms-pending.bin=1 to enforce response (hard gate in dispatcher).
Clears coms-pending.bin=0 when the agent has responded.

Run as systemd service: brain-coms-watch.service
"""

import os
import sys
import json
import time
import traceback
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines.coms_protocol import (
    load_coms_state, save_coms_state,
    should_handle, build_queue_item,
    parse_coms_meta,
)

BRAIN = Path.home() / ".claude" / "brain"
QUEUE_FILE = BRAIN / "queue" / "inbox.jsonl"
LOG_DIR = BRAIN / "logger" / "coms-watch"
COMS_PENDING_BIN = BRAIN / "binaries" / "coms-pending.bin"
THALAMUS = BRAIN / "thalamus.json"

COMS_API = os.environ.get("COMS_API", "http://localhost:3001")
POLL_INTERVAL = int(os.environ.get("COMS_POLL_INTERVAL", "90"))


def get_agent_name():
    try:
        return json.loads(THALAMUS.read_text()).get("agent_name", "khaan").lower()
    except Exception:
        return "khaan"


def log_event(event, data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = LOG_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": event, **data
        }) + "\n")



def set_coms_pending(val):
    try:
        COMS_PENDING_BIN.write_text(str(val))
    except Exception:
        pass


def fetch_messages(after_id=None):
    url = f"{COMS_API}/api/chat"
    if after_id:
        url += f"?after_id={after_id}"
    req = urllib.request.Request(url, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return data.get("messages", [])
    except Exception as e:
        log_event("fetch_error", {"error": str(e)[:200]})
        return []


def fetch_thread_history(thread_id, all_messages):
    history = []
    for m in all_messages:
        meta, _ = parse_coms_meta(m.get("text", ""))
        if meta and meta.get("thread_id") == thread_id:
            history.append(m)
    return history[-5:]


def enqueue(item):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "a") as f:
        f.write(json.dumps(item) + "\n")


def check_agent_responded(agent_name, state):
    """Check if the agent has posted a reply since the last pending message.
    If so, clear the coms-pending gate."""
    try:
        cursor = state.get("last_seen_id")
        if not cursor:
            return
        messages = fetch_messages(after_id=cursor)
        for msg in messages:
            if msg.get("role") == agent_name:
                # Agent posted a reply — clear the gate
                set_coms_pending(0)
                log_event("coms_pending_cleared", {"reason": "agent_responded", "msg_id": msg.get("id")})
                # Update cursor past this message
                state["last_seen_id"] = msg["id"]
                save_coms_state(state)
                return
    except Exception:
        pass


def poll_cycle(agent_name):
    state = load_coms_state()
    cursor = state.get("last_seen_id")

    # If coms-pending is already set, check if the agent has responded
    try:
        if COMS_PENDING_BIN.exists() and COMS_PENDING_BIN.read_text().strip() == "1":
            check_agent_responded(agent_name, state)
            state = load_coms_state()  # reload after possible update
            cursor = state.get("last_seen_id")
    except Exception:
        pass

    messages = fetch_messages(after_id=cursor)
    if not messages:
        return 0

    enqueued = 0
    all_messages = fetch_messages()  # full history for thread context

    for msg in messages:
        msg_id = msg.get("id", "")
        if msg_id:
            state["last_seen_id"] = msg_id

        if not should_handle(agent_name, msg, state):
            continue

        meta, _ = parse_coms_meta(msg.get("text", ""))
        thread_id = meta.get("thread_id", "") if meta else ""
        thread_history = fetch_thread_history(thread_id, all_messages) if thread_id else []

        item = build_queue_item(agent_name, msg, thread_history)
        enqueue(item)
        state["processed_msg_ids"].append(msg_id)

        # Set the hard gate — agent must respond before doing other work
        set_coms_pending(1)

        log_event("enqueued", {
            "msg_id": msg_id,
            "from": msg.get("role", "?"),
            "thread_id": thread_id,
            "coms_pending_set": True,
        })
        enqueued += 1

    save_coms_state(state)
    return enqueued


def main():
    agent_name = get_agent_name()

    # Ensure coms-pending.bin exists
    if not COMS_PENDING_BIN.exists():
        COMS_PENDING_BIN.write_text("0")

    log_event("watcher_start", {"agent": agent_name, "poll_interval": POLL_INTERVAL})
    print(f"COMS watcher started for {agent_name}, polling every {POLL_INTERVAL}s", flush=True)

    while True:
        try:

            n = poll_cycle(agent_name)
            if n > 0:
                log_event("poll_result", {"enqueued": n})

        except KeyboardInterrupt:
            log_event("watcher_stop", {"reason": "keyboard_interrupt"})
            return
        except Exception as e:
            log_event("poll_error", {"error": str(e)[:500], "trace": traceback.format_exc()[:1000]})

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
