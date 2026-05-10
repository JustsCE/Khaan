import os, sys, json, time
import calendar, re
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines import flip_tool_guards

BRAIN = Path.home() / ".claude" / "brain"

BLOCKING_BINARIES = [
    "learning-cycle-overdue",
    "learning-cycle-running",
    "consolidation-pending",
    "promote-scan-stale",
]

ROUTING = {
    "SessionStart":     {"behaviour": "passthrough", "blocking_binaries": []},
    "UserPromptSubmit": {"behaviour": "passthrough", "blocking_binaries": []},
    "PreToolUse":       {"behaviour": "block",       "blocking_binaries": BLOCKING_BINARIES},
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
            exp_ts = calendar.timegm(time.strptime(expiry_iso[:19], "%Y-%m-%dT%H:%M:%S"))
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
            if bname == "learning-cycle-overdue":
                tool_name = payload.get("tool_name", "")
                if tool_name == "Skill":
                    skill = payload.get("tool_input", {}).get("skill", "")
                    if skill == "brain-cycle":
                        continue
                elif tool_name == "Bash":
                    cmd = payload.get("tool_input", {}).get("command", "")
                    if re.match(r"python3\s+(-m\s+engines\.brain_cycle|.*engines/brain_cycle\.py)", cmd):
                        continue
            raised.append(bname)
    raised.extend(per_call_gates)

    blocks = bool(raised) and spec["behaviour"].startswith("block")
    return 2 if blocks else 0
