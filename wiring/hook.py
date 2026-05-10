import os, sys, json, time
from pathlib import Path

if os.environ.get("BRAIN_SKIP_HOOKS"):
    print("{}")
    sys.exit(0)

BRAIN = Path.home() / ".claude" / "brain"
sys.path.insert(0, str(BRAIN))

from engines._shared import read_bin, write_bin, read_state, write_state


def _safe_log(msg):
    try:
        p = BRAIN / "logger" / "handler" / "hook.errors.jsonl"
        with open(p, "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "error": msg}) + "\n")
    except Exception:
        pass


DECISION_BINS = [
    "decision-hypothesis-1", "decision-hypothesis-2", "decision-hypothesis-3",
    "decision-hypothesis-4", "decision-hypothesis-5",
    "decision-source-missing", "decision-failed", "decision-timeout"
]
RECALL_BINS = ["recall-stale", "recall-dispatch-failed", "recall-failed", "recall-timeout"]
IDENTITY_BINS = ["identity-boot-failed", "identity-relay-failed", "identity-boot-timeout", "identity-relay-timeout"]
LEARNING_BINS = [
    "learning-cycle-overdue", "learning-cycle-running", "learning-cycle-failed",
    "learning-cycle-timeout", "consolidation-pending", "promote-scan-stale", "cycle-empty"
]


def handle_session_start(payload):
    for b in DECISION_BINS + RECALL_BINS + IDENTITY_BINS + LEARNING_BINS:
        write_bin(b, 0)
    from engines.identity_engine.identity_boot import boot
    kernel = boot()
    if kernel:
        return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": kernel}}
    return {}


ANTI_LOCKOUT_BINS = [
    "decision-failed", "decision-timeout", "decision-source-missing",
    "recall-failed", "recall-timeout", "recall-stale", "recall-dispatch-failed",
    "identity-boot-failed", "identity-boot-timeout",
    "identity-relay-failed", "identity-relay-timeout",
    "cycle-empty", "learning-cycle-failed", "learning-cycle-timeout",
]


def handle_user_prompt_submit(payload):
    from engines.decision_engine.flip_decision_trigger import trigger
    from engines.decision import dispatch
    from engines.learning_engine.flip_cycle_overdue import check_overdue

    for b in ANTI_LOCKOUT_BINS:
        write_bin(b, 0)
    st = read_state()
    st["decision_consecutive_failures"] = 0
    st["message_counter"] = st.get("message_counter", 0) + 1
    write_state(st)

    check_overdue()

    user_message = payload.get("prompt") or payload.get("message") or payload.get("content", "")
    proceed = trigger()
    if proceed:
        # /decision-engine skill auto-invocation per handler.html § UserPromptSubmit step 3.
        # Skill descriptor: ~/.claude/skills/decision-engine.md
        # Orchestrator: engines/decision.py::dispatch (decision-engine.html line 288).
        dispatch(user_message)

    ctx = _compose_turn_context()
    if ctx:
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}
    return {}


def handle_pre_tool_use(payload):
    from engines.dispatcher import dispatch as rule_dispatch
    exit_code = rule_dispatch("PreToolUse", payload, BRAIN)
    if exit_code == 2:
        return {"decision": "block", "reason": "Blocked by rule engine"}
    return {}


def handle_stop(payload):
    try:
        p = BRAIN / "logger" / "handler" / "turn_complete.jsonl"
        user_prompt = ""
        tool_uses = []
        transcript_path = payload.get("transcript_path", "")
        if transcript_path:
            from pathlib import Path as _P
            tp = _P(transcript_path)
            if tp.exists():
                last_user = ""
                last_tools = []
                for line in tp.read_text(errors="replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        evt = json.loads(line)
                    except Exception:
                        continue
                    if evt.get("type") == "user":
                        msg = evt.get("message", {})
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            last_user = " ".join(b.get("text", "") for b in content if b.get("type") == "text")
                        else:
                            last_user = str(content)
                    elif evt.get("type") == "assistant":
                        msg = evt.get("message", {})
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            last_tools = [b.get("name", "") for b in content if b.get("type") == "tool_use"]
                user_prompt = last_user
                tool_uses = last_tools
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": payload.get("session_id", ""),
            "user_prompt": user_prompt[-2000:] if user_prompt else "",
            "final_response": (payload.get("last_assistant_message", "") or "")[-2000:],
            "tool_uses": tool_uses,
        }
        with open(p, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    return {}



def _compose_turn_context():
    nav = BRAIN / "navigation"
    parts = []
    for name in ["active-recall.json", "active-identity.json", "active-decision.json"]:
        p = nav / name
        if p.exists():
            try:
                data = json.loads(p.read_text())
                if name == "active-decision.json" and "hypotheses" in data:
                    parts.append("## Decision Hypotheses\n")
                    for h in data["hypotheses"]:
                        parts.append(f"### {h['id']}: {h['label']}\n")
                        parts.append(f"**Deliver:** {h.get('deliver', '')}\n\n")
                elif name == "active-recall.json" and "qualified_entries" in data:
                    parts.append("## Recall\n")
                    for e in data["qualified_entries"][:5]:
                        parts.append(f"- **{e.get('id', '')}**: {e.get('gist', '')}\n")
                    parts.append("\n")
                elif name == "active-identity.json":
                    sit = data.get("situational", "")
                    if sit:
                        parts.append("## Identity\n")
                        parts.append(f"{sit}\n\n")
            except Exception:
                pass
    return "".join(parts) if parts else None


def handle_post_tool_use(payload):
    return {}


def handle_subagent_stop(payload):
    # Decision, Brain Retro, Brain Learn, Brain Correct all run via cli_invoke
    # (a Bash subprocess), not Anthropic's native subagent — so SubagentStop
    # does not fire for them. Each engine does its schema verification inline
    # inside run(). Kept as a named no-op so DISPATCH stays valid; rewire here
    # if any engine transitions to a native subagent.
    return {}


DISPATCH = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PreToolUse": handle_pre_tool_use,
    "PostToolUse": handle_post_tool_use,
    "SubagentStop": handle_subagent_stop,
    "Stop": handle_stop,
}


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            payload = json.loads(raw)
    except Exception:
        pass

    handler = DISPATCH.get(event, lambda p: {})
    try:
        result = handler(payload)
        if result and result.get("decision") == "block":
            print(json.dumps(result))
            sys.exit(2)
        print(json.dumps(result or {}))
        sys.exit(0)
    except Exception as e:
        _safe_log(f"{event}: {e}")
        print("{}")
        sys.exit(0)


if __name__ == "__main__":
    main()
