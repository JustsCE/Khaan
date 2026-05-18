import os, sys, re, json, hashlib, time, math, tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, write_bin
from logger.api import write_recall_log

CORTEX = BRAIN / "cortex"
NAV = BRAIN / "navigation"
SCAN_REGIONS = ["semantic", "episodic", "procedural", "fusiform", "prefrontal"]
LEVELS = {"L1": 0.5, "L2": 1.5, "L3": 3.0, "L4": 3.0}
SCORE_FLOOR = 2.0

EXCLUDE_RE = re.compile(r"(?:not the|exclude|ignore|skip|without)\s+(\w+)", re.I)
TIME_RE = re.compile(r"(yesterday|last night|last week|this week|last month|this month)", re.I)
COMPARE_RE = re.compile(r"(\w+)\s+(?:vs\.?|versus|compared to|against)\s+(\w+)", re.I)
INTENT_RE = re.compile(r"(?:deploy|build|fix|debug|connect(?:\s+to)?)\s+(\w+)", re.I)
ID_RE = re.compile(r"\b(?:S|E|PR|FUS|ID|BR|AM|R|H)\d*-?\d+\b", re.I)

QUERY_TYPE_PATTERNS = [
    ("procedural", ["how do i", "how to", "step", "procedure", "deploy", "build", "fix", "debug", "run"]),
    ("episodic",   ["when", "what happened", "remember", "session", "incident", "story"]),
    ("fusiform",   ["who", "person", "team", "user"]),
    ("prefrontal", ["rule", "never", "always", "must"]),
    ("identity",   ["i am", "kha'an", "myself"]),
    ("broca",      ["voice", "tone", "say it", "communication"]),
    ("amygdala",   ["feel", "frustrated", "angry", "anxious", "charge"]),
]


def _infer_query_type(lower):
    for qtype, keywords in QUERY_TYPE_PATTERNS:
        for kw in keywords:
            if kw in lower:
                return qtype
    return "semantic"


def _normalize(msg):
    lower = msg.lower()
    excluded = set(m.group(1).lower() for m in EXCLUDE_RE.finditer(lower))
    time_hint = None
    tm = TIME_RE.search(lower)
    if tm:
        t = tm.group(1).lower()
        if t in ("yesterday", "last night"):
            time_hint = "recent_1d"
        elif t in ("last week", "this week"):
            time_hint = "recent_7d"
        elif t in ("last month", "this month"):
            time_hint = "recent_30d"
    compare_targets = []
    for m in COMPARE_RE.finditer(lower):
        compare_targets.extend([m.group(1), m.group(2)])
    intent_targets = [m.group(1) for m in INTENT_RE.finditer(lower)]
    msg_words = re.findall(r"[a-z0-9]+", lower)
    # stems require inverted-index.json with a stem_map field;
    # the index rebuilder (cycle_phases.py phase 4) does not write stem_map yet,
    # so stems are empty until the Learning Engine adds stemming to index rebuild
    msg_stems = set()
    query_type = _infer_query_type(lower)
    entity_linked = {m.group(0).upper() for m in ID_RE.finditer(msg)}
    return excluded, time_hint, compare_targets, intent_targets, msg_words, msg_stems, query_type, entity_linked


def _parse_entry(path):
    text = path.read_text(errors="replace")
    lines = text.strip().splitlines()
    entry_id = path.stem
    gist = ""
    domain = ""
    learned = ""
    related = []
    # Fallback: extract gist from YAML frontmatter title if no ### header found
    for line in lines:
        l = line.strip()
        if l.startswith("title:"):
            gist = l[6:].strip().strip('"').strip("'")
            break
    for line in lines:
        l = line.strip()
        if l.startswith("### "):
            gist = l[4:].strip()
        elif "**Domain:**" in l:
            domain = l.split("**Domain:**")[-1].strip().lower()
        elif "**Learned:**" in l or "**Date:**" in l:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", l)
            if m:
                learned = m.group(1)
        elif "**Linked entries:**" in l or "**Referenced by:**" in l or "**Evidence:**" in l:
            related.extend(re.findall(r"[A-Z]+[\-]?\d+", l))
    region = path.parent.parent.name
    level = path.parent.name
    return {
        "id": entry_id, "path": str(path.relative_to(BRAIN)),
        "gist": gist, "body": text, "domain": domain,
        "region": region, "level": level, "learned": learned,
        "related_to": related
    }


def _domain_match(msg_words, excluded, compare_targets, intent_targets):
    dict_path = NAV / "domain-dictionary.json"
    matched_domains = []
    scan_domains = list(SCAN_REGIONS)

    if dict_path.exists():
        dd = json.loads(dict_path.read_text())
        msg_str = " ".join(msg_words)
        for dname, dinfo in dd.items():
            if dname.lower() in excluded:
                continue
            if dname.lower() in msg_str:
                matched_domains.append(dname)
                continue
            for kw in dinfo.get("keywords", []):
                if kw.lower() in msg_str:
                    matched_domains.append(dname)
                    break
        for ct in compare_targets:
            for dname in dd:
                if ct in dname.lower() and dname not in matched_domains:
                    matched_domains.append(dname)

    # bundle detection
    bundle_entry_ids = set()
    active_bundles = []
    bundle_dir = BRAIN / "bundles"
    if bundle_dir.exists():
        for bp in bundle_dir.glob("*.json"):
            b = json.loads(bp.read_text())
            trigger = b.get("trigger", "").lower()
            keywords = [k.lower() for k in b.get("keywords", [])]
            msg_str = " ".join(msg_words)
            kw_hits = sum(1 for k in keywords if k in msg_str)
            intent_hits = sum(1 for it in intent_targets if it in msg_str)
            if trigger and trigger in msg_str:
                active_bundles.append(b["name"])
                bundle_entry_ids.update(b.get("entries", []))
            elif kw_hits >= 2 or (kw_hits >= 1 and intent_hits >= 1):
                active_bundles.append(b["name"])
                bundle_entry_ids.update(b.get("entries", []))

    return matched_domains, active_bundles, bundle_entry_ids, scan_domains


def _collect_entries(scan_domains):
    entries = []
    for region in scan_domains:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for level_dir in sorted(rdir.iterdir()):
            if not level_dir.is_dir() or level_dir.name not in LEVELS:
                continue
            for f in level_dir.glob("*.md"):
                entries.append(_parse_entry(f))
    return entries


def _score(entries, matched_domains, msg_words, msg_stems, bundle_entry_ids, query_type, entity_linked):
    # read inverted index for IDF if it exists
    idx_path = NAV / "inverted-index.json"
    idf_weights = {}
    if idx_path.exists():
        idx = json.loads(idx_path.read_text())
        idf_weights = idx.get("idf", {})

    # read recall-index for per-entry access counters (voluntary_access, last_access_ts)
    recall_idx_path = NAV / "recall-index.json"
    recall_meta = {}
    if recall_idx_path.exists():
        try:
            recall_meta = json.loads(recall_idx_path.read_text())
        except Exception:
            recall_meta = {}

    now = time.time()
    candidates = []
    for e in entries:
        etext = e["body"].lower()
        ewords = set(re.findall(r"[a-z0-9]+", etext))

        domain_bonus = 3.0 if any(d.lower() in e["domain"] for d in matched_domains) else 0.0
        type_bonus = 1.5 if e["region"] == query_type else 0.0
        level_bonus = LEVELS.get(e["level"], 0.5)

        # lex_bonus: IDF-weighted if index exists, plain hit count otherwise
        lex = 0.0
        for w in msg_words:
            if w in ewords:
                lex += idf_weights.get(w, 1.0)
        for s in msg_stems:
            if any(s in ew for ew in ewords):
                lex += idf_weights.get(s, 1.0) * 0.5
        lex_bonus = min(lex, 4.0)

        co_ref_bonus = 2.0 if e["id"].upper() in entity_linked else 0.0
        bundle_bonus = 1.5 if e["id"] in bundle_entry_ids else 0.0

        meta = recall_meta.get(e["id"], {})
        va = meta.get("voluntary_access", 0)
        last_ts = meta.get("last_access_ts")
        reuse_bonus = min(va * 0.5, 2.0)
        if last_ts:
            try:
                age_days = (now - time.mktime(time.strptime(last_ts[:19], "%Y-%m-%dT%H:%M:%S"))) / 86400
                if age_days > 7:
                    reuse_bonus -= 0.5
            except ValueError:
                pass

        score = domain_bonus + type_bonus + level_bonus + lex_bonus + co_ref_bonus + bundle_bonus + reuse_bonus
        if score > 0:
            e["score"] = score
            e["scoring_trace"] = {
                "domain_bonus": domain_bonus, "type_bonus": type_bonus,
                "level_bonus": level_bonus, "lex_bonus": lex_bonus,
                "co_ref_bonus": co_ref_bonus, "bundle_bonus": bundle_bonus,
                "reuse_bonus": reuse_bonus
            }
            candidates.append(e)

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def _rerank(candidates, msg_words, time_hint):
    if not candidates:
        return []

    msg_set = set(msg_words)
    type_seen = {}
    now = time.time()

    for c in candidates:
        gist_words = set(re.findall(r"[a-z0-9]+", c["gist"].lower()))
        specificity = min(len(msg_set & gist_words) * 0.5, 2.0)

        region = c["region"]
        dup_count = type_seen.get(region, 0)
        type_seen[region] = dup_count + 1
        diversity = -1.0 * dup_count

        temporal = 0.0
        if c["learned"]:
            try:
                learned_ts = time.mktime(time.strptime(c["learned"], "%Y-%m-%d"))
                days_ago = (now - learned_ts) / 86400
                if time_hint == "recent_1d":
                    temporal = 1.0 if days_ago <= 1 else (-0.5 if days_ago > 30 else 0.0)
                elif time_hint == "recent_7d":
                    temporal = 1.0 if days_ago <= 7 else (0.5 if days_ago <= 14 else (-0.5 if days_ago > 30 else 0.0))
                elif time_hint == "recent_30d":
                    temporal = 1.0 if days_ago <= 30 else -0.5
                else:
                    temporal = 1.0 if days_ago <= 7 else (0.5 if days_ago <= 30 else -0.5)
            except ValueError:
                pass

        c["rerank_score"] = c["score"] + specificity + diversity + temporal
        c["rerank_trace"] = {"specificity": specificity, "diversity": diversity, "temporal": temporal}

    # graph expansion: 1-hop
    id_map = {c["id"]: c for c in candidates}
    all_entries = {}
    for region in SCAN_REGIONS:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for ld in rdir.iterdir():
            if not ld.is_dir() or ld.name not in LEVELS:
                continue
            for f in ld.glob("*.md"):
                all_entries[f.stem] = f

    neighbours = []
    for c in candidates:
        if c["rerank_score"] < SCORE_FLOOR:
            continue
        for rid in c.get("related_to", []):
            if rid in id_map:
                continue
            if rid in all_entries:
                ne = _parse_entry(all_entries[rid])
                ne["score"] = c["rerank_score"] * 0.5
                ne["rerank_score"] = ne["score"]
                ne["scoring_trace"] = {"graph_expansion_from": c["id"]}
                ne["rerank_trace"] = {"graph_expansion": True}
                if ne["rerank_score"] >= SCORE_FLOOR:
                    neighbours.append(ne)
                    id_map[rid] = ne

    candidates.extend(neighbours)
    candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
    return candidates


def _handoff(candidates, query_hash):
    qualified = [c for c in candidates if c.get("rerank_score", c.get("score", 0)) >= SCORE_FLOOR]
    route = "normal" if qualified else "empty"
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query_hash": query_hash,
        "qualified_entries": [
            {
                "id": c["id"], "path": c["path"], "gist": c["gist"],
                "body": c["body"], "score": round(c.get("rerank_score", c["score"]), 2),
                "scoring_trace": c.get("scoring_trace", {}),
                "related_to": c.get("related_to", [])
            }
            for c in qualified
        ],
        "route": route
    }

    p = NAV / "active-recall.json"
    fd, tmp = tempfile.mkstemp(dir=NAV)
    os.write(fd, json.dumps(payload, indent=2).encode())
    os.close(fd)
    os.replace(tmp, p)

    write_recall_log("handoff", {
        "ts": payload["ts"], "query_hash": query_hash,
        "qualified_ids": [c["id"] for c in qualified],
        "total_chars": len(json.dumps(payload))
    })
    return payload


def dispatch(user_message):
    query_hash = hashlib.sha256(user_message.lower().encode()).hexdigest()[:16]

    try:
        excluded, time_hint, compare_targets, intent_targets, msg_words, msg_stems, query_type, entity_linked = _normalize(user_message)
        matched_domains, active_bundles, bundle_entry_ids, scan_domains = _domain_match(
            msg_words, excluded, compare_targets, intent_targets)

        entries = _collect_entries(scan_domains)
        candidates = _score(entries, matched_domains, msg_words, msg_stems, bundle_entry_ids, query_type, entity_linked)

        write_recall_log("dispatch", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "query_hash": query_hash,
            "scan_domains": scan_domains,
            "candidate_count": len(candidates),
            "qualified_count": len([c for c in candidates if c["score"] >= SCORE_FLOOR]),
            "route": "normal" if candidates else "empty"
        })

        if active_bundles:
            write_recall_log("bundle_activation", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "query_hash": query_hash,
                "bundles_active": active_bundles,
                "bundle_entry_ids": list(bundle_entry_ids)
            })

        reranked = _rerank(candidates, msg_words, time_hint)
        result = _handoff(reranked, query_hash)

        for b in ["recall-stale", "recall-dispatch-failed", "recall-failed", "recall-timeout"]:
            write_bin(b, 0)

        return result

    except Exception:
        write_bin("recall-dispatch-failed", 1)
        return None
