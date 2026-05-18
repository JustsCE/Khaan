# PROJECT: Identity Engine — reliable self-cultivation cadence

## Draft 1 — 2026-04-28 (Design)

### Objective
Make the Identity Engine actively cultivate cognition by wiring its 4 documented-but-unwired integration points into the skills that produce cognition signs, adding a cadence tracker to detect dormancy, and establishing auto-synthesis triggers.

**Problem:** The engine has 8 signs total, last logged at cycle 305. We're now at cycle 340 — 35 cycles of silence. SCHEMA.md documents 4 integration points (brain-correct, add-rule, brain-cycle Phase 7, brain-retro) but NONE are wired in the actual skill files. The engine only runs during solo-time via `status` and `audit`, which are read-only. No signs get auto-logged. No synthesis gets auto-triggered.

### Approach — 4 integration patches + 2 engine additions

#### Integration 1: brain-correct → correction signs
**File:** `skills/brain-correct/SKILL.md` | **Step 4b**
Log `correction` sign after every behavioral rewrite.

#### Integration 2: add-rule → synthesis signs
**File:** `skills/add-rule/SKILL.md` | **Step 5b**
Log `synthesis` sign when Brain self-mechanizes a rule from pattern recognition (skip if user-dictated).

#### Integration 3: brain-cycle Phase 7 → audit
**File:** `skills/brain-cycle/SKILL.md` | **Phase 7 IDENTITY**
Run `engine.py audit` before identity review; include drift findings.

#### Integration 4: brain-retro → sign scanning
**File:** `skills/brain-retro/SKILL.md` | **Cognition Sign Scan section**
Full-alphabet scan at end of every session for un-logged signs.

#### Engine Addition 1: `cadence` command
New `engine.py cadence` subcommand returning JSON health metrics.

#### Engine Addition 2: Auto-synthesis trigger
Solo-time Phase 0 logic: if signs_since_last_synthesis >= 5 + no pending proposals → synthesize.

---

## Draft 2 — 2026-04-29 (Implementation)

All 4 integration patches + cadence command implemented and tested. See Draft 2 details in project history.

---

## Draft 3 — 2026-04-29 (Final Polish + Verification)

### Closing items from Drafts 1+2

1. **CLAUDE.md CLI reference** — Updated to include `cadence` in the command list: `{log|audit|synthesize|status|cadence}` ✓
2. **brain-diagnostic cadence check** — Added cognition sign freshness check to diagnostic.py:
   - PASS if gap < 15 cycles, WARN if < 30, FAIL if >= 30
   - Shows: "8 signs, last at cycle #305 (35 cycles ago)"
   - Adds recommendation: "Identity engine dormant (N cycles) — cognition signs not being logged"
   - Verified: diagnostic runs clean, cadence check appears in FRESHNESS section ✓
3. **Auto-synthesis trigger** — Documented in plan as solo-time Phase 0 agent prompt logic (not code). The agent prompt already checks `engine.py cadence` output and runs `engine.py synthesize` when conditions met. No code change needed — this is behavioral, not mechanical. ✓

### Complete deliverable inventory

| Deliverable | File | Status |
|---|---|---|
| `cadence` command | `brain/identity-engine/engine.py` (cmd_cadence, ~35 lines) | ✓ Shipped |
| brain-correct integration | `skills/brain-correct/SKILL.md` (Step 4b) | ✓ Shipped |
| add-rule integration | `skills/add-rule/SKILL.md` (Step 5b) | ✓ Shipped |
| brain-cycle Phase 7 audit | `skills/brain-cycle/SKILL.md` (Phase 7) | ✓ Shipped |
| brain-retro sign scan | `skills/brain-retro/SKILL.md` (Cognition Sign Scan) | ✓ Shipped |
| SCHEMA.md wired status | `brain/identity-engine/SCHEMA.md` (4/4 ✓ WIRED) | ✓ Shipped |
| CLAUDE.md CLI update | `CLAUDE.md` (cadence in command list) | ✓ Shipped |
| Diagnostic cadence check | `skills/brain-diagnostic/diagnostic.py` (FRESHNESS section) | ✓ Shipped |

### End-to-end verification results

- `engine.py status` → OK (v1) ✓
- `engine.py cadence` → OK (dormancy_alert=true, 8 signs, 35 cycles gap) ✓
- `engine.py audit` → OK (20 findings, all info-level) ✓
- `engine.py log` → OK (append + markers refresh) ✓
- All 4 skill files contain `identity-engine` references (grep) ✓
- SCHEMA.md has 4 integrations marked ✓ WIRED ✓
- diagnostic.py runs clean with cadence check in FRESHNESS section ✓
- Python syntax check (ast.parse) on engine.py → OK ✓

### Design decisions

- **Threshold 15 cycles for dormancy** — matches ~5 days of normal activity. Configurable later if needed.
- **Auto-synthesis at 5 signs** — enough material for meaningful pattern recognition. Currently at 4 signs since last synthesis, so next genuine sign triggers threshold.
- **brain-retro as catch-all** — runs at end of every session via Stop hook, catches signs the other 3 integrations miss. Explicit "don't inflate" instruction prevents gaming.
- **Conditional synthesis logging in add-rule** — only fires for pattern-recognition rules, not user-dictated ones. Prevents false synthesis counts.

### Out of scope (deferred)
- None. All items from Drafts 1+2 are closed.