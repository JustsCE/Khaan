---
name: decision-engine
description: Compose 5 hypotheses about user intent through fixed lenses (Literal, Identity-shaped, Recall-shaped, Contrarian, Minimal-action). Auto-invoked on every UserPromptSubmit by hook.py. Spawns Recall + Identity Relay in parallel, runs Decision subprocess via claude -p, verifies the returned envelope, writes navigation/active-decision.json.
---

The Decision Engine produces a 5-hypothesis assessment of what the user needs, per turn. It does not pick a lens — the parent picks based on live chat context the subprocess does not have.

This skill is auto-invoked by the UserPromptSubmit hook handler. Manual invocation is supported for debugging the dispatch pipeline against a specific input string.

## Pipeline (per turn)

1. Mutex acquire on `state.json :: active_decision_nonce` (240s wait, 250ms poll, exit clean if exceeded).
2. Spawn Recall + Identity Relay as Python threads. Each writes its `navigation/active-*.json` for THIS turn. Join both threads before continuing.
3. Spawn Decision subprocess via `engines._shared.cli_invoke()` with the pinned SYSTEM_PROMPT.
4. Run `flip-decision-verify` on the returned envelope: 5 hypotheses present, lens labels match canonical order, source hashes match, query_hash matches, tool_uses include Reads of every cited evidence ID.
5. On pass: write `navigation/active-decision.json`, clear `decision-hypothesis-{1..5}` bins, release mutex.
   On fail: increment strike counter; retry up to 3 times; after 3 strikes raise `decision-failed.bin = 1`. Anti-lockout clears it on the next UserPromptSubmit.
6. Mutex release in `finally`.

Spec: `brain/docs/decision-engine.html`. Orchestrator code: `engines/decision.py::dispatch()`.

## Manual invocation

```bash
python3 -c "import sys; sys.path.insert(0, '~/.claude/brain'); from engines.decision import dispatch; import json; r = dispatch('$ARGUMENTS'); print(json.dumps(r, indent=2) if r else 'decision pipeline returned None')"
```

Manual invocation is mostly for debugging — the UserPromptSubmit hook already runs the pipeline on every turn. If `active-decision.json` is missing or stale, run this skill against the most recent user message to reproduce the failure.
