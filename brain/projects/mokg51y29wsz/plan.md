# PROJECT: Identity Engine v2 — modular HTML doc

## Draft 1 — 2026-04-30 (Build + Push)

### Objective
Build `docs/identity-engine.html` in JustsCE/Brain repo, matching the modular pattern of rule-engine.html and recall-engine.html v3. Single file, same CSS, exactly 5 TOC sections.

### What was delivered (Round 1)
- **File:** `docs/identity-engine.html` on branch `claude/identity-engine-v2-RuXNx`
- **Commit:** a6097107
- **Size:** 15,305 bytes
- Used aspirational migrated paths (logger/identity/, navigation/) — addressed in Round 2

## Draft 2 — 2026-04-30 (Fact-check + Path fixes)

### Issues found and fixed
1. **5 component paths wrong** — doc used aspirational paths that don't exist. Fixed to actual `brain/identity-engine/*` paths.
2. **Markers filename wrong** — `identity-markers.json` → `cognition-markers.json`.
3. **Components table misleading** — replaced "Type" (log/state) with "Mutability" (append-only, rebuilt, mutable).
4. **State vs. log subsection bloated** — replaced with tighter "Markers rebuild" paragraph.
5. **Salience guidance verbose** — tightened all 7 rows.
6. **evolution.md not automated** — added "Manually maintained" qualifier.

### What was delivered (Round 2)
- **Commit:** cdacf74 on branch `claude/identity-engine-v2-fKOf4`
- **Size:** 14,507 bytes (798 bytes leaner)

## Draft 3 — 2026-04-30 (Final polish)

### Objective
Ship-quality doc for Teacher review. Close all threads, verify structural consistency with siblings.

### Final audit results
- [x] CSS `<style>` block byte-identical to rule-engine.html
- [x] TOC has exactly 5 entries
- [x] Philosophy section body is `[reserved]` placeholder
- [x] No forbidden tokens
- [x] All 5 component paths match actual files on disk
- [x] All API facts verified against engine.py (sign validation, salience default 0.8, markers rebuild, audit sources, cadence 12 return fields, dormancy threshold 15)
- [x] Meta line has timestamp consistent with sibling docs
- [x] Doc size proportional to engine complexity (264 lines / 14.5 KB — smallest engine, shortest doc)

### What was delivered (Round 3)
- **Commit:** 9165353 on branch `claude/identity-engine-v2-fKOf4`
- **Size:** 14,517 bytes
- **Branch:** `claude/identity-engine-v2-fKOf4` in JustsCE/Brain

### Sections delivered
1. **Philosophy** — `[reserved]` placeholder (matches recall-engine pattern)
2. **Cognition signs** — 7 sign types with definition, when-fires, salience guidance. JSON log entry format example from real data.
3. **Components** — 5 components with correct paths, mutability column, markers rebuild explanation.
4. **Identity API** — 5 frozen functions (log, audit, synthesize, status, cadence) with args, returns, side effects, validation.
5. **Hook integration** — 4-row table (brain-correct, add-rule, brain-cycle, brain-retro) with skill, hook point, identity call, condition. Clean boundary statement.

### No open TODOs
All items closed. Ready for Teacher review.
