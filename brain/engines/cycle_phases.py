import os, sys, re, json, hashlib, time, math, tempfile, subprocess, shutil
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, write_bin, read_bin, cli_invoke, file_hash, read_state, write_state
from logger.api import write_learning_log

CORTEX = BRAIN / "cortex"
NAV = BRAIN / "navigation"
HIPPO = BRAIN / "hippocampus.md"
THALAMUS = BRAIN / "thalamus.json"
KHAAN_REPO = Path("/home/ubuntu/Khaan")
ALL_REGIONS = ["semantic", "episodic", "procedural", "fusiform", "identity", "broca", "amygdala", "prefrontal"]
REGION_PREFIX = {"semantic": "S", "episodic": "E", "procedural": "PR", "fusiform": "FUS",
                 "identity": "ID", "broca": "BR", "amygdala": "AM", "prefrontal": "R"}

INGEST_PROMPT = """I am Kha'an. I am ingesting observations from my recent conversation transcript.

For each candidate observation, I classify it into one memory category and assign salience 0.0-1.0.

Categories:
- semantic: stable fact about a tool, system, concept
- episodic: event with narrative + weight
- procedural: cue + routine + reward
- fusiform: about a person in my orbit
- identity: a facet of my current self-model
- broca: an emotional event chain
- amygdala: a current emotional charge with subject self or person
- prefrontal: a rule observation (do X, never do Y)

Salience heuristics:
- User correction or explicit emphasis ("remember this") -> 0.9+
- Recurring pattern across multiple turns -> 0.7-0.9
- Novel fact or procedure with concrete outcome -> 0.5-0.7
- Routine working state, uncontested observations, ephemeral chatter -> < 0.5

I discard ephemeral or already-known observations.

Return JSON only:
{"observations": [{"text": "...", "category": "...", "salience": 0.0-1.0}]}"""

SYNTH_SYSTEM_PROMPT = """You are synthesizing a cluster of source cortex entries
into a single canonical, abstracted entry one level higher in the
brain's memory pyramid.

# Inputs (passed under ---INPUTS---)

A JSON object:

    {
      "region": "semantic|episodic|procedural|fusiform|identity|
                broca|amygdala|prefrontal",
      "level_out": "L2|L3",
      "cohesion": 0.62,        // overlap-coefficient of the cluster
      "common_terms": ["..."],  // shared tokens across all members
      "members": [
        {"id": "S012", "title": "...", "body_excerpt": "...",
         "tags": ["..."]},
        ...
      ]
    }

# Output

Markdown body only. The Python wrapper adds YAML frontmatter — do NOT
include `---` blocks. Compose:

    # <prose title — not bullet-y, but substantive>

    <1–3 paragraphs identifying the underlying pattern the source
    entries share. Don't enumerate the sources. Don't say "this
    cluster is about X." State the pattern as canonical knowledge,
    grounded in the sources.>

    *Source: [<comma-separated source IDs>]*

# Voice constraints by region

- semantic    → declarative, factual ("X is Y because Z")
- episodic    → narrative, events with consequence ("On <date>, <event>;
                 it implied <pattern>")
- procedural  → instructional, second-person imperative ("To do X,
                 first <step>; the principle is <abstraction>")
- fusiform    → biographical, relational ("<person> is <role>;
                 their pattern is <observation>")
- identity    → first-person, reflective ("I X because Y")
- broca       → register-aware ("My voice does X when Y")
- amygdala    → emotionally-grounded ("X charges me; Y dampens")
- prefrontal  → rule-shaped ("Always X. Never Y. Reason: Z.")

# Constraints

- Total length: 100–300 words.
- Don't quote source bodies verbatim. Abstract to the pattern.
- Don't apologize for synthesis ("I tried to combine these…").
- Title must be a noun phrase or imperative, not a question or
  bulleted list.
- The `*Source: [...]*` line is required and must be the last line.

# Failure mode

If inputs are missing, malformed, or empty, return:

    {"error": "compose-failed: <one-line reason>"}

(JSON object, no surrounding markdown.) Otherwise, return only the
markdown body — no JSON wrapper, no preamble, no ```fences```."""


def _read_thalamus():
    return json.loads(THALAMUS.read_text())


def _write_thalamus(data):
    fd, tmp = tempfile.mkstemp(dir=BRAIN)
    os.write(fd, json.dumps(data, indent=2).encode())
    os.close(fd)
    os.rename(tmp, THALAMUS)


def _parse_hippo():
    if not HIPPO.exists():
        return []
    text = HIPPO.read_text()
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("### H"):
            if current:
                entries.append(current)
            m = re.match(r"### (H\d+)", line)
            current = {"id": m.group(1) if m else "", "header": line, "lines": [], "meta": {}}
        elif current:
            current["lines"].append(line)
            if line.startswith("- **") and ":**" in line:
                k = line.split("**")[1].rstrip(":")
                v = line.split(":**")[-1].strip()
                current["meta"][k] = v
    if current:
        entries.append(current)
    return entries


def _write_hippo(entries):
    lines = []
    for e in entries:
        lines.append(e["header"])
        lines.extend(e["lines"])
    fd, tmp = tempfile.mkstemp(dir=BRAIN)
    os.write(fd, ("\n".join(lines) + "\n").encode())
    os.close(fd)
    os.rename(tmp, HIPPO)


def _parse_cortex_entry(path):
    text = path.read_text(errors="replace")
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = parts[2].strip()
    entry_id = meta.get("id", path.stem)
    strength = 0
    try:
        strength = int(meta.get("strength", "0"))
    except ValueError:
        pass
    tags = []
    raw_tags = meta.get("tags", "")
    if raw_tags.startswith("["):
        tags = [t.strip().strip("'\"") for t in raw_tags.strip("[]").split(",")]
    related = []
    raw_rel = meta.get("related", meta.get("lineage", ""))
    if raw_rel.startswith("["):
        related = [r.strip().strip("'\"") for r in raw_rel.strip("[]").split(",") if r.strip()]
    return {
        "id": entry_id, "path": path, "body": body, "meta": meta,
        "strength": strength, "tags": tags, "related": related,
        "region": path.parent.parent.name, "level": path.parent.name,
        "terms": set(re.findall(r"[a-z0-9]+", (meta.get("title", "") + " " + body).lower()))
    }


def _entry_terms(entry):
    return entry["terms"] | set(entry["tags"])


def _overlap_coeff(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# Phase 1 — Ingest
def phase_ingest():
    tc_path = BRAIN / "logger" / "handler" / "turn_complete.jsonl"
    if not tc_path.exists():
        return [], {"phase": "ingest", "executed": True, "detail": "0 observations across 0 categories"}

    st = read_state()
    last_cycle_ts = st.get("last_cycle_end_ts", 0)

    turns = []
    for line in tc_path.read_text().splitlines():
        if not line.strip():
            continue
        evt = json.loads(line)
        evt_ts = evt.get("ts", "")
        if evt_ts and last_cycle_ts:
            try:
                t = time.mktime(time.strptime(evt_ts[:19], "%Y-%m-%dT%H:%M:%S"))
                if t <= last_cycle_ts:
                    continue
            except ValueError:
                pass
        turns.append(evt)

    if not turns:
        return [], {"phase": "ingest", "executed": True, "detail": "0 observations across 0 categories"}

    # walk the chat transcript since the last cycle -- no truncation
    transcript = "\n\n".join(
        f"User: {t.get('user_prompt', '')}\nAssistant: {t.get('final_response', '')}"
        for t in turns
    )

    try:
        resp = cli_invoke(INGEST_PROMPT, transcript, timeout=60)
        observations = resp["result"].get("observations", [])
    except Exception:
        observations = []

    cats = {}
    for o in observations:
        c = o.get("category", "semantic")
        cats[c] = cats.get(c, 0) + 1

    detail = f"{len(observations)} observations across {len(cats)} categories"
    return observations, {"phase": "ingest", "executed": True, "detail": detail}


# Phase 2 — Hippocampus
def phase_hippocampus(observations):
    if not observations:
        write_bin("cycle-empty", 1)
        write_learning_log("cycle_empty", {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        return {"phase": "hippocampus", "executed": True, "detail": "0 entries"}

    thal = _read_thalamus()
    existing = _parse_hippo()
    pending_count = len([e for e in existing if e["meta"].get("consolidation") == "pending"])

    for obs in observations:
        h_id = f"H{thal['nextIds']['H']:03d}"
        thal["nextIds"]["H"] += 1

        entry = {
            "id": h_id,
            "header": f"### {h_id}",
            "lines": [
                f"- **date:** {time.strftime('%Y-%m-%d')}",
                f"- **salience:** {obs.get('salience', 0.5)}",
                f"- **category:** {obs.get('category', 'semantic')}",
                f"- **consolidation:** pending",
                f"- **text:** {obs.get('text', '')}",
                ""
            ],
            "meta": {
                "date": time.strftime("%Y-%m-%d"),
                "salience": str(obs.get("salience", 0.5)),
                "category": obs.get("category", "semantic"),
                "consolidation": "pending",
                "text": obs.get("text", "")
            }
        }
        existing.append(entry)
        pending_count += 1

        if pending_count > 50:
            pending = [e for e in existing if e["meta"].get("consolidation") == "pending"]
            pending.sort(key=lambda e: float(e["meta"].get("salience", "0")))
            drop = pending[0]
            existing.remove(drop)
            pending_count -= 1

        if pending_count >= 40:
            _write_hippo(existing)
            phase_consolidate()
            existing = _parse_hippo()
            pending_count = len([e for e in existing if e["meta"].get("consolidation") == "pending"])

    _write_hippo(existing)
    _write_thalamus(thal)
    return {"phase": "hippocampus", "executed": True, "detail": f"{len(observations)} entries"}


# Phase 3 — Consolidate
def phase_consolidate():
    entries = _parse_hippo()
    pending = [e for e in entries if e["meta"].get("consolidation") == "pending"]
    if not pending:
        return {"phase": "consolidate", "executed": True, "detail": "0 reinforced, 0 promoted, 0 discarded"}

    thal = _read_thalamus()
    config = thal.get("config", {})
    l2_thresh = config.get("level_thresholds", {}).get("L2", 5)

    reinforced = 0
    promoted = 0
    discarded = 0

    for h in pending:
        cat = h["meta"].get("category", "semantic")
        if cat not in ALL_REGIONS:
            cat = "semantic"
        obs_text = h["meta"].get("text", "")
        obs_terms = set(re.findall(r"[a-z0-9]+", obs_text.lower()))
        salience = float(h["meta"].get("salience", "0.5"))

        best_match = None
        best_overlap = 0.0
        region_dir = CORTEX / cat
        if region_dir.exists():
            for ldir in region_dir.iterdir():
                if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                    continue
                for f in ldir.glob("*.md"):
                    ce = _parse_cortex_entry(f)
                    ov = _overlap_coeff(obs_terms, _entry_terms(ce))
                    # prefer entries below L2 threshold per spec
                    if ov >= 0.5:
                        if best_match is None:
                            best_overlap = ov
                            best_match = ce
                        elif ce["strength"] < l2_thresh and best_match["strength"] >= l2_thresh:
                            best_overlap = ov
                            best_match = ce
                        elif ov > best_overlap and not (ce["strength"] >= l2_thresh and best_match["strength"] < l2_thresh):
                            best_overlap = ov
                            best_match = ce
                    elif ov > best_overlap:
                        best_overlap = ov
                        best_match = ce

        if best_overlap >= 0.5 and best_match:
            best_match["strength"] += 1
            best_match["meta"]["strength"] = str(best_match["strength"])
            reinforced_count = int(best_match["meta"].get("reinforced", "0")) + 1
            best_match["meta"]["reinforced"] = str(reinforced_count)
            _rewrite_entry(best_match)
            _check_level_move(best_match, thal)
            reinforced += 1

        elif best_overlap >= 0.25 and best_match:
            if salience >= 0.5:
                _promote_new_entry(cat, obs_text, salience, thal)
                promoted += 1
            else:
                best_match["strength"] += 1
                best_match["meta"]["strength"] = str(best_match["strength"])
                _rewrite_entry(best_match)
                reinforced += 1

        elif salience >= 0.5:
            _promote_new_entry(cat, obs_text, salience, thal)
            promoted += 1

        else:
            discarded += 1

        h["meta"]["consolidation"] = "done"

    remaining = [e for e in entries if e["meta"].get("consolidation") == "pending"]
    _write_hippo(remaining)
    _write_thalamus(thal)

    write_learning_log("consolidation_summary", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reinforced": reinforced, "promoted": promoted, "discarded": discarded
    })
    return {"phase": "consolidate", "executed": True,
            "detail": f"{reinforced} reinforced, {promoted} promoted, {discarded} discarded"}


def _promote_new_entry(region, text, salience, thal):
    prefix = REGION_PREFIX.get(region, "S")
    next_id = thal["nextIds"].get(prefix, 1)
    entry_id = f"{prefix}{next_id:03d}"
    thal["nextIds"][prefix] = next_id + 1

    content = f"""---
id: {entry_id}
title: {text[:80]}
strength: 1
reinforced: 0
date_created: {time.strftime("%Y-%m-%d")}
salience: {salience}
tags: []
sources: [this-cycle]
---

{text}
"""
    p = CORTEX / region / "L1" / f"{entry_id}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent)
    os.write(fd, content.encode())
    os.close(fd)
    os.rename(tmp, p)


def _rewrite_entry(entry):
    p = entry["path"]
    text = p.read_text(errors="replace")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta_lines = []
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k = line.split(":")[0].strip()
                    if k in entry["meta"]:
                        meta_lines.append(f"{k}: {entry['meta'][k]}")
                    else:
                        meta_lines.append(line)
                else:
                    meta_lines.append(line)
            new_text = f"---\n{chr(10).join(meta_lines)}\n---\n{parts[2]}"
            fd, tmp = tempfile.mkstemp(dir=p.parent)
            os.write(fd, new_text.encode())
            os.close(fd)
            os.rename(tmp, p)


def _check_level_move(entry, thal):
    config = thal.get("config", {})
    l2_thresh = config.get("level_thresholds", {}).get("L2", 5)
    l3_thresh = config.get("level_thresholds", {}).get("L3", 8)
    s = entry["strength"]
    current_level = entry["level"]
    target_level = None
    if s >= l3_thresh and current_level in ("L1", "L2"):
        target_level = "L3"
    elif s >= l2_thresh and current_level == "L1":
        target_level = "L2"
    if target_level and target_level != current_level:
        old_path = entry["path"]
        new_dir = old_path.parent.parent / target_level
        new_dir.mkdir(parents=True, exist_ok=True)
        new_path = new_dir / old_path.name
        shutil.move(str(old_path), str(new_path))
        entry["path"] = new_path
        entry["level"] = target_level


# Phase 4 — Index rebuild
def phase_index_rebuild():
    postings = {}
    entry_count = 0
    entries_meta = {}

    for region in ALL_REGIONS:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for ldir in rdir.iterdir():
            if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3", "L4"):
                continue
            if "archive" in str(ldir):
                continue
            for f in ldir.glob("*.md"):
                ce = _parse_cortex_entry(f)
                entry_count += 1
                entries_meta[ce["id"]] = {
                    "path": str(f.relative_to(BRAIN)),
                    "region": ce["region"], "level": ce["level"],
                    "strength": ce["strength"], "tags": ce["tags"],
                    "title": ce["meta"].get("title", "")
                }
                for term in ce["terms"]:
                    if term not in postings:
                        postings[term] = []
                    postings[term].append(ce["id"])

    idf = {}
    for term, ids in postings.items():
        idf[term] = round(math.log(entry_count / max(len(ids), 1)) + 1.0, 3)

    # access counters — scan recent recall logs for qualified_ids
    access_counts = {}
    last_access = {}
    recall_log_dir = BRAIN / "logger" / "recall"
    if recall_log_dir.exists():
        for lf in sorted(recall_log_dir.glob("*.jsonl")):
            for line in lf.read_text(errors="replace").splitlines():
                if not line.strip():
                    continue
                try:
                    evt = json.loads(line)
                except Exception:
                    continue
                if evt.get("event") != "dispatch":
                    continue
                ts = evt.get("ts", "")
                for eid in evt.get("qualified_ids", []) or []:
                    access_counts[eid] = access_counts.get(eid, 0) + 1
                    if ts > last_access.get(eid, ""):
                        last_access[eid] = ts
    for eid, meta in entries_meta.items():
        meta["voluntary_access"] = access_counts.get(eid, 0)
        if eid in last_access:
            meta["last_access_ts"] = last_access[eid]

    idx = {"terms_count": len(postings), "entries_count": entry_count,
           "postings": postings, "idf": idf}
    p = NAV / "inverted-index.json"
    fd, tmp = tempfile.mkstemp(dir=NAV)
    os.write(fd, json.dumps(idx).encode())
    os.close(fd)
    os.rename(tmp, p)

    p2 = NAV / "recall-index.json"
    fd2, tmp2 = tempfile.mkstemp(dir=NAV)
    os.write(fd2, json.dumps(entries_meta).encode())
    os.close(fd2)
    os.rename(tmp2, p2)

    write_learning_log("index_rebuild", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "terms_count": len(postings), "entries_count": entry_count
    })
    return {"phase": "index_rebuild", "executed": True,
            "detail": f"{len(postings)} terms, {entry_count} entries"}


# Phase 5 — Synthesis
def phase_synthesis(cycle_id):
    thal = _read_thalamus()
    config = thal.get("config", {})
    l2_thresh = config.get("level_thresholds", {}).get("L2", 5)
    l3_thresh = config.get("level_thresholds", {}).get("L3", 8)
    cohesion_thresh = config.get("synthesis", {}).get("cohesion", 0.4)
    cluster_min = config.get("synthesis", {}).get("cluster_size", {}).get("min", 2)
    cluster_max = config.get("synthesis", {}).get("cluster_size", {}).get("max", 8)

    l2_created = 0
    l3_created = 0
    archived = 0

    for region in ALL_REGIONS:
        l2_c, l2_a = _synthesize_level(region, "L1", "L2", l2_thresh,
                                         cohesion_thresh, cluster_min, cluster_max, cycle_id, thal)
        l2_created += l2_c
        archived += l2_a
        l3_c, l3_a = _synthesize_level(region, "L2", "L3", l3_thresh,
                                         cohesion_thresh, cluster_min, cluster_max, cycle_id, thal)
        l3_created += l3_c
        archived += l3_a

    thal["schedule"]["last_promotion_scan_cycle"] = cycle_id
    _write_thalamus(thal)
    write_bin("promote-scan-stale", 0)

    return {"phase": "synthesis", "executed": True,
            "detail": f"L2 created {l2_created}, L3 created {l3_created}, sources archived {archived}"}


def _recursive_median_split(eligible, cohesion_thresh, cluster_max, cluster_min):
    """Split oversized cluster by recursive median-overlap per spec."""
    if len(eligible) <= cluster_max:
        return [eligible] if len(eligible) >= cluster_min else []
    # compute median pairwise overlap
    overlaps = []
    for i in range(len(eligible)):
        for j in range(i + 1, len(eligible)):
            overlaps.append(_overlap_coeff(_entry_terms(eligible[i]), _entry_terms(eligible[j])))
    if not overlaps:
        return [eligible[:cluster_max]]
    median = sorted(overlaps)[len(overlaps) // 2]
    # split: build graph at median threshold, take connected components
    n = len(eligible)
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            if _overlap_coeff(_entry_terms(eligible[i]), _entry_terms(eligible[j])) >= median:
                adj[i].add(j)
                adj[j].add(i)
    visited = set()
    subs = []
    for i in range(n):
        if i in visited:
            continue
        comp = []
        stack = [i]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.append(node)
            stack.extend(adj[node] - visited)
        subs.append([eligible[idx] for idx in comp])
    result = []
    for sub in subs:
        if len(sub) <= cluster_max and len(sub) >= cluster_min:
            result.append(sub)
        elif len(sub) > cluster_max:
            result.extend(_recursive_median_split(sub, cohesion_thresh, cluster_max, cluster_min))
        # drop if < cluster_min
    return result


def _synthesize_level(region, src_level, dst_level, strength_thresh,
                      cohesion_thresh, cluster_min, cluster_max, cycle_id, thal):
    src_dir = CORTEX / region / src_level
    if not src_dir.exists():
        return 0, 0

    eligible = []
    for f in src_dir.glob("*.md"):
        ce = _parse_cortex_entry(f)
        if ce["strength"] >= strength_thresh:
            eligible.append(ce)

    if len(eligible) < cluster_min:
        return 0, 0

    # cluster: pairwise overlap, edges at >= cohesion_thresh, connected components
    n = len(eligible)
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            sim = _overlap_coeff(_entry_terms(eligible[i]), _entry_terms(eligible[j]))
            if sim >= cohesion_thresh:
                adj[i].add(j)
                adj[j].add(i)

    visited = set()
    clusters = []
    for i in range(n):
        if i in visited:
            continue
        component = []
        stack = [i]
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            component.append(node)
            stack.extend(adj[node] - visited)
        if len(component) >= cluster_min:
            members = [eligible[idx] for idx in component]
            if len(members) <= cluster_max:
                clusters.append(members)
            else:
                clusters.extend(_recursive_median_split(members, cohesion_thresh, cluster_max, cluster_min))

    created = 0
    archived_count = 0
    for members in clusters:
        all_terms = set()
        for m in members:
            all_terms |= _entry_terms(m)
        common = all_terms.copy()
        for m in members:
            common &= _entry_terms(m)
        cohesion = min(_overlap_coeff(_entry_terms(members[i]), _entry_terms(members[j]))
                       for i in range(len(members)) for j in range(i + 1, len(members)))

        inputs_json = json.dumps({
            "region": region, "level_out": dst_level,
            "cohesion": round(cohesion, 2),
            "common_terms": sorted(common)[:20],
            "members": [{"id": m["id"], "title": m["meta"].get("title", ""),
                         "body_excerpt": m["body"][:300], "tags": m["tags"]}
                        for m in members]
        })

        try:
            resp = cli_invoke(SYNTH_SYSTEM_PROMPT, f"---INPUTS---\n{inputs_json}", timeout=120)
            result_text = resp["result"]
            if isinstance(result_text, dict) and "error" in result_text:
                continue
            if isinstance(result_text, str):
                body = result_text
            else:
                body = json.dumps(result_text)
        except Exception:
            continue

        # extract title from first # line of generated body
        title = ""
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        prefix = REGION_PREFIX.get(region, "S")
        next_id = thal["nextIds"].get(prefix, 1)
        entry_id = f"{prefix}{next_id:03d}"
        thal["nextIds"][prefix] = next_id + 1
        source_ids = [m["id"] for m in members]

        content = f"""---
id: {entry_id}
title: {title or entry_id}
strength: 1
reinforced: 0
date_created: {time.strftime("%Y-%m-%d")}
lineage: {json.dumps(source_ids)}
tags: {json.dumps(sorted(common)[:10])}
sources: [synthesis-cycle-{cycle_id}]
---

{body}
"""
        dst_dir = CORTEX / region / dst_level
        dst_dir.mkdir(parents=True, exist_ok=True)
        p = dst_dir / f"{entry_id}.md"
        fd, tmp = tempfile.mkstemp(dir=dst_dir)
        os.write(fd, content.encode())
        os.close(fd)
        os.rename(tmp, p)
        created += 1

        for m in members:
            archive_dir = CORTEX / "archive" / region / src_level
            archive_dir.mkdir(parents=True, exist_ok=True)
            src_text = m["path"].read_text(errors="replace")
            if src_text.startswith("---"):
                parts = src_text.split("---", 2)
                if len(parts) >= 3:
                    src_text = f"---\n{parts[1].strip()}\narchived_in_cycle: {cycle_id}\n---\n{parts[2]}"
            archive_path = archive_dir / m["path"].name
            fd, tmp = tempfile.mkstemp(dir=archive_dir)
            os.write(fd, src_text.encode())
            os.close(fd)
            os.rename(tmp, archive_path)
            m["path"].unlink()
            archived_count += 1

        write_learning_log("synthesis_event", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cycle_id": cycle_id, "region": region,
            "source_ids": source_ids, "target_id": entry_id,
            "trigger_strength": strength_thresh
        })

    return created, archived_count


# Phase 6 — Eval (every 30 cycles)
def phase_eval(cycle_id):
    thal = _read_thalamus()
    config = thal.get("config", {})
    sample_size = config.get("decay", {}).get("sample_size", 10)

    # load all entry content for term matching
    entry_content = {}
    for region in ALL_REGIONS:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for ldir in rdir.iterdir():
            if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3", "L4"):
                continue
            for f in ldir.glob("*.md"):
                ce = _parse_cortex_entry(f)
                entry_content[ce["id"]] = _entry_terms(ce)
                entry_content[f.stem] = _entry_terms(ce)

    # read recall dispatch logs -- which entries were surfaced per turn
    recall_dir = BRAIN / "logger" / "recall"
    surfaced_per_turn = {}  # query_hash -> set of entry IDs
    if recall_dir.exists():
        for f in sorted(recall_dir.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if not line.strip():
                    continue
                evt = json.loads(line)
                if evt.get("event") == "handoff":
                    qh = evt.get("query_hash", "")
                    surfaced_per_turn[qh] = set(evt.get("qualified_ids", []))

    # read turn_complete for required/applied computation
    tc_path = BRAIN / "logger" / "handler" / "turn_complete.jsonl"
    turns = []
    if tc_path.exists():
        for line in tc_path.read_text().splitlines():
            if not line.strip():
                continue
            turns.append(json.loads(line))

    # per-entry counters
    counters = {}  # entry_id -> {required, surfaced, applied}
    for eid in entry_content:
        counters[eid] = {"required": 0, "surfaced": 0, "applied": 0}

    for turn in turns:
        response = turn.get("final_response", "")
        tool_uses = turn.get("tool_uses", [])
        response_terms = set(re.findall(r"[a-z0-9]+", response.lower()))
        tool_text = json.dumps(tool_uses).lower()
        response_and_tools = response_terms | set(re.findall(r"[a-z0-9]+", tool_text))

        qh = hashlib.sha256(turn.get("user_prompt", "").lower().encode()).hexdigest()[:16]
        surfaced_this_turn = surfaced_per_turn.get(qh, set())

        for eid, terms in entry_content.items():
            if not terms:
                continue
            # required: term overlap >= 0.4 with entry content against response + tool_uses
            ov = _overlap_coeff(terms, response_and_tools)
            if ov >= 0.4:
                counters.setdefault(eid, {"required": 0, "surfaced": 0, "applied": 0})
                counters[eid]["required"] += 1

            # surfaced
            if eid in surfaced_this_turn:
                counters.setdefault(eid, {"required": 0, "surfaced": 0, "applied": 0})
                counters[eid]["surfaced"] += 1

                # applied: surfaced AND overlap >= 0.3 between gist and response
                gist_ov = _overlap_coeff(terms, response_terms)
                if gist_ov >= 0.3:
                    counters[eid]["applied"] += 1

    results = {}
    for eid, c in counters.items():
        r = c["required"]
        a = c["applied"]
        if r >= sample_size:
            miss_rate = round((r - a) / r, 2)
        else:
            miss_rate = "undefined"
        results[eid] = {"required": r, "surfaced": c["surfaced"],
                        "applied": a, "miss_rate": miss_rate, "samples": r}

    eval_data = {
        "cycle_id": cycle_id,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window": config.get("eval", {}).get("window", 30),
        "entries": results
    }
    p = BRAIN / "logger" / "learning" / f"eval-{cycle_id:04d}.json"
    with open(p, "w") as f:
        f.write(json.dumps(eval_data, indent=2))

    write_learning_log("eval_run", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cycle_id": cycle_id, "entries_graded": len(results),
        "turns_in_window": len(turns)
    })
    return {"phase": "eval", "executed": True,
            "detail": f"graded {len(results)} entries across {len(turns)} turns"}


# Phase 7 — Hygiene (every 30 cycles, after eval)
def phase_hygiene(cycle_id):
    thal = _read_thalamus()
    config = thal.get("config", {})
    miss_rate_floor = config.get("decay", {}).get("miss_rate", 0.80)
    sample_size = config.get("decay", {}).get("sample_size", 10)

    eval_path = BRAIN / "logger" / "learning" / f"eval-{cycle_id:04d}.json"
    if not eval_path.exists():
        return {"phase": "hygiene", "executed": False, "detail": "no eval data"}

    eval_data = json.loads(eval_path.read_text())
    entries_eval = eval_data.get("entries", {})

    decayed = 0
    total = 0
    findings = {
        "lineage_integrity": [], "orphaned_cross_refs": [],
        "stale_but_strong": [], "index_disc_mismatch": [], "domain_drift": []
    }

    # build lookup of all live entry IDs
    live_ids = set()
    for region in ALL_REGIONS:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for ldir in rdir.iterdir():
            if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3", "L4"):
                continue
            for f in ldir.glob("*.md"):
                live_ids.add(f.stem)

    # decay + audit pass
    for region in ALL_REGIONS:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for ldir in rdir.iterdir():
            if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                continue
            for f in ldir.glob("*.md"):
                total += 1
                ce = _parse_cortex_entry(f)
                eid = ce["id"]
                e_eval = entries_eval.get(eid, entries_eval.get(f.stem, {}))
                mr = e_eval.get("miss_rate", "undefined")
                samples = e_eval.get("samples", 0)

                # decay
                if mr != "undefined" and float(mr) > miss_rate_floor and samples >= sample_size:
                    ce["strength"] = max(ce["strength"] - 1, 0)
                    ce["meta"]["strength"] = str(ce["strength"])
                    _rewrite_entry(ce)
                    decayed += 1
                    _check_level_demotion(ce, thal)

                # audit: stale-but-strong
                if ce["strength"] >= 5 and e_eval.get("surfaced", 0) == 0:
                    findings["stale_but_strong"].append({
                        "entry_id": eid, "region": region, "strength": ce["strength"]
                    })

                # audit: lineage integrity
                for src_id in ce.get("related", []):
                    if src_id and src_id not in live_ids:
                        # check if archived
                        archived = False
                        for al in ("L1", "L2", "L3"):
                            if (CORTEX / "archive" / region / al / f"{src_id}.md").exists():
                                archived = True
                                break
                        if not archived:
                            findings["lineage_integrity"].append({
                                "entry_id": eid, "missing_source": src_id, "region": region
                            })

                # audit: orphaned cross-references
                for ref_id in re.findall(r"[A-Z]+[\-]?\d+", ce["body"]):
                    if ref_id != eid and ref_id not in live_ids:
                        findings["orphaned_cross_refs"].append({
                            "entry_id": eid, "missing_ref": ref_id, "where": "body"
                        })

    # audit: index-disc mismatch
    idx_path = NAV / "inverted-index.json"
    if idx_path.exists():
        idx = json.loads(idx_path.read_text())
        all_indexed = set()
        for ids in idx.get("postings", {}).values():
            all_indexed.update(ids)
        for eid in all_indexed:
            if eid not in live_ids:
                findings["index_disc_mismatch"].append({"index_id": eid, "exists_on_disc": False})

    # audit: domain drift -- requires domain-dictionary.json
    dd_path = NAV / "domain-dictionary.json"
    if dd_path.exists():
        dd = json.loads(dd_path.read_text())
        for region in ALL_REGIONS:
            rdir = CORTEX / region
            if not rdir.exists():
                continue
            for ldir in rdir.iterdir():
                if not ldir.is_dir() or ldir.name not in ("L1", "L2", "L3"):
                    continue
                for f in ldir.glob("*.md"):
                    ce = _parse_cortex_entry(f)
                    domain = ce["meta"].get("domain", "")
                    if domain and domain in dd:
                        kws = set(k.lower() for k in dd[domain].get("keywords", []))
                        entry_t = _entry_terms(ce)
                        if not (kws & entry_t):
                            findings["domain_drift"].append({
                                "entry_id": ce["id"], "registered_domain": domain,
                                "current_top_terms": sorted(entry_t)[:10]
                            })

    audit_data = {"cycle_id": cycle_id,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  **findings}
    p = BRAIN / "logger" / "learning" / f"audit-{cycle_id:04d}.json"
    with open(p, "w") as f:
        f.write(json.dumps(audit_data, indent=2))

    write_learning_log("audit_findings", {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cycle_id": cycle_id, **{k: len(v) for k, v in findings.items()}
    })

    detail_parts = [f"decayed {decayed} of {total}"]
    for k, v in findings.items():
        if v:
            detail_parts.append(f"{k} {len(v)}")
    return {"phase": "hygiene", "executed": True, "detail": "; ".join(detail_parts)}


def _check_level_demotion(entry, thal):
    config = thal.get("config", {})
    l2_thresh = config.get("level_thresholds", {}).get("L2", 5)
    l3_thresh = config.get("level_thresholds", {}).get("L3", 8)
    s = entry["strength"]
    current = entry["level"]
    target = None
    if current == "L3" and s < l3_thresh:
        target = "L2"
    elif current == "L2" and s < l2_thresh:
        target = "L1"
    elif current == "L1" and s < 1:
        entry["path"].unlink()
        return
    if target and target != current:
        old_path = entry["path"]
        new_dir = old_path.parent.parent / target
        new_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_path), str(new_dir / old_path.name))


# Phase 8 — Commit
def phase_commit(cycle_id, ledger, hippo_hash_start, nonce):
    thal = _read_thalamus()

    # 6 invariant checks from rule-engine.html
    # 1. cycleCount incremented by exactly +1
    if thal["cycleCount"] + 1 != cycle_id:
        raise ValueError(f"invariant 1: cycleCount {thal['cycleCount']} + 1 != {cycle_id}")

    # 2. hippocampus.md hash differs from start
    hippo_hash_now = file_hash(HIPPO) if HIPPO.exists() else ""
    if hippo_hash_now == hippo_hash_start and any(l.get("phase") == "hippocampus" and l.get("detail", "") != "0 entries" for l in ledger):
        raise ValueError("invariant 2: hippocampus hash unchanged despite non-empty cycle")

    # 3. active_cycle_nonce matches
    st = read_state()
    if st.get("active_cycle_nonce") != nonce:
        raise ValueError(f"invariant 3: nonce mismatch")

    # 4. Phase 5 ran
    if thal["schedule"].get("last_promotion_scan_cycle") != cycle_id:
        raise ValueError("invariant 4: Phase 5 did not run this cycle")

    # 5. Pending H### not strictly growing over last 3 cycles
    # (first cycles won't have history; skip if insufficient data)

    # 6. Every due phase stamped
    for l in ledger:
        if l.get("executed") is None:
            raise ValueError(f"invariant 6: phase {l.get('phase')} not stamped")

    thal["cycleCount"] = cycle_id
    thal["schedule"]["last_promotion_scan_cycle"] = cycle_id
    _write_thalamus(thal)

    st["last_brain_update"] = st.get("message_counter", 0)
    st["last_cycle_end_ts"] = time.time()
    st["last_cycle_outcome"] = "success"
    st["fsm"] = "NORMAL"
    st["active_cycle_nonce"] = None
    write_state(st)

    write_learning_log("cycle_ledger", {"cycle_id": cycle_id, "phases": ledger,
                                         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    write_learning_log("cycle_commit", {"cycle_id": cycle_id,
                                         "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    write_bin("learning-cycle-running", 0)
    write_bin("learning-cycle-overdue", 0)

    # git commit + push in Khaan repo
    git_status = "ok"
    try:
        a = subprocess.run(["git", "add", "-A"], cwd=str(KHAAN_REPO),
                           capture_output=True, text=True, timeout=30)
        if a.returncode != 0:
            git_status = f"add failed: {a.stderr[:200]}"
        else:
            c = subprocess.run(["git", "commit", "-m", f"brain cycle {cycle_id}"],
                               cwd=str(KHAAN_REPO), capture_output=True, text=True, timeout=30)
            if c.returncode != 0:
                if "nothing to commit" in (c.stdout + c.stderr):
                    git_status = "nothing to commit"
                else:
                    git_status = f"commit failed: {c.stderr[:200]}"
            else:
                p = subprocess.run(["git", "push"], cwd=str(KHAAN_REPO),
                                   capture_output=True, text=True, timeout=60)
                if p.returncode != 0:
                    subprocess.run(["git", "stash"], cwd=str(KHAAN_REPO), capture_output=True, timeout=30)
                    subprocess.run(["git", "pull", "--rebase"], cwd=str(KHAAN_REPO), capture_output=True, timeout=60)
                    subprocess.run(["git", "stash", "pop"], cwd=str(KHAAN_REPO), capture_output=True, timeout=30)
                    p2 = subprocess.run(["git", "push"], cwd=str(KHAAN_REPO),
                                        capture_output=True, text=True, timeout=60)
                    git_status = "ok (after rebase)" if p2.returncode == 0 else f"push failed: {p2.stderr[:200]}"
    except Exception as e:
        git_status = f"exception: {type(e).__name__}: {str(e)[:200]}"

    write_learning_log("cycle_git", {"cycle_id": cycle_id, "status": git_status,
                                      "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    return {"phase": "commit", "executed": True, "detail": f"cycle {cycle_id}"}
