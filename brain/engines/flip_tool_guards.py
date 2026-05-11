import os, sys, re, json, time, calendar
from pathlib import Path

BRAIN = Path.home() / ".claude" / "brain"
BRAIN_PATH = str(BRAIN)
BRAIN_REAL = os.path.realpath(str(BRAIN))

BYPASSABLE = {"use-bash-block", "engine-security-block", "cycle-security-block", "permissions-block"}
CYCLE_STATE_FILES = {"state.json", "brain_cycle.py", "cycle_phases.py"}
DOCKER_RE = re.compile(r"docker\s+compose\s+(up|down|restart)(\s*$|\s*[;&|])")
WRITE_CMD_RE = re.compile(r"(?:(?<!&)>(?![&=])|>>|tee\s+|open\s*\(|os\.rename\s*\(|(?:cp|mv|dd|install|rsync|scp|patch|sed\s+-i|perl\s+-\S*[ip])\s+|shutil\.\w+|\.write_text\s*\(|\.write_bytes\s*\(|fs\.writeFile)")
CHMOD_CHOWN_RE = re.compile(r"(?:sudo\s+)?(?:chmod|chown)\s+.*brain/")


def _is_bypassed(guard_name, repo_root):
    if guard_name not in BYPASSABLE:
        return False
    st_path = repo_root / "state.json"
    if not st_path.exists():
        return False
    st = json.loads(st_path.read_text())
    bypass = st.get("bypass_expiry", {})
    expiry_iso = bypass.get(guard_name)
    if not expiry_iso:
        return False
    try:
        exp_ts = calendar.timegm(time.strptime(expiry_iso[:19], "%Y-%m-%dT%H:%M:%S"))
        return time.time() <= exp_ts
    except (ValueError, TypeError):
        return False


def evaluate(payload, repo_root):
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    gates = []

    # Rule 1: use-bash-block — Edit/Write targeting brain/
    if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        raw = tool_input.get("file_path", "")
        resolved = os.path.realpath(raw)
        if BRAIN_PATH in raw or BRAIN_PATH in resolved or BRAIN_REAL in resolved:
            if not _is_bypassed("use-bash-block", repo_root):
                gates.append("use-bash-block")

    # Rule 2: engine-security-block — Bash writing to engines/*.py
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").replace("\n", " ")
        if WRITE_CMD_RE.search(cmd) and re.search(r"engines/[\w/]+\.py", cmd):
            if not _is_bypassed("engine-security-block", repo_root):
                gates.append("engine-security-block")

    # Rule 2b: engine-security-block — Bash writing to binaries/*.bin
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").replace("\n", " ")
        if WRITE_CMD_RE.search(cmd) and re.search(r"binaries/[\w-]+\.bin", cmd):
            if not _is_bypassed("engine-security-block", repo_root):
                gates.append("engine-security-block")

    # Rule 3: cycle-security-block — Bash writes to cycle-state files outside CYCLE_RUNNING
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").replace("\n", " ")
        for csf in CYCLE_STATE_FILES:
            if csf in cmd and WRITE_CMD_RE.search(cmd):
                st_path = repo_root / "state.json"
                if st_path.exists():
                    st = json.loads(st_path.read_text())
                    if st.get("fsm") != "CYCLE_RUNNING":
                        if not _is_bypassed("cycle-security-block", repo_root):
                            gates.append("cycle-security-block")
                break

    # Rule 4: server-security-block — docker compose without service name
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if DOCKER_RE.search(cmd):
            gates.append("server-security-block")

    # Rule 5: permissions-block — chmod/chown on brain/
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if CHMOD_CHOWN_RE.search(cmd):
            if not _is_bypassed("permissions-block", repo_root):
                gates.append("permissions-block")

    # Rule 6: bypass-secret-block — .bypass.secret is never readable
    if tool_name == "Read":
        if ".bypass.secret" in tool_input.get("file_path", ""):
            gates.append("bypass-secret-block")
    if tool_name == "Bash":
        if ".bypass.secret" in tool_input.get("command", ""):
            gates.append("bypass-secret-block")

    # Rule 7: settings-security-block — protect settings.json from Bash writes
    if tool_name == "Bash":
        cmd = tool_input.get("command", "").replace("\n", " ")
        if ("settings.json" in cmd or "settings.local.json" in cmd) and WRITE_CMD_RE.search(cmd):
            gates.append("settings-security-block")

    return gates
