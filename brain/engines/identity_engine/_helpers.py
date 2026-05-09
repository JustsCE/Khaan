import os, sys, re, json, hashlib
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN

CORTEX = BRAIN / "cortex"
NAV = BRAIN / "navigation"
BOOT_REGIONS = ["identity", "broca", "amygdala"]
BOOT_LEVELS = ["L1", "L2", "L3", "L4"]
RELAY_LEVELS = ["L1", "L2", "L3"]
LEVEL_BONUS_BOOT = {"L1": 0.5, "L2": 1.5, "L3": 3.0, "L4": 5.0}
LEVEL_BONUS_RELAY = {"L1": 0.5, "L2": 1.5, "L3": 3.0}
SCORE_FLOOR = 1.5


def _parse_entry(path):
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
    title = meta.get("title", "")
    strength = 0
    try:
        strength = int(meta.get("strength", "0"))
    except ValueError:
        pass
    reinforced_at = None
    try:
        reinforced_at = int(meta.get("reinforced_at_cycle", meta.get("cycle", "")))
    except ValueError:
        reinforced_at = None
    region = path.parent.parent.name
    level = path.parent.name
    subject = meta.get("subject", "")
    return {
        "id": entry_id, "title": title, "body": body,
        "strength": strength, "region": region, "level": level,
        "subject": subject, "reinforced_at_cycle": reinforced_at,
        "path": str(path.relative_to(BRAIN))
    }


def _recency_bonus(entry, cycle_count):
    rc = entry.get("reinforced_at_cycle")
    if rc is None or cycle_count is None:
        return 0.0
    gap = cycle_count - rc
    if gap <= 5:
        return 1.0
    if gap <= 20:
        return 0.5
    return 0.0


def _walk_entries(regions, levels):
    entries = []
    for region in regions:
        rdir = CORTEX / region
        if not rdir.exists():
            continue
        for lname in levels:
            ldir = rdir / lname
            if not ldir.exists():
                continue
            for f in ldir.glob("*.md"):
                entries.append(_parse_entry(f))
    return entries


def _region_file_hashes(regions):
    hashes = {}
    for r in regions:
        rdir = CORTEX / r
        if not rdir.exists():
            continue
        h = hashlib.sha256()
        for ldir in sorted(rdir.iterdir()):
            if not ldir.is_dir():
                continue
            for f in sorted(ldir.glob("*.md")):
                h.update(f.read_bytes())
        hashes[r] = h.hexdigest()[:16]
    return hashes


def _read_cycle_count():
    thalamus_path = BRAIN / "thalamus.json"
    if thalamus_path.exists():
        try:
            return json.loads(thalamus_path.read_text()).get("cycleCount", 0)
        except Exception:
            return 0
    return 0


def _score_boot(entries):
    cycle_count = _read_cycle_count()
    scored = []
    for e in entries:
        level_bonus = LEVEL_BONUS_BOOT.get(e["level"], 0.5)
        recency_bonus = _recency_bonus(e, cycle_count)
        strength_bonus = min(e["strength"] * 0.3, 2.0)
        score = level_bonus + recency_bonus + strength_bonus
        if score >= SCORE_FLOOR:
            e["score"] = score
            scored.append(e)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _score_relay(entries, msg_words, fusiform_aliases, cycle_count):
    scored = []
    for e in entries:
        level_bonus = LEVEL_BONUS_RELAY.get(e["level"], 0.5)
        recency_bonus = _recency_bonus(e, cycle_count)
        strength_bonus = min(e["strength"] * 0.3, 2.0)

        entry_words = set(re.findall(r"[a-z0-9]+", e["body"].lower()))
        overlap = len(msg_words & entry_words)
        coeff = overlap / max(min(len(msg_words), len(entry_words)), 1)
        relevance_bonus = 2.0 if coeff >= 0.25 else 0.0

        charge_bonus = 0.0
        if e["region"] == "amygdala" and e["subject"]:
            subj = e["subject"].lower()
            for fus_id, aliases in fusiform_aliases.items():
                if subj == fus_id.lower() or subj in aliases:
                    for alias in aliases:
                        if alias in msg_words:
                            charge_bonus = 1.0
                            break
                    if charge_bonus > 0:
                        break

        score = level_bonus + recency_bonus + strength_bonus + relevance_bonus + charge_bonus
        if score >= SCORE_FLOOR:
            e["score"] = score
            scored.append(e)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def _load_fusiform_aliases():
    aliases = {}
    fdir = CORTEX / "fusiform"
    if not fdir.exists():
        return aliases
    for ldir in fdir.iterdir():
        if not ldir.is_dir():
            continue
        for f in ldir.glob("*.md"):
            text = f.read_text(errors="replace")
            fus_id = f.stem
            als = set()
            for line in text.splitlines():
                if "**Aliases:**" in line:
                    raw = line.split("**Aliases:**")[-1].strip()
                    for a in re.split(r"[,;]\s*", raw):
                        a = a.strip().lower()
                        if a:
                            als.add(a)
            aliases[fus_id] = als
    return aliases
