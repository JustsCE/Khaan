# Implementation Guide

Fresh Khaan brain. Everything below is spec from the 8 golden docs mapped to what needs building.
Cortex entries (563 files across 8 regions) are the only migrated data.
Everything else starts from zero.

---

## Implementation order

Build bottom-up. Each layer depends on the one below it.

```
Layer 0: Disc layout          brain.html
Layer 1: State + binaries     rule-engine.html (state.json, binaries/, bin_io)
Layer 2: Hook wiring          handler.html (hook.py, settings.json)
Layer 3: Recall Engine        recall-engine.html
Layer 4: Identity Engine      identity-engine.html
Layer 5: Decision Engine      decision-engine.html
Layer 6: Learning Engine      learning-engine.html
Layer 7: Skills               skills.html (Brain Retro, Brain Learn, Brain Correct)
```

Each layer's dependencies are listed below in its section.

---

## 1. The Brain (brain.html)

**What it specifies:** Disc layout for all memory regions, entry lineage (L1-L4 promotion),
hippocampus buffer, thalamus counters, navigation files, logger structure.

**Status: PARTIAL -- cortex migrated, everything else missing.**

### Files to create

| File / Directory | Purpose | Status |
|---|---|---|
| `brain/cortex/{semantic,episodic,procedural,fusiform,identity,broca,amygdala,prefrontal}/L{1,2,3,4}/` | 8 regions x 4 levels | MIGRATED (563 entries) |
| `brain/cortex/archive/<region>/L{1,2}/` | Archived source entries after synthesis | NOT CREATED |
| `brain/hippocampus.md` | Short-term buffer (H### entries, cap 50) | NOT CREATED |
| `brain/thalamus.json` | Counters, nextIds, schedule, config constants | NOT CREATED |
| `brain/state.json` | FSM state, cycle nonce, escalation count, bypass expiry | NOT CREATED |
| `brain/binaries/<name>.bin` | Gate files (0 silent / 1 alert) | NOT CREATED |
| `brain/navigation/active-recall.json` | Per-turn recall output | NOT CREATED |
| `brain/navigation/active-identity.json` | Per-turn identity output | NOT CREATED |
| `brain/navigation/active-decision.json` | Per-turn decision output | NOT CREATED |
| `brain/navigation/inverted-index.json` | Term -> entry posting list with IDF weights | NOT CREATED |
| `brain/navigation/recall-index.json` | Entry metadata for fast scoring | NOT CREATED |
| `brain/navigation/domain-dictionary.json` | Domain -> keyword mapping | NOT CREATED |
| `brain/logger/` | Append-only event stream | NOT CREATED |
| `brain/bundles/<name>.json` | Recall preload lists for recurring workflows | NOT CREATED |

### Dependencies

None. This is Layer 0.

### Implementation notes

- `thalamus.json` must contain `config` block with all manually-maintained constants from learning-engine.html (level thresholds, cohesion, decay rates, cycle gap, eval window).
- `state.json` initializes with `state: "NORMAL"`, `cycleCount: 0`, `message_counter: 0`.
- `hippocampus.md` starts empty.
- Binaries: create all gate files at `0`. Full list in rule-engine.html section below.

---

## 2. Rule Engine (rule-engine.html)

**What it specifies:** Binary gate OS, 5 enforcement rules, HMAC bypass, invariant verification,
dispatcher routing table, state.json FSM.

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `brain/engines/dispatcher.py` | Route hook events, read binaries, block on PreToolUse | ~80 |
| `brain/engines/bin_io.py` | `read_binary()`, `write_binary()` -- atomic tmp+rename | ~30 |
| `brain/engines/flip_tool_guards.py` | 5 rule predicates evaluated per PreToolUse | ~120 |
| `brain/engines/flip_bypass.py` | HMAC token verification, bypass window management | ~80 |
| `brain/engines/init_binaries.py` | Create all .bin files at 0 | ~40 |

### Binaries to create (23 files)

**Brain Cycle (5):** `learning-cycle-overdue`, `learning-cycle-running`, `learning-cycle-failed`, `learning-cycle-timeout`, `consolidation-pending`, `promote-scan-stale`, `cycle-empty`

**[CORRECTION]**: That's 7, not 5. The doc lists 7 Brain Cycle binaries.

**Recall (4):** `recall-stale`, `recall-dispatch-failed`, `recall-failed`, `recall-timeout`

**Decision (8):** `decision-hypothesis-1` through `-5`, `decision-source-missing`, `decision-failed`, `decision-timeout`

**Identity (4):** `identity-boot-failed`, `identity-relay-failed`, `identity-boot-timeout`, `identity-relay-timeout`

**Total: 23 gate files** (not 29 as CLAUDE.md claimed -- the 5 tool-security gates are per-call predicates, not persistent binaries).

### 5 enforcement rules

1. `use-bash-block` -- Block Edit/Write on `brain/` paths
2. `engine-security-block` -- Block Bash redirects into `engines/*.py`
3. `cycle-security-block` -- Block cycle-state writes outside CYCLE_RUNNING
4. `server-security-block` -- Block bare `docker compose up/down/restart`
5. `permissions-block` -- Block chmod/chown on `brain/`

### Dependencies

- Layer 0 (disc layout from brain.html)
- `.bypass.secret` file for HMAC verification (already exists at `~/.claude/.bypass.secret`)

---

## 3. The Handler (handler.html)

**What it specifies:** CLAUDE.md content, hook.py dispatch table, settings.json registration,
recursion guard, context injection.

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `~/.claude/hook.py` | Single entry point for all 6 hook events | ~150 |
| `~/.claude/CLAUDE.md` | Brain loader (declaration + "don't fight the gates") | ~80 lines of markdown |
| settings.json hook entries | 6 registrations pointing to hook.py | ~10 |

### hook.py dispatch table

| Event | Handler | Action |
|---|---|---|
| `SessionStart` | `handle_session_start()` | Reset binaries, run Identity Boot, return kernel |
| `UserPromptSubmit` | `handle_user_prompt_submit()` | Increment counter, gap check, invoke Decision Engine skill, compose context |
| `PreToolUse` | `handle_pre_tool_use()` | Delegate to dispatcher (block if gates raised) |
| `PostToolUse` | `handle_post_tool_use()` | Passthrough |
| `SubagentStop` | `handle_subagent_stop()` | Dispatch by subagent_type (decision verify) |
| `Stop` | `handle_stop()` | Log turn_complete to logger |

### Key detail: recursion guard

`BRAIN_SKIP_HOOKS=1` env var on all `claude -p` subprocess calls. Checked at top of hook.py.

### Dependencies

- Layer 1 (rule engine -- dispatcher, binaries)
- Layer 4 (identity engine -- Boot runs at SessionStart)
- Layer 5 (decision engine -- invoked at UserPromptSubmit)

### Implementation notes

- handler.html specifies the CLAUDE.md content verbatim. Use that content exactly.
- Hook registrations go in `~/.claude/settings.json`.
- Skip: `CLAUDE.local.md`, `.claude/rules/*.md`, project-level CLAUDE.md (per the doc's "What NOT to use" section).

---

## 4. Recall Engine (recall-engine.html)

**What it specifies:** 5-stage pipeline (Normalize, Domain Match, Score, Rerank, Handoff),
7 scoring signals, lexical rescue, graph expansion, inverted index reads.

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `brain/engines/recall.py` | Full 5-stage recall pipeline | ~400 |

### 7 scoring signals

| Signal | Cap | Type |
|---|---|---|
| `domain_bonus` | +3.0 | binary |
| `type_bonus` | +1.5 | binary |
| `level_bonus` | L1 +0.5 / L2 +1.5 / L3 +3.0 | tiered |
| `lex_bonus` | +4.0 | continuous (IDF-weighted) |
| `co_ref_bonus` | +2.0 | binary |
| `bundle_bonus` | +1.5 | binary |
| `reuse_bonus` | +2.0 / -0.5 | continuous |

### 3 rerank components

| Component | Cap |
|---|---|
| `specificity` | +2.0 |
| `diversity` | -1.0 per dup |
| `temporal` | -1.5 to +1.0 |

### Dependencies

- Layer 0 (cortex files, inverted-index.json, domain-dictionary.json)
- Layer 1 (binaries for recall-stale, recall-failed, etc.)

### Implementation notes

- Score floor: 2.0
- No top-N truncation -- everything above the floor advances
- Reads `inverted-index.json` and `recall-index.json` (built by Learning Engine Phase 4)
- First run needs a bootstrap: build the inverted index before recall can function

---

## 5. Identity Engine (identity-engine.html)

**What it specifies:** Boot (SessionStart, L1-L4 identity/broca/amygdala) and Relay (per-turn, L1-L3 only),
kernel composition via `claude -p`, scoring with level/recency/strength/relevance/charge bonuses.

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `brain/engines/identity_boot.py` | SessionStart kernel composition | ~200 |
| `brain/engines/identity_relay.py` | Per-turn situational picks | ~200 |

### Boot scoring (3 signals)

| Signal | Formula | Cap |
|---|---|---|
| `level_bonus` | L1 +0.5, L2 +1.5, L3 +3.0, L4 +5.0 | +5.0 |
| `recency_bonus` | +1.0 within 5 cycles, +0.5 within 20 | +1.0 |
| `strength_bonus` | +0.3 per strength point | +2.0 |

Score floor: 1.5.

### Relay scoring (5 signals)

Same 3 as Boot plus:
- `relevance_bonus`: +2.0 if terms overlap message (threshold 0.25)
- `charge_bonus`: +1.0 if amygdala subject matches named person

### Key details

- Boot reads L1-L4. Relay reads L1-L3 only (L4 mirrored from kernel).
- Both use `claude -p --output-format json` via `engines._shared.cli_invoke()`.
- Boot writes `boot-identity.md`. Relay writes `active-identity.json`.

### Dependencies

- Layer 0 (cortex identity/broca/amygdala regions)
- `engines/_shared.py` with `cli_invoke()` (shared infrastructure)
- Layer 1 (binaries for identity-boot-failed, etc.)

---

## 6. Decision Engine (decision-engine.html)

**What it specifies:** 5 hypotheses through 4-D methodology (Deconstruct/Diagnose/Develop/Deliver),
subprocess lifecycle, mutex, schema verification, anti-lockout.

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `brain/engines/decision.py` | Decision skill orchestrator (mutex, spawn, verify) | ~250 |

### The 5 lenses

1. **Literal** -- message text alone (covers over-reading)
2. **Identity-shaped** -- active-identity.json (covers pattern recognition)
3. **Recall-shaped** -- active-recall.json (covers fact-grounded read)
4. **Contrarian** -- adversarial heuristic (covers confirmation bias)
5. **Minimal-action** -- Occam's razor (covers scope creep)

### Lifecycle per turn

```
T0  UserPromptSubmit fires
T1  Mutex acquire (state.json :: active_decision_nonce)
T2  Block parent tools (decision-hypothesis-1..5 = 1)
T3  Spawn Recall + Identity Relay in parallel (Python threads)
T4  Launch Decision subprocess (claude -p with pinned prompt)
T5  Subprocess produces 5 hypotheses, each binary flips 1->0
T6  Schema validation (flip-decision-verify)
T7  Write active-decision.json, release mutex, tools unblock
```

### Dependencies

- Layer 3 (Recall Engine -- must produce active-recall.json first)
- Layer 4 (Identity Engine -- must produce active-identity.json first)
- Layer 1 (binaries, state.json for mutex)
- `engines/_shared.py` with `cli_invoke()`

### Implementation notes

- The pinned system prompt is specified verbatim in the doc. Use it exactly.
- SubagentStop verification: schema check + tool_uses audit.
- Anti-lockout: 3-strike forgiveness, 120s timeout, SessionStart reset.

---

## 7. Learning Engine (learning-engine.html)

**What it specifies:** 8-phase Brain Cycle, synthesis subprocess, eval/hygiene at 30-cycle intervals,
hippocampus management, manually-maintained constants.

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `brain/engines/brain_cycle.py` | Cycle orchestrator (FSM, nonce, invariant checks) | ~200 |
| `brain/engines/cycle_phases.py` | Phase 1-8 implementations | ~800 |
| `brain/engines/learning_helpers.py` | Overlap coefficient, salience, cluster algorithm | ~200 |

### 8 phases

| # | Phase | Frequency | Writes |
|---|---|---|---|
| 1 | Ingest | Every cycle | (in-memory classification) |
| 2 | Hippocampus | Every cycle | hippocampus.md |
| 3 | Consolidate | Every cycle | cortex L1 (new entries, reinforce existing) |
| 4 | Index rebuild | Every cycle | inverted-index.json, recall-index.json |
| 5 | Synthesis | Every cycle | cortex L2/L3 (new synthesized entries), archive sources |
| 6 | Eval | Every 30 cycles | eval-NNNN.json |
| 7 | Hygiene | Every 30 cycles | audit-NNNN.json, decay strengths |
| 8 | Commit | Every cycle | thalamus.json, ledger, git push |

### Manually-maintained constants (thalamus.json :: config)

| Constant | Default |
|---|---|
| L1->L2 strength threshold | 5 |
| L2->L3 strength threshold | 8 |
| Cluster cohesion threshold | 0.4 |
| Cluster size bounds | min 2, max 8 |
| Decay miss-rate floor | 0.80 |
| Decay sample size | 10 |
| Cycle counter gap | 5 messages |
| Eval window | 30 cycles |
| turn_complete retention | 35 cycles |

### Dependencies

- Layer 0-5 (everything -- the cycle touches all regions and reads recall/decision logs)
- `engines/_shared.py` with `cli_invoke()` for synthesis subprocess

### Key details

- Overlap coefficient: `|A ∩ B| / min(|A|, |B|)`
- Eager-trigger: Consolidate runs when hippocampus reaches 80% (40/50)
- Synthesis is NOT a file move -- produces NEW content from clusters
- Archive is append-only under `cortex/archive/<region>/L<n>/`

---

## 8. Brain Skills (skills.html)

**What it specifies:** Brain Retro (session-end sweep), Brain Learn (external source ingestion),
Brain Correct (immediate correction encoding).

**Status: NOT IMPLEMENTED.**

### Files to create

| File | Purpose | LOC estimate |
|---|---|---|
| `~/.claude/skills/brain-retro/SKILL.md` | Skill definition | ~50 |
| `~/.claude/skills/brain-learn/SKILL.md` | Skill definition | ~50 |
| `~/.claude/skills/brain-correct/SKILL.md` | Skill definition | ~50 |
| Subagent verification logic | SubagentStop schema checks | ~100 per skill |

### Skill comparison

| Skill | Trigger | Scope | Writes to | Budget |
|---|---|---|---|---|
| Brain Retro | `/brain-retro` | full session | hippocampus + prefrontal L1 (recurring) | 80 calls / 300s |
| Brain Learn | `/brain-learn <source>` | one external source | hippocampus only | 160 calls / 1800s |
| Brain Correct | `/brain-correct <text>` | one correction | prefrontal L1 directly | 30 calls / 60s |

### Dependencies

- Layer 6 (Learning Engine -- skills feed hippocampus, cycle consolidates)
- Layer 0 (cortex prefrontal for direct rule writes)

---

## Shared infrastructure

### `engines/_shared.py`

Used by Identity Boot, Identity Relay, Decision Engine, and Synthesis.

| Function | Purpose |
|---|---|
| `cli_invoke(system_prompt, user_message)` | Wrapper for `claude -p --output-format json` with `BRAIN_SKIP_HOOKS=1` |
| Entry dataclass | Standard cortex entry with frontmatter parsing |

### Logger API

| Function | Purpose |
|---|---|
| `logger/api.py` | Write functions per engine: `write_recall_log()`, `write_decision_log()`, `write_identity_log()`, `write_learning_log()` |

Logger directories: `recall/`, `decision/`, `identity/`, `identity_boot/`, `identity_relay/`, `handler/`, `learning/`.

---

## Total estimated LOC

| Component | LOC |
|---|---|
| dispatcher.py | ~80 |
| bin_io.py | ~30 |
| flip_tool_guards.py | ~120 |
| flip_bypass.py | ~80 |
| init_binaries.py | ~40 |
| hook.py | ~150 |
| recall.py | ~400 |
| identity_boot.py | ~200 |
| identity_relay.py | ~200 |
| decision.py | ~250 |
| brain_cycle.py | ~200 |
| cycle_phases.py | ~800 |
| learning_helpers.py | ~200 |
| _shared.py | ~100 |
| logger/api.py | ~100 |
| Skill definitions (3) | ~150 |
| **Total** | **~3,100** |

~3,100 LOC across ~16 files.
