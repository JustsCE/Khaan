import os, sys, re, json, hashlib, time, tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, cli_invoke, write_bin
from engines.cycle_phases import _read_thalamus, _write_thalamus, _parse_cortex_entry, _overlap_coeff, _entry_terms, _rewrite_entry, REGION_PREFIX, CORTEX
from logger.api import write_learning_log

HIPPO = BRAIN / "hippocampus.md"

# [DEVIATES FROM SPEC: skills.html]
# Spec does not provide a pinned prompt for Brain Retro.
# Framed as Kha'an per user instruction.
RETRO_PROMPT = """I am Kha'an. I am running my session-end retrospective.

I read the session transcript and classify findings into three categories:

1. **Worked** -- intended outcome achieved with no correction. I name the procedural path that succeeded.
2. **Broke** -- user correction received. I capture the original behavior, the correction, and the resulting behavior.
3. **Recurring** -- same correction or class of correction received multiple times. I flag it as a candidate for a prefrontal rule.

Return JSON only:
{"findings": [{"category": "worked|broke|recurring", "description": "...", "target_region": "episodic|procedural|prefrontal", "rule_text": "...(only for recurring)"}]}"""


def _verify_payload(payload):
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("findings must be a list")
    for f in findings:
        if "category" not in f or f["category"] not in ("worked", "broke", "recurring"):
            raise ValueError(f"invalid category: {f.get('category')}")
        if "description" not in f:
            raise ValueError("finding missing description")
    return True


def run():
    tc_path = BRAIN / "logger" / "handler" / "turn_complete.jsonl"
    if not tc_path.exists():
        return None

    transcript = tc_path.read_text()
    if not transcript.strip():
        return None

    try:
        resp = cli_invoke(RETRO_PROMPT, transcript, timeout=300)
        payload = resp["result"]
        _verify_payload(payload)
    except Exception as e:
        write_learning_log("retro_verification_failed", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "reason": str(e)
        })
        return None

    thal = _read_thalamus()
    findings = payload["findings"]
    worked = 0
    broke = 0
    recurring = 0
    hippo_written = 0

    for f in findings:
        cat = f["category"]

        if cat == "broke":
            broke += 1
            h_id = f"H{thal['nextIds']['H']:03d}"
            thal["nextIds"]["H"] += 1
            entry_line = (f"### {h_id}\n"
                          f"- **date:** {time.strftime('%Y-%m-%d')}\n"
                          f"- **salience:** 0.8\n"
                          f"- **category:** episodic\n"
                          f"- **consolidation:** pending\n"
                          f"- **text:** {f['description']}\n\n")
            with open(HIPPO, "a") as fp:
                fp.write(entry_line)
            hippo_written += 1

        elif cat == "recurring":
            recurring += 1
            rule_text = f.get("rule_text", f["description"])
            prefix = "R"
            next_id = thal["nextIds"].get(prefix, 1)
            entry_id = f"{prefix}{next_id:03d}"
            thal["nextIds"][prefix] = next_id + 1

            # check for existing match
            matched = False
            pdir = CORTEX / "prefrontal"
            if pdir.exists():
                for ldir in pdir.iterdir():
                    if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                        continue
                    for fp in ldir.glob("*.md"):
                        ce = _parse_cortex_entry(fp)
                        obs_terms = set(re.findall(r"[a-z0-9]+", rule_text.lower()))
                        if _overlap_coeff(obs_terms, _entry_terms(ce)) >= 0.5:
                            ce["strength"] += 1
                            ce["meta"]["strength"] = str(ce["strength"])
                            _rewrite_entry(ce)
                            matched = True
                            break
                    if matched:
                        break

            if not matched:
                content = f"""---
id: {entry_id}
title: {rule_text[:80]}
strength: 1
reinforced: 0
date_created: {time.strftime("%Y-%m-%d")}
shape: brain-retro
tags: [recurring-correction]
sources: [brain-retro]
---

{rule_text}
"""
                p = CORTEX / "prefrontal" / "L1" / f"{entry_id}.md"
                p.parent.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=p.parent)
                os.write(fd, content.encode())
                os.close(fd)
                os.rename(tmp, p)

        elif cat == "worked":
            worked += 1
            # reinforce existing procedural entry or write hippocampus entry
            matched = False
            pdir = CORTEX / "procedural"
            if pdir.exists():
                obs_terms = set(re.findall(r"[a-z0-9]+", f["description"].lower()))
                for ldir in pdir.iterdir():
                    if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                        continue
                    for fp in ldir.glob("*.md"):
                        ce = _parse_cortex_entry(fp)
                        if _overlap_coeff(obs_terms, _entry_terms(ce)) >= 0.5:
                            ce["strength"] += 1
                            ce["meta"]["strength"] = str(ce["strength"])
                            _rewrite_entry(ce)
                            matched = True
                            break
                    if matched:
                        break

            if not matched:
                h_id = f"H{thal['nextIds']['H']:03d}"
                thal["nextIds"]["H"] += 1
                entry_line = (f"### {h_id}\n"
                              f"- **date:** {time.strftime('%Y-%m-%d')}\n"
                              f"- **salience:** 0.6\n"
                              f"- **category:** procedural\n"
                              f"- **consolidation:** pending\n"
                              f"- **text:** {f['description']}\n\n")
                with open(HIPPO, "a") as fp:
                    fp.write(entry_line)
                hippo_written += 1

    _write_thalamus(thal)

    summary = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "worked_count": worked, "broke_count": broke,
        "recurring_flagged": recurring, "hippo_entries_written": hippo_written
    }
    write_learning_log("retro_summary", summary)

    # write retro ledger
    retro_id = thal.get("cycleCount", 0)
    p = BRAIN / "logger" / "learning" / f"retro-{retro_id:04d}.json"
    with open(p, "w") as fp:
        fp.write(json.dumps({"findings": findings, **summary}, indent=2))

    return summary
