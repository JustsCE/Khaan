import os, sys, json, hmac, hashlib, time, tempfile
from pathlib import Path

BRAIN = Path.home() / ".claude" / "brain"
SECRET_PATH = Path.home() / ".claude" / ".bypass.secret"

# [DEVIATES FROM SPEC: rule-engine.html]
# Spec says "a short time window" but does not define duration.
# Spec says "HMAC secret" but does not define what the token signs.
# Spec says "one-shot" -- token is consumed and cannot be reused.
# The Lambda issue endpoint defines the actual token format;
# this code verifies HMAC(guard_name) as a placeholder until
# the endpoint's signing contract is documented.


def consume(token, guard_name, repo_root):
    if not SECRET_PATH.exists():
        return False
    secret = SECRET_PATH.read_text().strip()

    # [DEVIATES FROM SPEC: rule-engine.html]
    # HMAC input is guard_name only -- actual signing contract
    # is defined by the issue-bypass Lambda endpoint, not this file.
    expected = hmac.new(secret.encode(), guard_name.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(token, expected):
        return False

    st_path = repo_root / "state.json"
    st = json.loads(st_path.read_text())
    bypass = st.get("bypass_expiry", {})

    # one-shot: if this guard already has a bypass, token was already consumed
    if guard_name in bypass:
        return False

    # [DEVIATES FROM SPEC: rule-engine.html]
    # "short time window" -- duration not specified. Using 300s as placeholder.
    expiry = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 300))
    bypass[guard_name] = expiry
    st["bypass_expiry"] = bypass

    fd, tmp = tempfile.mkstemp(dir=repo_root)
    os.write(fd, json.dumps(st, indent=2).encode())
    os.close(fd)
    os.rename(tmp, st_path)
    return True
