# autonomy-invariant

Quick reference. See `SKILL.md` for the full contract.

## What

Verifies every always-on daemon iteration produced a COMS message AND a digest containing the iteration's hash marker. Without these, autonomous work happens but isn't discoverable.

## Two callers

| Caller | Mode | Action on failure |
|--------|------|-------------------|
| `always_on.py` (post-subprocess audit) | `--mode full` | Logs `autonomy_invariant` event with `pass: false` |
| `flip_tool_guards.py` Rule 12 (PreToolUse on `post_digest`) | `--mode coms-only` | Blocks the digest call until COMS posted first |

## CLI test

```bash
# Pretend an iteration ran with hash abc123def456
python3 ~/Khaan/skills/autonomy-invariant/verify.py abc123def456
# → exits 2 (marker not in chat.json or digests.json), prints JSON

python3 ~/Khaan/skills/autonomy-invariant/verify.py abc123def456 --mode coms-only
# → exits 2 (COMS marker absent), prints JSON
```

## Marker format

Agent must include the literal string `ITERHASH-<hash>` in:
- COMS message text (`role=khaan`)
- Digest content (`triggerName="Brain Solo Time"`)

## Files

- `verify.py` — the checker (full + coms-only modes)
- `SKILL.md` — full contract
- `README.md` — this file
