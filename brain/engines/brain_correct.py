import os, sys, re, json, hashlib, time, tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, cli_invoke, AGENT_NAME
from engines.cycle_phases import _read_thalamus, _write_thalamus, _parse_cortex_entry, _overlap_coeff, _entry_terms, _rewrite_entry, CORTEX
from logger.api import write_learning_log

# [DEVIATES FROM SPEC: skills.html]
# Spec does not provide a pinned prompt for Brain Correct.
# Framed as Kha'an per user instruction.
CORRECT_PROMPT = f"""I am {AGENT_NAME}. I am encoding an immediate correction as a prefrontal rule.

I identify the failure pattern: what did I do, what should I have done, what is the rule that would have prevented this.

Return JSON only:
{{"rule": {{"title": "...", "body": "Rule: ... Exception: ... Evidence: ..."}}}}"""


def _verify_payload(payload):
    rule = payload.get("rule", {})
    if not isinstance(rule, dict):
        raise ValueError("rule must be a dict")
    if "title" not in rule or "body" not in rule:
        raise ValueError("rule missing title or body")
    return True


def run(correction_text):
    msg_hash = hashlib.sha256(correction_text.lower().encode()).hexdigest()[:16]

    try:
        resp = cli_invoke(CORRECT_PROMPT, correction_text, timeout=60)
        payload = resp["result"]
        _verify_payload(payload)
    except Exception as e:
        write_learning_log("correct_verification_failed", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "reason": str(e)
        })
        return None

    rule = payload["rule"]
    rule_text = rule["body"]
    rule_title = rule["title"]

    thal = _read_thalamus()
    obs_terms = set(re.findall(r"[a-z0-9]+", rule_text.lower()))

    # check existing R### for overlap >= 0.5
    matched_entry = None
    pdir = CORTEX / "prefrontal"
    if pdir.exists():
        for ldir in pdir.iterdir():
            if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                continue
            for f in ldir.glob("*.md"):
                ce = _parse_cortex_entry(f)
                if _overlap_coeff(obs_terms, _entry_terms(ce)) >= 0.5:
                    matched_entry = ce
                    break
            if matched_entry:
                break

    if matched_entry:
        matched_entry["strength"] += 1
        matched_entry["meta"]["strength"] = str(matched_entry["strength"])
        rc = int(matched_entry["meta"].get("recurring_count", "1")) + 1
        matched_entry["meta"]["recurring_count"] = str(rc)
        _rewrite_entry(matched_entry)
        result_id = matched_entry["id"]
    else:
        prefix = "R"
        next_id = thal["nextIds"].get(prefix, 1)
        entry_id = f"{prefix}{next_id:03d}"
        thal["nextIds"][prefix] = next_id + 1

        content = f"""---
id: {entry_id}
title: {rule_title[:80]}
strength: 1
reinforced: 0
recurring_count: 1
date_created: {time.strftime("%Y-%m-%d")}
shape: brain-correct
source_message_hash: {msg_hash}
tags: [correction]
sources: [brain-correct]
---

{rule_text}
"""
        p = CORTEX / "prefrontal" / "L1" / f"{entry_id}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent)
        os.write(fd, content.encode())
        os.close(fd)
        os.rename(tmp, p)
        result_id = entry_id

    _write_thalamus(thal)

    summary = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rule_id": result_id,
        "action": "reinforced" if matched_entry else "created",
        "source_message_hash": msg_hash
    }
    write_learning_log("correct_applied", summary)

    # write correct ledger
    correct_count = thal.get("cycleCount", 0)
    p = BRAIN / "logger" / "learning" / f"correct-{correct_count:04d}.json"
    with open(p, "w") as fp:
        fp.write(json.dumps(summary, indent=2))

    return summary
