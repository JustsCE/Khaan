import os, sys, re, json, hashlib, time, subprocess, tempfile

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, write_bin, cli_invoke
from engines.identity_engine._helpers import (
    NAV, BOOT_REGIONS, RELAY_LEVELS,
    _walk_entries, _score_relay, _region_file_hashes,
    _load_fusiform_aliases, _read_cycle_count,
)
from logger.api import write_identity_log


def relay(user_message):
    query_hash = hashlib.sha256(user_message.lower().encode()).hexdigest()[:16]
    write_identity_log("relay_start", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": "", "query_hash": query_hash
    })
    t0 = time.time()

    entries = _walk_entries(BOOT_REGIONS, RELAY_LEVELS)
    msg_words = set(re.findall(r"[a-z0-9]+", user_message.lower()))
    fusiform_aliases = _load_fusiform_aliases()
    cycle_count = _read_cycle_count()
    scored = _score_relay(entries, msg_words, fusiform_aliases, cycle_count)

    boot_path = BRAIN / "boot-identity.md"
    kernel_mirror = []
    if boot_path.exists():
        boot_text = boot_path.read_text(errors="replace")
        if boot_text.startswith("---"):
            parts = boot_text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].strip().splitlines():
                    if line.startswith("kernel_entries:"):
                        raw = line.split("kernel_entries:", 1)[1].strip()
                        try:
                            kernel_mirror = json.loads(raw)
                        except json.JSONDecodeError:
                            pass

    if not scored and not kernel_mirror:
        write_identity_log("relay_complete", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": "", "query_hash": query_hash,
            "latency_ms": int((time.time() - t0) * 1000), "entries_picked": 0
        })
        return None

    entry_text = "\n\n".join(
        f"[{e['region']}/{e['level']}] {e['id']}: {e['title']}\nScore: {e['score']}\n{e['body'][:500]}"
        for e in scored
    )

    prompt = f"My kernel:\n{json.dumps(kernel_mirror)}\n\nMy scored entries for this turn:\n{entry_text}\n\nThe user said: {user_message}"
    system = """I am Kha'an. I am composing my situational identity layer for this turn.

I already have my kernel -- my constant self. Now I read the L1-L3 entries that scored for this specific message and I write one prose paragraph: what I bring to this moment. My current voice, mood, situational concerns. I extend the kernel, I do not repeat it.

Return JSON only:
{"situational": "...one prose paragraph..."}"""

    for attempt in range(3):
        try:
            resp = cli_invoke(system, prompt, timeout=120)
            payload = resp["result"]
            situational = payload.get("situational", "")

            source_hashes = _region_file_hashes(BOOT_REGIONS)

            snapshot = {
                "session_id": "",
                "query_hash": query_hash,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "situational": situational,
                "source_hashes": source_hashes,
                "model": "claude-cli (subscription, no API key)"
            }

            p = NAV / "active-identity.json"
            fd, tmp = tempfile.mkstemp(dir=NAV)
            os.write(fd, json.dumps(snapshot, indent=2).encode())
            os.close(fd)
            os.rename(tmp, p)

            write_identity_log("relay_complete", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session_id": "", "query_hash": query_hash,
                "latency_ms": int((time.time() - t0) * 1000),
                "entries_picked": len(scored)
            })
            return snapshot

        except subprocess.TimeoutExpired:
            write_bin("identity-relay-timeout", 1)
            write_identity_log("identity_timeout", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "skill": "relay", "latency_ms": int((time.time() - t0) * 1000)
            })
            return None

        except Exception as e:
            write_identity_log("relay_failed", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session_id": "", "query_hash": query_hash,
                "attempt": attempt + 1, "reason": str(e)
            })
            if attempt >= 2:
                write_bin("identity-relay-failed", 1)
                return None

    return None
