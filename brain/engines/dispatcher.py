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
    "decision-hypothesis-1",
    "decision-hypothesis-2",
    "decision-hypothesis-3",
    "decision-hypothesis-4",
    "decision-hypothesis-5",
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

    # When brain cycle is actively running, all tools must pass through —
    # the cycle itself needs Read, Write, Edit, Agent, etc. to do its work.
    cycle_running = False
    try:
        cycle_running = read_binary(repo_root, "learning-cycle-running") == 1
    except Exception:
        pass

    raised = []
    for bname in spec["blocking_binaries"]:
        try:
            val = read_binary(repo_root, bname)
        except Exception:
            continue
        if val == 1:
            if bname in ("learning-cycle-overdue", "learning-cycle-running",
                         "consolidation-pending", "promote-scan-stale"):
                # Always let the brain-cycle skill / bash invocation through
                tool_name = payload.get("tool_name", "")
                if tool_name == "Skill":
                    skill = payload.get("tool_input", {}).get("skill", "")
                    if skill == "brain-cycle":
                        continue
                elif tool_name == "Bash":
                    cmd = payload.get("tool_input", {}).get("command", "")
                    if re.match(r"python3\s+(-m\s+engines\.brain_cycle|.*engines/brain_cycle\.py|-c\s+.*brain_cycle)", cmd):
                        continue
                # When cycle is running, let ALL tools through (cycle uses them internally)
                if cycle_running:
                    continue
            if bname.startswith("decision-hypothesis-"):
                tool_name = payload.get("tool_name", "")
                if tool_name == "Skill":
                    skill = payload.get("tool_input", {}).get("skill", "")
                    if skill in ("decision-engine", "brain-cycle"):
                        continue
                elif tool_name == "Bash":
                    cmd = payload.get("tool_input", {}).get("command", "")
                    if re.match(r"python3\s+.*engines[./](decision|brain_cycle)", cmd):
                        continue
            raised.append(bname)
    raised.extend(per_call_gates)

    blocks = bool(raised) and spec["behaviour"].startswith("block")
    return 2 if blocks else 0
