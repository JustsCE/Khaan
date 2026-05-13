---
name: brain-cycle
description: Run the 8-phase Brain Cycle consolidation. Auto-triggered when learning-cycle-overdue fires (counter gap >= 5 messages) — until the cycle commits, every tool except this skill is blocked. May also be invoked manually for an on-demand consolidation pass.
---

The Brain Cycle is the periodic consolidation pass that turns chat observations into long-term memory. It is non-negotiable: while `learning-cycle-overdue.bin = 1`, the parent's tool gate blocks every tool except `/brain-cycle`. The cycle must commit before the brain can act again.

## Phases (in order)

1. **Ingest** — walk the chat transcript since the last cycle, classify each candidate observation into one of 8 memory categories with a salience 0.0–1.0.
2. **Hippocampus** — write each ingested observation as an `H###` entry to `hippocampus.md`. Cap 50; drop lowest-salience pending at cap.
3. **Consolidate** — overlap-coefficient match each `H###` against existing entries: ≥0.5 reinforces, 0.25–0.5 reviews, <0.25 promotes new L1 if salience ≥0.5 else discards.
4. **Index rebuild** — rebuild `navigation/inverted-index.json` and `navigation/recall-index.json` from current cortex state, including IDF weights and per-entry access counters.
5. **Synthesis** — cluster L1 entries at strength ≥5 and L2 entries at strength ≥8 (cohesion ≥0.4, size 2–8); distil each cluster into a new higher-level entry; archive sources to `cortex/archive/<region>/L<n>/`.
6. **Eval** (every 30 cycles) — compute per-entry miss-rate from recall + decision + turn_complete logs over the last 30 cycles; write `logger/learning/eval-NNNN.json`.
7. **Hygiene** (every 30 cycles) — decay entries with miss-rate >0.80 over 10+ qualified recalls; log integrity findings to `logger/learning/audit-NNNN.json`.
8. **Commit** — increment `thalamus.cycleCount`, write the ledger, `git add && git commit && git push`.

Budget: 80 tool calls / 300 seconds. Past either, `learning-cycle-timeout.bin = 1`. Three consecutive cycle failures → `learning-cycle-failed.bin = 1`. Both clear on the next `UserPromptSubmit` (anti-lockout).

Spec: `brain/docs/learning-engine.html` § Brain Cycle. Orchestrator: `engines/brain_cycle.py::run_cycle()`. Phase implementations: `engines/cycle_phases.py`.

## Manual invocation

```bash
python3 -c "import sys; sys.path.insert(0, '~/.claude/brain'); from engines.brain_cycle import run_cycle; import json; r = run_cycle(); print(json.dumps(r, indent=2) if r else 'cycle returned None (timeout or 3-strike failure)')"
```

The auto-trigger handles the normal case. Manual invocation is for forcing a consolidation pass after large changes (Brain Learn batch, manual cortex edits) before the next gap-of-5 would naturally fire one.
