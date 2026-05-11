import os, json, hashlib, subprocess, tempfile
from pathlib import Path

BRAIN = Path.home() / ".claude" / "brain"


def read_bin(name):
    return int((BRAIN / "binaries" / f"{name}.bin").read_text().strip())


def write_bin(name, val):
    p = BRAIN / "binaries" / f"{name}.bin"
    fd, tmp = tempfile.mkstemp(dir=p.parent)
    os.write(fd, str(val).encode())
    os.close(fd)
    os.rename(tmp, p)


def read_state():
    return json.loads((BRAIN / "state.json").read_text())


def write_state(data):
    p = BRAIN / "state.json"
    fd, tmp = tempfile.mkstemp(dir=p.parent)
    os.write(fd, json.dumps(data, indent=2).encode())
    os.close(fd)
    os.rename(tmp, p)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def cli_invoke(system_prompt, user_prompt, timeout=120):
    # --bare was dropped in CLI 2.1.x: it now also skips OAuth credential
    # loading, breaking auth. Recursion is prevented by BRAIN_SKIP_HOOKS=1
    # which hook.py checks before any engine import.
    env = {**os.environ, "BRAIN_SKIP_HOOKS": "1"}
    r = subprocess.run(
        ["claude", "-p", "--system-prompt", system_prompt,
         "--output-format", "stream-json", "--verbose"],
        input=user_prompt, capture_output=True, text=True,
        timeout=timeout, env=env
    )
    if r.returncode != 0:
        raise RuntimeError(f"claude -p exited {r.returncode}: {r.stderr[:500]}")
    tool_uses = []
    result_text = None
    for line in r.stdout.strip().splitlines():
        if not line.strip():
            continue
        evt = json.loads(line)
        if evt.get("type") == "assistant":
            for block in evt.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_uses.append(block)
        elif evt.get("type") == "result":
            result_text = evt.get("result", "")
    if result_text is None:
        raise RuntimeError("no result event in stream")
    # strip markdown code fences if the model wrapped the JSON
    s = result_text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s[3:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    if not s:
        raise RuntimeError("empty result text from claude -p")
    # tolerate prose around the JSON: find first { or [ and parse from there;
    # raw_decode returns the first valid value and ignores trailing content.
    candidates = [i for i in (s.find("{"), s.find("[")) if i != -1]
    if not candidates:
        raise RuntimeError(f"no JSON object in result: {s[:200]}")
    start = min(candidates)
    payload, _ = json.JSONDecoder().raw_decode(s[start:])
    return {"result": payload, "tool_uses": tool_uses}
