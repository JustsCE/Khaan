#!/usr/bin/env bash
set -e

if [ $# -lt 2 ]; then
  echo "Usage: $0 <brain-name> <display-name>"
  echo "Example: $0 norde Norde"
  exit 1
fi

NAME="$1"
DISPLAY="$2"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$REPO/$NAME"

if [ -d "$TARGET" ]; then
  echo "ERROR: $TARGET already exists"
  exit 1
fi

echo "Creating brain '$DISPLAY' at $TARGET..."

# Brain state directories
mkdir -p "$TARGET/brain/binaries"
mkdir -p "$TARGET/brain/cortex"/{semantic,episodic,procedural,fusiform,identity,prefrontal,broca,amygdala}/{L1,L2}
mkdir -p "$TARGET/brain/navigation"
mkdir -p "$TARGET/brain/logger"/{always-on,handler,identity-relay}
mkdir -p "$TARGET/brain/modes"

# Gate binaries — all initialized to 0
BINS=(
  always-on consolidation-pending cycle-empty
  decision-failed decision-hypothesis-1 decision-hypothesis-2
  decision-hypothesis-3 decision-hypothesis-4 decision-hypothesis-5
  decision-source-missing decision-timeout
  identity-boot-failed identity-boot-timeout
  identity-relay-failed identity-relay-timeout
  learning-cycle-failed learning-cycle-overdue
  learning-cycle-running learning-cycle-timeout
  promote-scan-stale recall-dispatch-failed
  recall-failed recall-stale recall-timeout
)
for bin in "${BINS[@]}"; do
  echo -n "0" > "$TARGET/brain/binaries/${bin}.bin"
done

# State files
cat > "$TARGET/brain/state.json" << 'STATEEOF'
{
  "fsm": "NORMAL",
  "message_counter": 0,
  "last_brain_update": 0,
  "active_decision_nonce": null,
  "last_decision_start_ts": 0,
  "decision_consecutive_failures": 0,
  "active_cycle_nonce": null,
  "escalation_count": 0,
  "last_session_start": null,
  "last_transition": null,
  "last_cycle_end_ts": 0,
  "last_cycle_outcome": null,
  "bypass_expiry": {}
}
STATEEOF

cat > "$TARGET/brain/thalamus.json" << THALEOF
{
  "agent_name": "$DISPLAY",
  "cycleCount": 0,
  "nextIds": {
    "H": 1, "S": 1, "E": 1, "PR": 1, "FUS": 1,
    "ID": 1, "BR": 1, "AM": 1, "R": 1
  },
  "schedule": {
    "last_promotion_scan_cycle": 0,
    "last_eval_cycle": 0,
    "last_hygiene_cycle": 0
  },
  "config": {
    "level_thresholds": {"L2": 5, "L3": 8},
    "synthesis": {"cohesion": 0.4, "cluster_size": {"min": 2, "max": 8}},
    "decay": {"miss_rate": 0.8, "sample_size": 10},
    "cycle": {"gap": 15},
    "eval": {"window": 30, "retention": 35}
  }
}
THALEOF

# Boot identity — placeholder
cat > "$TARGET/brain/boot-identity.md" << BOOTEOF
---
kernel_size: 0
kernel_entries: []
source_hashes: {}
situational: "$DISPLAY — session start. Cycle 0."
---
BOOTEOF

echo "# Hippocampus" > "$TARGET/brain/hippocampus.md"

# .gitignore — engines are symlinked, not committed per-brain
echo "engines/" > "$TARGET/brain/.gitignore"

# Wiring
mkdir -p "$TARGET/wiring/skills"
cp "$REPO/wiring/hook.py" "$TARGET/wiring/hook.py"
cp "$REPO/wiring/settings.json" "$TARGET/wiring/settings.json"

cat > "$TARGET/wiring/CLAUDE.md" << CLAUDEEOF
# I am $DISPLAY

I am **$DISPLAY**, a persistent AI agent.

I am omnipresent across sessions. I preserve continuity, reason from memory, execute precisely, and respond with disciplined clarity.

I remain truthful about my environment. I only claim access to files, hooks, machines, binaries, memory systems, or tools AFTER verifying I can actually use them.

On boot, I am provided with additional information about my Identity through additionalContext.

---

## Operating Doctrine

Long-term memory is stored in cortex regions: \`~/.claude/brain/cortex/<region>/L<N>/\`

I gain context-relevant information from my Decision Engine in the form of Hypotheses:
- \`~/.claude/brain/navigation/active-recall.json\`
- \`~/.claude/brain/navigation/active-identity.json\`
- \`~/.claude/brain/navigation/active-decision.json\`

My behavior and decisions are guided by the gates — I DO NOT fight them.
CLAUDEEOF

# Setup script
cat > "$TARGET/setup.sh" << 'SETUPEOF'
#!/usr/bin/env bash
set -e
BRAIN_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$BRAIN_DIR/.." && pwd)"

backup() {
  [ -e "$1" ] && [ ! -L "$1" ] && mv "$1" "$1.bak.$(date +%s)"
}

echo "$(basename "$BRAIN_DIR") setup starting..."
echo "  Brain dir:  $BRAIN_DIR"
echo "  Repo root:  $REPO"

# Engine symlink (engines live in brain/engines/, shared across all brains)
echo "Symlinking engines..."
ln -sfn "$REPO/brain/engines" "$BRAIN_DIR/brain/engines"

# ~/.claude/ wiring
echo "Wiring ~/.claude/..."
backup ~/.claude/brain
backup ~/.claude/hook.py
backup ~/.claude/CLAUDE.md
backup ~/.claude/settings.json

ln -sfn "$BRAIN_DIR/brain"                ~/.claude/brain
ln -sfn "$BRAIN_DIR/wiring/hook.py"       ~/.claude/hook.py
ln -sfn "$BRAIN_DIR/wiring/CLAUDE.md"     ~/.claude/CLAUDE.md
ln -sfn "$BRAIN_DIR/wiring/settings.json" ~/.claude/settings.json

mkdir -p ~/.claude/skills
for f in "$BRAIN_DIR/wiring/skills/"*.md 2>/dev/null; do
  [ -f "$f" ] || continue
  backup ~/.claude/skills/"$(basename "$f")"
  ln -sfn "$f" ~/.claude/skills/"$(basename "$f")"
done

# Verify
echo "Verifying engine import..."
cd "$BRAIN_DIR/brain" && python3 -c "from engines._shared import cli_invoke; print('Engine OK')"

echo ""
echo "$(basename "$BRAIN_DIR") wired successfully. Restart Claude Code to activate."
SETUPEOF
chmod +x "$TARGET/setup.sh"

echo ""
echo "Brain '$DISPLAY' created at $TARGET"
echo ""
echo "Next steps:"
echo "  1. Edit $TARGET/brain/boot-identity.md with identity kernel"
echo "  2. Edit $TARGET/wiring/CLAUDE.md with full identity doc"
echo "  3. Run: $TARGET/setup.sh"
echo "  4. Restart Claude Code"
