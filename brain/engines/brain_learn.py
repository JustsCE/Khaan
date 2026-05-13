import os, sys, re, json, hashlib, time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, cli_invoke, AGENT_NAME
from engines.cycle_phases import _read_thalamus, _write_thalamus, _parse_cortex_entry, _overlap_coeff, _entry_terms, ALL_REGIONS, CORTEX
from logger.api import write_learning_log

HIPPO = BRAIN / "hippocampus.md"

# [DEVIATES FROM SPEC: skills.html]
# Spec does not provide a pinned prompt for Brain Learn.
# Framed per user instruction.
LEARN_PROMPT = f"""I am {AGENT_NAME}. I am extracting observations from an external source.

For each observation I extract, I classify it into one memory category and assign salience 0.0-1.0.
Every observation cites a span of the source. I do not fabricate. Unknowns are marked TBD.
If the source contradicts itself, I surface the contradiction.

Categories: semantic, episodic, procedural, fusiform, identity, broca, amygdala, prefrontal.

Return JSON only:
{{"observations": [{{"text": "...", "category": "...", "salience": 0.0-1.0, "source_span": "..."}}]}}"""


def _verify_payload(payload):
    obs = payload.get("observations", [])
    if not isinstance(obs, list):
        raise ValueError("observations must be a list")
    for o in obs:
        if "text" not in o:
            raise ValueError("observation missing text")
        if "category" not in o or o["category"] not in ALL_REGIONS:
            raise ValueError(f"invalid category: {o.get('category')}")
        if "salience" not in o:
            raise ValueError("observation missing salience")
        if "source_span" not in o:
            raise ValueError("observation missing source_span")
    return True


def run(source):
    source_path = Path(source).expanduser()
    if source_path.exists():
        content = source_path.read_text(errors="replace")
    else:
        content = source

    source_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

    try:
        resp = cli_invoke(LEARN_PROMPT, content, timeout=1800)
        payload = resp["result"]
        _verify_payload(payload)
    except Exception as e:
        write_learning_log("learn_verification_failed", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_hash": source_hash, "reason": str(e)
        })
        return None

    observations = payload["observations"]
    thal = _read_thalamus()
    promoted = 0
    rejected = 0

    for obs in observations:
        obs_terms = set(re.findall(r"[a-z0-9]+", obs["text"].lower()))
        cat = obs["category"]

        # match against existing cortex
        matched = False
        region_dir = CORTEX / cat
        if region_dir.exists():
            for ldir in region_dir.iterdir():
                if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                    continue
                for f in ldir.glob("*.md"):
                    ce = _parse_cortex_entry(f)
                    if _overlap_coeff(obs_terms, _entry_terms(ce)) >= 0.5:
                        matched = True
                        break
                if matched:
                    break

        if matched:
            rejected += 1
            continue

        h_id = f"H{thal['nextIds']['H']:03d}"
        thal["nextIds"]["H"] += 1
        entry_line = (f"### {h_id}\n"
                      f"- **date:** {time.strftime('%Y-%m-%d')}\n"
                      f"- **salience:** {obs.get('salience', 0.5)}\n"
                      f"- **category:** {cat}\n"
                      f"- **consolidation:** pending\n"
                      f"- **source:** brain-learn\n"
                      f"- **text:** {obs['text']}\n\n")
        with open(HIPPO, "a") as fp:
            fp.write(entry_line)
        promoted += 1

    _write_thalamus(thal)

    summary = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_hash": source_hash,
        "observations_extracted": len(observations),
        "observations_rejected": rejected,
        "hippo_entries_promoted": promoted,
        "model": "claude-cli"
    }
    write_learning_log("learn_batch", summary)

    p = BRAIN / "logger" / "learning" / f"learn-{source_hash}.json"
    with open(p, "w") as fp:
        fp.write(json.dumps({"observations": observations, **summary}, indent=2))

    return summary
