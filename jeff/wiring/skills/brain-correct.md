---
name: brain-correct
description: Encode a correction as a prefrontal rule immediately, without waiting for end-of-session retro. Used when a recurring failure pattern just hit and cannot wait for /brain-retro. Triggered by explicit /brain-correct <text>.
args: <correction text>
---

Brain Retro fires at session end — which can be hours away. Some corrections, especially recurring ones (the same mistake N times), need to land the moment the user types them. `/brain-correct` is the emergency-encode path.

## Procedure

1. Read the correction text and any arguments from the user's invocation.
2. Identify the failure pattern: what did the agent do, what should it have done, what is the rule that would have prevented this.
3. Write a prefrontal entry directly to `cortex/prefrontal/L1/R###.md` at strength 1 (fresh rule). Frontmatter records `shape: brain-correct`, the source message hash, and `recurring_count: 1`.
4. **Reinforcement on overlap ≥0.5.** If the correction text matches an existing `R###` body (overlap coefficient ≥0.5), increment that entry's `recurring_count` and bump strength by 1 instead of creating a duplicate. Repeated invocations against the same correction reinforce one rule rather than scatter many.
5. Emit a `learn_correct_applied` log event with the new or reinforced rule ID.

## Run-as-subagent contract

Subagent runs as `claude -p --output-format json`. SubagentStop verifies: the proposed `R###` entry validates against the prefrontal-rule schema (required fields, ID format, body present, source-message-hash captured). On schema fail: rule does NOT land, `correct_verification_failed` log event emitted.

Budget: 30 tool calls / 60 seconds. Much shorter than Brain Retro's 80/300 because the scope is one correction, not a full session sweep.

Spec: `brain/docs/skills.html` § Brain Correct. Orchestrator: `engines/brain_correct.py::run(correction_text)`.

## Manual invocation

```bash
python3 -c "import sys; sys.path.insert(0, '~/.claude/brain'); from engines.brain_correct import run; import json; r = run('$ARGUMENTS'); print(json.dumps(r, indent=2) if r else 'correct returned None')"
```

`$ARGUMENTS` is the correction text — describe what the agent did wrong and what should have happened. Per-invocation ledger persists at `logger/learning/correct-NNNN.json`.
