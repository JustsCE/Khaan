import os, sys, json, time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines import flip_tool_guards

BRAIN = Path.home() / ".claude" / "brain"

ALL_BINARIES = [
    "decision-hypothesis-1", "decision-hypothesis-2", "decision-hypothesis-3",
    "decision-hypothesis-4", "decision-hypothesis-5",
    "decision-source-missing", "decision-failed", "decision-timeout",
    "recall-stale", "recall-dispatch-failed", "recall-failed", "recall-timeout",
    "identity-boot-failed", "identity-relay-failed", "identity-boot-timeout", "identity-relay-timeout",
    "learning-cycle-overdue", "learning-cycle-running", "learning-cycle-failed",
    "learning-cycle-timeout", "consolidation-pending", "promote-scan-stale", "cycle-empty"
]

ROUTING = {
    "SessionStart":     {"behaviour": "passthrough", "blocking_binaries": []},
    "UserPromptSubmit": {"behaviour": "passthrough", "blocking_binaries": []},
    "PreToolUse":       {"behaviour": "block",       "blocking_binaries": ALL_BINARIES},
    "PostToolUse":      {"behaviour": "passthrough", "blocking_binaries": []},
    "SubagentStop":     {"behaviour": "passthrough", "blocking_binaries": []},
    "Stop":             {"behaviour": "passthrough", "blocking_binaries": []},
}


def read_binary(repo_root, name):
    return int((repo_root / "binaries" / f"{name}.bin").read_text().strip())


def restore_expired(repo_root):
    st_path = repo_root / "state.json"
    if not st_path.exists():
        return
    st = json.loads(st_path.read_text())
    bypass = st.get("bypass_expiry", {})
    now = time.time()
    changed = False
    for guard, expiry_iso in list(bypass.items()):
        try:
            exp_ts = time.mktime(time.strptime(expiry_iso[:19], "%Y-%m-%dT%H:%M:%S"))
            if now > exp_ts:
                del bypass[guard]
                changed = True
        except (ValueError, TypeError):
            del bypass[guard]
            changed = True
    if changed:
        st["bypass_expiry"] = bypass
        import tempfile
        fd, tmp = tempfile.mkstemp(dir=repo_root)
        os.write(fd, json.dumps(st, indent=2).encode())
        os.close(fd)
        os.rename(tmp, st_path)


def dispatch(event, payload, repo_root):
    restore_expired(repo_root)

    per_call_gates = []
    if event == "PreToolUse":
        per_call_gates = flip_tool_guards.evaluate(payload, repo_root)

    spec = ROUTING.get(event)
    if spec is None:
        return 0

    raised = []
    for bname in spec["blocking_binaries"]:
        if read_binary(repo_root, bname) == 1:
            # learning-cycle-overdue: allow brain_cycle commands through
            if bname == "learning-cycle-overdue":
                tool_name = payload.get("tool_name", "")
                cmd = payload.get("tool_input", {}).get("command", "")
                if tool_name == "Bash" and "brain_cycle" in cmd:
                    continue
            raised.append(bname)
    raised.extend(per_call_gates)

    blocks = bool(raised) and spec["behaviour"].startswith("block")
    return 2 if blocks else 0
