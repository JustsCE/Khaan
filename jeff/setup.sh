#!/usr/bin/env bash
set -e
JEFF="$(cd "$(dirname "$0")" && pwd)"   # jeff/ dir
REPO="$(cd "$JEFF/.." && pwd)"          # repo root

backup() {
  [ -e "$1" ] && [ ! -L "$1" ] && mv "$1" "$1.bak.$(date +%s)"
}

echo "Jeff setup starting..."
echo "  Jeff dir:  $JEFF"
echo "  Repo root: $REPO"

# --- Engine symlink (engines live in brain/engines/, not committed to jeff/brain/) ---
echo "Symlinking engines..."
ln -sfn "$REPO/brain/engines" "$JEFF/brain/engines"

# --- ~/.claude/ wiring ---
echo "Wiring ~/.claude/..."
backup ~/.claude/brain
backup ~/.claude/hook.py
backup ~/.claude/CLAUDE.md
backup ~/.claude/settings.json

ln -sfn "$JEFF/brain"                ~/.claude/brain
ln -sfn "$JEFF/wiring/hook.py"       ~/.claude/hook.py
ln -sfn "$JEFF/wiring/CLAUDE.md"     ~/.claude/CLAUDE.md
ln -sfn "$JEFF/wiring/settings.json" ~/.claude/settings.json

mkdir -p ~/.claude/skills
for f in "$JEFF/wiring/skills/"*.md; do
  backup ~/.claude/skills/"$(basename "$f")"
  ln -sfn "$f" ~/.claude/skills/"$(basename "$f")"
done

# --- Verify ---
echo "Verifying engine import..."
cd "$JEFF/brain" && python3 -c "from engines.brain_cycle import run_cycle; print('Jeff engine OK')"

echo ""
echo "Jeff wired successfully. Restart Claude Code to activate."
