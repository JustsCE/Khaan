#!/usr/bin/env bash
# Push engine updates to all registered brains.
# Co-located brains use symlinks — changes are instant after git pull.
# Remote brains: SSH + git pull + systemctl restart.
set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BRAINS_FILE="$REPO/kit/brains.json"

if [ ! -f "$BRAINS_FILE" ]; then
  echo "ERROR: $BRAINS_FILE not found"
  exit 1
fi

echo "Pushing engine updates from $REPO/brain/engines/..."

# Read brains from JSON
python3 -c "
import json, sys
brains = json.load(open('$BRAINS_FILE'))['brains']
for b in brains:
    print(f\"{b['id']}|{b['host']}|{b['dir']}|{b['type']}\")
" | while IFS='|' read -r id host dir type; do
  echo ""
  echo "--- Brain: $id ($type) on $host ---"

  if [ "$host" = "localhost" ]; then
    # Co-located: symlink handles it, just verify
    BRAIN_ENGINES="$REPO/$dir/engines"
    if [ -L "$REPO/$dir/../brain/engines" ] 2>/dev/null || [ -L "$REPO/$dir/brain/engines" ] 2>/dev/null; then
      echo "  Symlinked — changes already live"
    else
      echo "  WARNING: $id engines not symlinked"
    fi
  else
    # Remote: SSH + git pull
    echo "  Remote deployment to $host..."
    ssh "$host" "cd ~/Khaan && git pull origin main && echo 'Pull OK'"
    # Restart always-on if running
    ssh "$host" "systemctl restart brain-${id}-always-on 2>/dev/null || echo 'No systemd unit for $id'"
  fi
done

echo ""
echo "Engine push complete."
