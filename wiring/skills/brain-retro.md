---
name: brain-retro
description: Sweep the just-completed session for what worked, what broke, and which corrections recurred. Produces hippocampus entries for the next Brain Cycle to consolidate; writes prefrontal rules directly when a correction is recurring. Triggered by explicit /brain-retro or by Brain Cycle's end-of-session detection.
---

Brain Retro runs at session end to capture the lessons that would otherwise vanish when the chat history rolls off. Three findings categories drive different write paths:

## Findings categories

1. **Worked** — intended outcome achieved with no correction. Reinforce the existing procedural entry that drove the success (strength +1) if one exists; otherwise write a procedural-target hippocampus entry. Successes are evidence; ignoring them is a memory leak.
2. **Broke** — user correction received. Write an episodic-target hippocampus entry capturing the original action, the correction, and the resulting behavior.
3. **Recurring** — same correction or class of correction received N+ times across the session or recent cycles. File a candidate `R1-###` directly to `cortex/prefrontal/L1/` (fresh rule). This bypasses the Brain Cycle's promote-scan because correction-driven rules need to land immediately.

## Run-as-subagent contract

Brain Retro launches a subagent via `claude -p --output-format json`. The subagent reads the session transcript end-to-end, classifies findings, and returns a structured payload (`worked[]`, `broke[]`, `recurring[]`, each with target IDs and source citations).

The SubagentStop hook then runs a single verifier check: the returned payload validates against the Brain Retro schema (required fields, ID format, target region valid, source citations present). On schema fail: payload rejected, no entries land, `retro_verification_failed` log event emitted.

Budget: 80 tool calls / 300 seconds (matches Brain Cycle).

Spec: `Khaan/brain/docs/skills.html` § Brain Retro. Orchestrator: `engines/brain_retro.py::run()`.

## Manual invocation

```bash
python3 -c "import sys; sys.path.insert(0, '/home/ubuntu/.claude/brain'); from engines.brain_retro import run; import json; r = run(); print(json.dumps(r, indent=2) if r else 'retro returned None')"
```

The orchestrator reads `logger/handler/turn_complete.jsonl` for the session transcript and the running cortex for duplicate detection. New entries land in `hippocampus.md` (Broke) and directly under `cortex/prefrontal/L1/` (Recurring); the next Brain Cycle consolidates the hippocampus side.
