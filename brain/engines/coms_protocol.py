"""
COMS Protocol — structured agent-to-agent messaging over the chat API.

Messages carry a machine-readable envelope in the first line of text:
  [COMS:v1 {"thread_id":"...","to":["khaan"],...}]
  Human-readable message body here.

This module provides format/parse/filter functions used by both
coms_watch.py (Kha'an's watcher) and hook.py (Jeff's session hooks).
"""

import json
import re
import time
from pathlib import Path

BRAIN = Path.home() / ".claude" / "brain"
COMS_STATE_FILE = BRAIN / "coms-state.json"

ENVELOPE_RE = re.compile(r'^\[COMS:v1\s+(\{.*?\})\]\s*\n?', re.DOTALL)

TERMINAL_STATUSES = {"resolved", "done", "closed", "failed", "escalated"}
DEFAULT_MAX_TURNS = 8


# ─── State persistence ────────────────────────────────────────────────────────

def load_coms_state() -> dict:
    try:
        if COMS_STATE_FILE.exists():
            return json.loads(COMS_STATE_FILE.read_text())
    except Exception:
        pass
    return {"last_seen_id": None, "processed_msg_ids": [], "open_threads": {}}


def save_coms_state(state: dict):
    if len(state.get("processed_msg_ids", [])) > 500:
        state["processed_msg_ids"] = state["processed_msg_ids"][-500:]
    import tempfile, os
    fd, tmp = tempfile.mkstemp(dir=BRAIN)
    os.write(fd, json.dumps(state, indent=2).encode())
    os.close(fd)
    os.replace(tmp, COMS_STATE_FILE)


def mark_processed(msg_id: str):
    state = load_coms_state()
    if msg_id not in state["processed_msg_ids"]:
        state["processed_msg_ids"].append(msg_id)
    save_coms_state(state)


def update_cursor(msg_id: str):
    state = load_coms_state()
    state["last_seen_id"] = msg_id
    save_coms_state(state)


# ─── Thread ID generation ─────────────────────────────────────────────────────

def make_thread_id(topic: str) -> str:
    date = time.strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-z0-9]+', '-', topic.lower().strip())[:40].strip('-')
    return f"coms-{date}-{slug}"


# ─── Envelope format / parse ──────────────────────────────────────────────────

def format_coms_message(
    text, to, kind="request", thread_id=None,
    requires_response=True, status="open", waiting_on=None,
    turn=1, max_turns=DEFAULT_MAX_TURNS, reply_to=None, from_agent=None,
):
    if thread_id is None:
        thread_id = make_thread_id(text[:40])
    meta = {
        "schema": "coms.v1",
        "thread_id": thread_id,
        "to": to,
        "kind": kind,
        "requires_response": requires_response,
        "status": status,
        "waiting_on": waiting_on or (to[0] if to else "none"),
        "turn": turn,
        "max_turns": max_turns,
    }
    if reply_to:
        meta["reply_to"] = reply_to
    if from_agent:
        meta["from"] = from_agent
    return f"[COMS:v1 {json.dumps(meta)}]\n{text}"


def parse_coms_meta(text):
    """Parse COMS envelope. Returns (meta_dict, clean_text) or (None, original_text)."""
    m = ENVELOPE_RE.match(text or "")
    if not m:
        return None, text or ""
    try:
        meta = json.loads(m.group(1))
        return meta, text[m.end():]
    except (json.JSONDecodeError, KeyError):
        return None, text or ""


# ─── Filter: should this message wake an agent? ───────────────────────────────

def should_handle(me, msg, state=None):
    """Determine if agent `me` should respond to this chat message."""
    if msg.get("role") == me:
        return False

    meta, _ = parse_coms_meta(msg.get("text", ""))
    if meta is None:
        return False

    if me not in meta.get("to", []):
        return False

    if not meta.get("requires_response", False):
        return False

    if meta.get("status") in TERMINAL_STATUSES:
        return False

    waiting = meta.get("waiting_on")
    if waiting and waiting != me and waiting != "none":
        return False

    turn = meta.get("turn", 0)
    max_turns = meta.get("max_turns", DEFAULT_MAX_TURNS)
    if turn >= max_turns:
        return False

    msg_id = msg.get("id", "")
    if state is None:
        state = load_coms_state()
    if msg_id in state.get("processed_msg_ids", []):
        return False

    return True


# ─── Build COMS prompt for claude -p ──────────────────────────────────────────

def build_coms_prompt(me, msg, thread_history=None):
    """Build a prompt for claude -p to handle a COMS message."""
    meta, clean_text = parse_coms_meta(msg.get("text", ""))
    if meta is None:
        return ""

    thread_id = meta.get("thread_id", "unknown")
    turn = meta.get("turn", 1)
    max_turns = meta.get("max_turns", DEFAULT_MAX_TURNS)
    from_agent = msg.get("role", "unknown")
    status = meta.get("status", "open")

    history_text = ""
    if thread_history:
        for h in thread_history[-5:]:
            _, h_clean = parse_coms_meta(h.get("text", ""))
            history_text += f"  [{h.get('role', '?')} @ {h.get('ts', '?')}]: {h_clean.strip()[:200]}\n"

    return f"""You have a COMS message from {from_agent}.

Thread: {thread_id}
Status: {status}
Turn: {turn}/{max_turns}
Waiting on: {me}

{f"Thread history:\n{history_text}" if history_text else ""}
New message from {from_agent}:
{clean_text.strip()}

Instructions:
- Investigate or act on the request using available tools.
- Post exactly ONE COMS reply using POST /api/chat with role={me}.
- Your reply MUST include the [COMS:v1 ...] envelope with updated metadata.
- If you resolved the issue: set status=resolved, requires_response=false, waiting_on=none.
- If {from_agent} must act next: set waiting_on={from_agent}, status=input_required.
- Increment turn to {turn + 1}.
- Keep thread_id={thread_id}.
- Do NOT reply to ack/done/status-only messages.
- If blocked or unsafe, set status=escalated, waiting_on=justs.
"""


def build_queue_item(me, msg, thread_history=None):
    meta, _ = parse_coms_meta(msg.get("text", ""))
    return {
        "source": "coms",
        "priority": "high",
        "msg_id": msg.get("id", ""),
        "thread_id": meta.get("thread_id", "") if meta else "",
        "from": msg.get("role", ""),
        "prompt": build_coms_prompt(me, msg, thread_history),
    }


# ─── Format pending COMS for hook context injection ──────────────────────────

def format_pending_for_context(me, messages):
    """Format actionable COMS messages as markdown for additionalContext."""
    state = load_coms_state()
    pending = [m for m in messages if should_handle(me, m, state)]
    if not pending:
        return None

    lines = ["## COMS pending for you\n"]
    for msg in pending:
        meta, clean = parse_coms_meta(msg.get("text", ""))
        if not meta:
            continue
        lines.append(f"**Thread:** {meta.get('thread_id', '?')}")
        lines.append(f"**From:** {msg.get('role', '?')} | **Status:** {meta.get('status', '?')} | **Turn:** {meta.get('turn', '?')}/{meta.get('max_turns', 8)}")
        lines.append(f"**Message:** {clean.strip()[:300]}")
        lines.append("")
        lines.append("Handle this COMS item. Reply via POST /api/chat with your role and a [COMS:v1 ...] envelope.")
        lines.append("")

    return "\n".join(lines)
