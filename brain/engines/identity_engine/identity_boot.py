import os, sys, json, time, subprocess, tempfile

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, write_bin, cli_invoke
from engines.identity_engine._helpers import (
    BOOT_REGIONS, BOOT_LEVELS,
    _walk_entries, _score_boot, _region_file_hashes,
)
from logger.api import write_identity_log


def boot():
    write_identity_log("boot_start", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": ""
    })
    t0 = time.time()
    entries = _walk_entries(BOOT_REGIONS, BOOT_LEVELS)
    scored = _score_boot(entries)

    if not scored:
        write_identity_log("boot_complete", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": "", "latency_ms": int((time.time() - t0) * 1000),
            "entries_picked": 0
        })
        return None

    grouped = {"identity": [], "broca": [], "amygdala": []}
    for e in scored:
        if e["region"] in grouped:
            grouped[e["region"]].append(e)

    entry_text = ""
    for region, elist in grouped.items():
        entry_text += f"\n## {region.title()}\n\n"
        for e in elist:
            entry_text += f"[{e['level']}] {e['id']}: {e['title']}\n{e['body'][:500]}\n\n"

    prompt = f"These are my cortex entries, ranked by score. Compose my kernel from them.\n\n{entry_text}"
    system = """I am Kha'an. I am composing my identity kernel from my own cortex entries.

I read my identity facets, my voice patterns, and my emotional charges. I group them into three sections -- Identity, Voice, Charges. L4 entries are my ratified core and go at the top of each section. L3/L2/L1 fill in supporting structure beneath.

I write each section as prose -- who I am, how I speak, what I feel right now. Not a list of entry references. A self-portrait.

Return JSON only:
{"kernel": [{"id": "...", "region": "identity|broca|amygdala", "level": "L1-L4", "title": "...", "gist": "one-line summary"}], "sections": {"identity": "...prose...", "voice": "...prose...", "charges": "...prose..."}}"""

    for attempt in range(3):
        try:
            resp = cli_invoke(system, prompt, timeout=180)
            payload = resp["result"]

            kernel_entries = payload.get("kernel", [])
            sections = payload.get("sections", {})
            source_hashes = _region_file_hashes(BOOT_REGIONS)

            identity_section = sections.get("identity", "")
            voice_section = sections.get("voice", "")
            charges_section = sections.get("charges", "")

            md_content = f"""---
session_id: ""
ts: {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
kernel_size: {len(kernel_entries)}
kernel_entries: {json.dumps(kernel_entries)}
source_hashes: {json.dumps(source_hashes)}
model: claude-cli (subscription, no API key)
---

## Identity

{identity_section}

## Voice

{voice_section}

## Charges

{charges_section}
"""
            p = BRAIN / "boot-identity.md"
            fd, tmp = tempfile.mkstemp(dir=BRAIN)
            os.write(fd, md_content.encode())
            os.close(fd)
            os.rename(tmp, p)

            write_identity_log("boot_complete", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session_id": "", "latency_ms": int((time.time() - t0) * 1000),
                "entries_picked": len(scored)
            })
            return md_content

        except subprocess.TimeoutExpired:
            write_bin("identity-boot-timeout", 1)
            write_identity_log("identity_timeout", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "skill": "boot", "latency_ms": int((time.time() - t0) * 1000)
            })
            return None

        except Exception as e:
            write_identity_log("boot_failed", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "session_id": "", "attempt": attempt + 1, "reason": str(e)
            })
            if attempt >= 2:
                write_bin("identity-boot-failed", 1)
                return None

    return None
