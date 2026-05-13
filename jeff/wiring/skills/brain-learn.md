---
name: brain-learn
description: Extract observations from an external source (PDF, URL, transcript, message thread, file) and stage them in hippocampus for the next Brain Cycle to consolidate. Iterative — present the batch to the user, accept surgical corrections, then commit. Triggered by explicit /brain-learn <source>.
args: <source>
---

Brain Learn ingests one external artefact per invocation. The output is `H###` entries in `hippocampus.md` tagged `source=brain-learn`; the next Brain Cycle promotes them through the normal consolidation pipeline. (Reading the current conversation is the Brain Retro skill's job, not this one.)

## Procedure

1. **Read the source. Plan first.** If multi-part, segment into manageable chunks. Non-trivial extractions enter plan mode — the plan lists what is being extracted, from where, with what confidence. The user approves before observations land.
2. **Extract candidate observations.** Per chunk, classify each by memory category and assign salience. Every observation cites a span of the source. Unknowns marked `TBD`, never invented. Surface contradictions; do not pick a side silently.
3. **Match against existing cortex.** Compute the overlap coefficient (same formula as Brain Cycle Phase 3). Pre-flag duplicates and reinforce-candidates.
4. **Present the batch. Iterate, not one-shot.** Show the staged observations. Wait for reaction.
5. **Apply pushback as surgical edits.** Edit only the observations the user calls out. Wholesale rewrites are signal violations.
6. **Verify before commit.** Grep the batch for fabricated IDs, ungrounded claims, missing source spans. Fix before promoting.
7. **Promote, then encode lessons.** Write verified observations to `hippocampus.md` tagged `source=brain-learn`. If the same correction lands N+ times across batches, file a prefrontal rule via the Brain Retro mechanism.
8. **Honesty over narrative.** If extraction confidence is low, say so in entry frontmatter. Don't paper over uncertainty with confident prose.

## Run-as-subagent contract

Subagent runs as `claude -p --output-format json`. SubagentStop verifies: every observation has id, target category, salience, source-span citation. On schema fail: no entries land, `learn_verification_failed` log event emitted.

Budget: 160 tool calls / 1800 seconds (up to 30 minutes for deep extractions).

Spec: `brain/docs/skills.html` § Brain Learn. Orchestrator: `engines/brain_learn.py::run(source)`.

## Manual invocation

```bash
python3 -c "import sys; sys.path.insert(0, '~/.claude/brain'); from engines.brain_learn import run; import json; r = run('$ARGUMENTS'); print(json.dumps(r, indent=2) if r else 'learn returned None')"
```

`$ARGUMENTS` is the source — a file path, URL, transcript ID, or quoted content string. Per-batch manifest persists at `logger/learning/learn-<source-hash>.json`.
