"""
COMS Watcher — lightweight polling daemon for agent-to-agent messaging.

Polls GET /api/chat?after_id=<cursor> every few seconds.
Filters messages addressed to this brain.
Writes actionable items to queue/inbox.jsonl for always_on.py to drain.

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
    load_coms_state, save_coms_state, mark_processed,
    update_cursor, should_handle, build_queue_item,
    parse_coms_meta,
)

BRAIN = Path.home() / ".claude" / "brain"
QUEUE_FILE = BRAIN / "queue" / "inbox.jsonl"
LOG_DIR = BRAIN / "logger" / "coms-watch"
GATE_FILE = BRAIN / "binaries" / "always-on.bin"
THALAMUS = BRAIN / "thalamus.json"

COMS_API = os.environ.get("COMS_API", "http://localhost:3001")
POLL_INTERVAL = int(os.environ.get("COMS_POLL_INTERVAL", "8"))

# Read agent name from thalamus.json
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


def gate_on():
    try:
        return GATE_FILE.read_text().strip() == "1"
    except Exception:
        return False


def fetch_messages(after_id=None, since=None):
    """Fetch chat messages from the COMS API."""
    url = f"{COMS_API}/api/chat"
    params = []
    if after_id:
        params.append(f"after_id={after_id}")
    elif since:
        params.append(f"since={urllib.request.quote(since)}")
    if params:
        url += "?" + "&".join(params)

    req = urllib.request.Request(url, method="GET")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        return data.get("messages", [])
    except Exception as e:
        log_event("fetch_error", {"error": str(e)[:200]})
        return []


def fetch_thread_history(thread_id, messages):
    """Get recent messages in a thread from the available messages."""
    history = []
    for m in messages:
        meta, _ = parse_coms_meta(m.get("text", ""))
        if meta and meta.get("thread_id") == thread_id:
            history.append(m)
    return history[-5:]


def enqueue(item):
    """Append a queue item to inbox.jsonl."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "a") as f:
        f.write(json.dumps(item) + "\n")


def poll_cycle(agent_name):
    """One poll cycle: fetch, filter, enqueue."""
    state = load_coms_state()
    cursor = state.get("last_seen_id")

    messages = fetch_messages(after_id=cursor)
    if not messages:
        return 0

    enqueued = 0
    all_messages_for_context = fetch_messages()  # full history for thread context

    for msg in messages:
        msg_id = msg.get("id", "")

        # Advance cursor
        if msg_id:
            state["last_seen_id"] = msg_id

        # Check if actionable
        if not should_handle(agent_name, msg, state):
            continue

        # Get thread history for context
        meta, _ = parse_coms_meta(msg.get("text", ""))
        thread_id = meta.get("thread_id", "") if meta else ""
        thread_history = fetch_thread_history(thread_id, all_messages_for_context) if thread_id else []

        # Build and enqueue
        item = build_queue_item(agent_name, msg, thread_history)
        enqueue(item)

        # Mark as processed to prevent re-enqueue
        state["processed_msg_ids"].append(msg_id)

        log_event("enqueued", {
            "msg_id": msg_id,
            "from": msg.get("role", "?"),
            "thread_id": thread_id,
        })
        enqueued += 1

    save_coms_state(state)
    return enqueued


def main():
    agent_name = get_agent_name()
    log_event("watcher_start", {"agent": agent_name, "poll_interval": POLL_INTERVAL})
    print(f"COMS watcher started for {agent_name}, polling every {POLL_INTERVAL}s", flush=True)

    while True:
        try:
            if not gate_on():
                time.sleep(POLL_INTERVAL)
                continue

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
