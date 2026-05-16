---
name: autonomy-invariant
description: Verify a daemon iteration posted required markers to COMS + digests. Used by always_on.py for end-of-iteration audit and by flip_tool_guards.py Rule 12 to mechanically force COMS-before-digest ordering.
type: invariant-check
invoked-by: always_on.py (post-subprocess), flip_tool_guards.py Rule 12 (PreToolUse), or manually via CLI
---

# autonomy-invariant

The autonomy-invariant skill is the post-iteration audit for the always-on daemon. Every autonomous iteration generates an `iteration_hash` (12-char sha256 prefix). The agent must include a marker `ITERHASH-<hash>` in both:

1. A COMS POST (chat.json) with `role=khaan`
2. A digest (digests.json) with `triggerName="Brain Solo Time"`

Without both markers, the iteration is considered an invariant failure — the agent did work but did not leave traceable proof of it.

## Contract

The skill answers two questions:

- **coms-only mode**: did `ITERHASH-<hash>` appear in chat.json with `role=khaan`? Used by Rule 12 to gate `post_digest` calls.
- **full mode**: did the marker appear in both chat.json AND digests.json? Used by always_on.py after subprocess.run completes for the iteration audit.

## CLI

```
python3 ~/Khaan/skills/autonomy-invariant/verify.py <iteration_hash> [--mode full|coms-only]
```

- `--mode full` (default): checks COMS + digest. Returns exit 0 if both pass.
- `--mode coms-only`: checks COMS only. Returns exit 0 if posted.
- Exit 2 if any required channel is missing the marker.
- Always prints a JSON record to stdout suitable for appending to `~/.claude/brain/logger/always-on/<date>.jsonl`.

## Import

```python
from skills.autonomy_invariant.verify import verify
result = verify(iteration_hash, mode="full")
# result = {ts, iteration_hash, mode, coms_posted, coms_ref, [digest_posted, digest_ref], pass}
```

## Data sources

- `chat.json`: `/var/lib/docker/volumes/brain-viz_brain-data/_data/brain/dashboard/chat.json`
- `digests.json`: same directory, `/digests.json`

Both files live inside the brain-viz docker volume. The skill reads them directly via the host mount path. World-readable per the chmod chain set up earlier.

## Failure modes

- File unreadable → returns `coms_ref` or `digest_ref` starting with `error:` and `pass: false`
- Marker absent → `coms_posted` or `digest_posted` is `false` and `pass: false`
- Invalid JSON in files → caught, reported as error, `pass: false`

The skill never raises; it always returns a structured result and an exit code.

## Why this exists

Pattern mirrors the decision engine's `query_hash` verification: the agent must produce output tagged with the same hash that was injected into its prompt. Without that, autonomous iterations are opaque — work happens but isn't discoverable. This skill makes every iteration leave a verifiable trail.
