# PROJECT: Fix the Autonomy Engine

## Draft 3 — Revision 1 (2026-04-28)

### Objective
Build a functional autonomy-engine module that gives Brain decision-making hands.

### Status: v1.2 COMPLETE — Teacher revision addressed

**Revision Changes (addressing Teacher REVISE feedback):**

1. **BUG FIX — warn-gate treated as block (charter.py:64):** Changed `overall` check from `r['gate'] == 'info'` to `r['gate'] in ('info', 'warn')`. Warn-gated tenet failures (like tenet 6: automate_never_refuse) now produce warnings without blocking the task. EXECUTE tasks with "skip"/"ignore"/"refuse"/"decline" in title now correctly route to ACT. Added 5 new tests: 3 charter-level (aligned=True, blockers=0, warnings=1) + 2 integration-level (EXECUTE+skip → ACT, 0 DEFER). Total: 23/23 passing.

2. **__pycache__ removed from git:** Added `brain/autonomy-engine/__pycache__/` to .gitignore, removed cached .pyc files from tracking via `git rm --cached`.

3. **Version string synced:** engine.py `cmd_status()` now reports `v1.2` (was `v1.1`), matching plan.

**Component 1: Decision Router (decision.py) — DONE**
- Verdict routing: ACT / PROPOSE / ASK / DEFER
- EXECUTE-tagged tasks → ACT (trusts Justs' promotion, no second-guessing)
- Financial/contract keyword detection → DEFER (checked BEFORE EXECUTE for safety)
- Irreversible action detection → DEFER
- VERIFY/NEW → DEFER (Justs-only)
- PROJECT → DEFER (project pipeline handles)
- PLAN → PROPOSE, PENDING → ACT
- Wrong assignee → DEFER

**Component 2: Charter Verifier (charter.py) — DONE**
- 6 tenets from charter.json (block/warn/info gates)
- Tenet 3: Vericity tasks blocked in non-solo modes ✓
- Tenet 1: enforcement drift warnings ✓
- Tenet 6: refusal pattern detection — WARN only, does NOT block ✓ (FIXED)
- Tenet 5: meta-satisfied (charter check IS the precondition) ✓
- Tenets 2, 4: info-level, aspirational (not enforceable at task-triage time)

**Component 3: Recurrence Detector (recurrence.py) — DONE**
- SequenceMatcher fuzzy matching (0.7 threshold)
- Timestamped occurrences (ISO 8601 UTC)
- patterns.json initialized clean, ready for production seeding
- Flags at N≥3 for automation proposal

**Component 4: Integration Layer (integrate.py) — DONE**
- `triage_tasks(tasks, record_patterns=True)`: full pipeline — charter check → decision routing → recurrence tracking
- `record_patterns=False` flag prevents test side-effects
- Returns sorted action plan grouped by verdict with reasoning
- Warnings from charter passed through to action plan results
- Pre-filters VERIFY and PROJECT tags before engine processing

**Component 5: Test Suite (test_engine.py) — DONE**
- 23 test cases covering all decision paths, charter modes, warn-gate behavior, and integration
- Tests use `record_patterns=False` — no longer pollute patterns.json
- All 23/23 passing

### Architecture
```
Dashboard Tasks (JSON)
       ↓
integrate.py:triage_tasks()
       ↓
  ┌─────────────┐
  │ Pre-filter   │ → VERIFY/PROJECT → DEFER (skip)
  └─────┬───────┘
        ↓
  ┌─────────────┐
  │ charter.py   │ → check 6 tenets → BLOCK/WARN/INFO
  └─────┬───────┘       (only BLOCK stops task; WARN passes through)
        ↓
  ┌─────────────┐
  │ decision.py  │ → ACT/PROPOSE/ASK/DEFER
  └─────┬───────┘
        ↓
  ┌─────────────┐
  │ recurrence.py│ → track pattern (with timestamp), flag at N≥3
  └─────────────┘
        ↓
  Action Plan (grouped by verdict, warnings attached)
```
