import os, sys, re, json, time, calendar
from pathlib import Path

BRAIN = Path.home() / ".claude" / "brain"
BRAIN_PATH = str(BRAIN)
BRAIN_REAL = os.path.realpath(str(BRAIN))

BYPASSABLE = {"use-bash-block", "engine-security-block", "cycle-security-block", "permissions-block", "script-content-block"}

# R260: Kha'an is read-only on WhatsApp. All send tools blocked at the hook layer.
# Mechanical enforcement — the model cannot reason around it.
# To re-enable sends, edit this set directly (no bypass mechanism).
WA_SEND_TOOLS = {
    "mcp__claude_ai_WhatsApp__send_whatsapp",
    "mcp__claude_ai_Brain__send_whatsapp",
}
# Slack is read-only. All send/write tools blocked at the hook layer.
# Mechanical enforcement — the model cannot reason around it.
SLACK_SEND_TOOLS = {
    "mcp__claude_ai_Slack__slack_send_message",
    "mcp__claude_ai_Slack__slack_send_message_draft",
    "mcp__claude_ai_Slack__slack_schedule_message",
    "mcp__claude_ai_Slack__slack_create_canvas",
    "mcp__claude_ai_Slack__slack_update_canvas",
}
CYCLE_STATE_FILES = {"state.json", "brain_cycle.py", "cycle_phases.py"}
DOCKER_RE = re.compile(r"docker\s+compose\s+(up|down|restart)(\s*$|\s*[;&|])")
WRITE_CMD_RE = re.compile(r"(?:(?<!&)>(?![&=])|>>|tee\s+|open\s*\(|\.rename\s*\(|\.replace\s*\(|\.link\s*\(|\.unlink\s*\(|(?:cp|mv|dd|install|rsync|scp|patch|sed\s+-i|perl\s+-\S*[ip])\s+|shutil\.\w+|\.write_text\s*\(|\.write_bytes\s*\(|fs\.writeFile)")
CHMOD_CHOWN_RE = re.compile(r"(?:sudo\s+)?(?:chmod|chown)\s+.*brain/")

# Rule 9: script-content-block
PYTHON_SCRIPT_RE = re.compile(
    r"python3\s+(?:-[A-Za-z]\s+)*"
    r"(~?/[^\s;|&]+\.py|\./[^\s;|&]+\.py)"
)
DYNAMIC_EXEC_RE = re.compile(
    r"(?:eval\s*\(|exec\s*\(|__import__\s*\(|"
    r"importlib\.|base64\.b64decode\s*\(|"
    r"subprocess\.(?:run|call|Popen|check_call|check_output)\s*\(|"
    r"os\.system\s*\(|os\.popen\s*\()"
)
BRAIN_TARGET_PATTERNS = [
    re.compile(r"engines/[\w/]+\.py"),
    re.compile(r"binaries/[\w-]+\.bin"),
    re.compile(r"(?:state\.json|brain_cycle\.py|cycle_phases\.py)"),
    re.compile(r"settings\.json|settings\.local\.json"),
    re.compile(r"\.claude/brain"),
    re.compile(r"\.bypass\.secret"),
]
BRAIN_ENGINE_DIR = str(BRAIN / "engines")
BRAIN_ENGINE_REAL = os.path.realpath(BRAIN_ENGINE_DIR)

# Rule 11: bypass-grant-block — prevent self-granting gate bypasses
BYPASS_GRANT_RE = re.compile(
    r"bypass_expiry|write_state|read_state|_shared|flip_bypass"
)


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


def _normalize_script(text):
    """Strip comments, docstrings, join continuation lines, collapse whitespace."""
    lines = text.splitlines()

    # Pass 1: Strip triple-quoted strings
    cleaned = []
    in_triple = None
    for line in lines:
        if in_triple:
            end_pos = line.find(in_triple)
            if end_pos != -1:
                line = line[end_pos + 3:]
                in_triple = None
            else:
                continue
        result = []
        i = 0
        while i < len(line):
            tri = line[i:i+3]
            if tri == '\"\"\"' or tri == "\'\'\'":
                marker = tri
                close = line.find(marker, i + 3)
                if close != -1:
                    i = close + 3
                else:
                    in_triple = marker
                    break
            else:
                result.append(line[i])
                i += 1
        cleaned.append("".join(result))

    # Pass 2: Strip # comments
    decommented = []
    for line in cleaned:
        in_str = None
        for j, ch in enumerate(line):
            if ch in ('"', "'") and not in_str:
                in_str = ch
            elif ch == in_str:
                in_str = None
            elif ch == '#' and not in_str:
                line = line[:j]
                break
        decommented.append(line)

    # Pass 3: Join backslash-continued lines
    joined = []
    buf = ""
    for line in decommented:
        stripped = line.rstrip()
        if stripped.endswith("\\"):
            buf += stripped[:-1] + " "
        else:
            buf += stripped
            joined.append(buf)
            buf = ""
    if buf:
        joined.append(buf)

    # Pass 4: Collapse whitespace
    text = " ".join(joined)
    return re.sub(r"\s+", " ", text)


def _log_script_scan(script_path, reason, repo_root):
    """Append a JSONL entry to the security audit log."""
    try:
        log_path = repo_root / "logger" / "handler" / "security-blocks.jsonl"
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "gate": "script-content-block",
            "script": script_path,
            "reason": reason,
        }
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _scan_script_content(script_path, repo_root):
    """Read a script, normalize it, scan for forbidden patterns.

    Returns True if forbidden patterns detected (should block).
    Returns False if file unreadable or clean.
    """
    resolved = os.path.expanduser(script_path)
    resolved = os.path.realpath(resolved)

    # Exempt brain's own engine scripts
    if resolved.startswith(BRAIN_ENGINE_REAL) or resolved.startswith(BRAIN_ENGINE_DIR):
        return False

    try:
        with open(resolved, "r", errors="replace") as f:
            raw = f.read(256_000)
    except (OSError, IOError):
        _log_script_scan(script_path, "unreadable", repo_root)
        return False

    normalized = _normalize_script(raw)

    # Tier 1: write pattern + brain target path
    has_write = bool(WRITE_CMD_RE.search(normalized))
    has_brain_target = any(p.search(normalized) for p in BRAIN_TARGET_PATTERNS)

    if has_write and has_brain_target:
        _log_script_scan(script_path, "tier1_write_to_brain", repo_root)
        return True

    # Tier 2: dynamic execution + brain target path
    has_dynamic = bool(DYNAMIC_EXEC_RE.search(normalized))
    if has_dynamic and has_brain_target:
        _log_script_scan(script_path, "tier2_dynamic_exec_with_brain_target", repo_root)
        return True

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

    # Rule 8: whatsapp-readonly — R260 mechanical enforcement
    # ALL WhatsApp send tools are blocked regardless of recipient.
    # Kha'an may read incoming messages but cannot send any.
    if tool_name in WA_SEND_TOOLS:
        gates.append("whatsapp-readonly")

    # Rule 10: slack-readonly — mechanical enforcement
    # ALL Slack send/write tools are blocked. Kha'an may read only.
    if tool_name in SLACK_SEND_TOOLS:
        gates.append("slack-readonly")

    # Rule 9: script-content-block — scan python script contents for brain writes
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        m = PYTHON_SCRIPT_RE.search(cmd)
        if m:
            script_path = m.group(1)
            if _scan_script_content(script_path, repo_root):
                if not _is_bypassed("script-content-block", repo_root):
                    gates.append("script-content-block")

    # Rule 11: bypass-grant-block — prevent self-granting gate bypasses
    # NON-BYPASSABLE. The only legitimate bypass path is flip_bypass.consume()
    # which requires HMAC from .bypass.secret (external-only, Justs controls).
    if tool_name == "Bash":
        cmd = tool_input.get("command", "")
        if re.search(r"python3\s+.*-c\s+", cmd) and BYPASS_GRANT_RE.search(cmd):
            gates.append("bypass-grant-block")

    return gates
