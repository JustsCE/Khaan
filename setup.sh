#!/usr/bin/env bash
# Brain bootstrap. Run once after cloning the repo.
#
#   git clone <repo>.git ~/<repo>
#   bash ~/<repo>/setup.sh
#
# Symlinks ~/.claude/brain → $REPO/brain and the wiring files in $REPO/wiring/.
# Idempotent; safe to re-run. Existing real files are backed up with .bak.<ts>.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TS="$(date +%s)"
CLAUDE="$HOME/.claude"

echo "Brain bootstrap from $REPO_DIR"

# 1. brain symlink
mkdir -p "$CLAUDE"
if [ -L "$CLAUDE/brain" ]; then
  rm "$CLAUDE/brain"
elif [ -d "$CLAUDE/brain" ]; then
  echo "  backing up $CLAUDE/brain → $CLAUDE/brain.bak.$TS"
  mv "$CLAUDE/brain" "$CLAUDE/brain.bak.$TS"
fi
ln -s "$REPO_DIR/brain" "$CLAUDE/brain"
echo "  brain → $REPO_DIR/brain"

# 2. wiring symlinks (hook.py, CLAUDE.md, settings.json)
for f in hook.py CLAUDE.md settings.json; do
  src="$REPO_DIR/wiring/$f"
  dst="$CLAUDE/$f"
  if [ ! -f "$src" ]; then
    echo "  WARN: missing $src — skipping $f"
    continue
  fi
  if [ -L "$dst" ]; then
    rm "$dst"
  elif [ -f "$dst" ]; then
    echo "  backing up $dst → $dst.bak.$TS"
    mv "$dst" "$dst.bak.$TS"
  fi
  ln -s "$src" "$dst"
  echo "  $f → $src"
done

# 3. skill symlinks
mkdir -p "$CLAUDE/skills"
for src in "$REPO_DIR/wiring/skills/"*.md; do
  [ -f "$src" ] || continue
  name="$(basename "$src")"
  dst="$CLAUDE/skills/$name"
  if [ -L "$dst" ]; then
    rm "$dst"
  elif [ -f "$dst" ]; then
    mv "$dst" "$dst.bak.$TS"
  fi
  ln -s "$src" "$dst"
  echo "  skills/$name → $src"
done

# 4. bypass secret (only if missing)
if [ ! -f "$CLAUDE/.bypass.secret" ]; then
  python3 -c "import secrets; print(secrets.token_hex(32))" > "$CLAUDE/.bypass.secret"
  chmod 0400 "$CLAUDE/.bypass.secret"
  echo "  generated $CLAUDE/.bypass.secret (mode 0400)"
else
  echo "  $CLAUDE/.bypass.secret already exists, leaving alone"
fi

# 5. verify imports resolve
python3 -c "import sys; sys.path.insert(0, '$CLAUDE/brain'); from engines.brain_cycle import run_cycle" \
  && echo "  imports ok" \
  || { echo "  IMPORT FAILED"; exit 1; }

cat <<EOF

Bootstrap complete.

Next:
  Open a fresh Claude Code session — hook.py loads on SessionStart.
  Run \`claude /login\` if OAuth tokens are missing.

To attach a different account/brain:
  bash /path/to/<other-repo>/setup.sh
EOF
