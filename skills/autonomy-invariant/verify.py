#!/usr/bin/env python3
"""
autonomy-invariant — verify daemon iteration produced traceable markers.

Usage:
  python3 verify.py <iteration_hash> [--mode full|coms-only]

Exit codes:
  0 — invariants pass
  2 — invariants fail
  1 — usage error

Always emits a single-line JSON record on stdout.
"""
import json
import sys
import time
import argparse
from pathlib import Path

CHAT = Path("/var/lib/docker/volumes/brain-viz_brain-data/_data/brain/dashboard/chat.json")
DIGESTS = Path("/var/lib/docker/volumes/brain-viz_brain-data/_data/brain/dashboard/digests.json")


def check_coms(marker):
    """Return (found, msg_id_or_error_str)."""
    try:
        chat = json.loads(CHAT.read_text())
        for m in chat:
            if m.get("role") == "khaan" and marker in (m.get("text") or ""):
                return True, m.get("id")
    except Exception as e:
        return False, f"error: {str(e)[:80]}"
    return False, None


def check_digest(marker):
    """Return (found, digest_id_or_error_str)."""
    try:
        raw = json.loads(DIGESTS.read_text())
        items = raw if isinstance(raw, list) else raw.get("digests", [])
        for d in items:
            if marker in json.dumps(d):
                return True, d.get("id")
    except Exception as e:
        return False, f"error: {str(e)[:80]}"
    return False, None


def verify(iter_hash, mode="full"):
    marker = f"ITERHASH-{iter_hash}"
    coms_ok, coms_ref = check_coms(marker)
    result = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "autonomy_invariant",
        "iteration_hash": iter_hash,
        "mode": mode,
        "coms_posted": coms_ok,
        "coms_ref": coms_ref,
    }
    if mode == "coms-only":
        result["pass"] = bool(coms_ok)
    else:
        digest_ok, digest_ref = check_digest(marker)
        result["digest_posted"] = digest_ok
        result["digest_ref"] = digest_ref
        result["pass"] = bool(coms_ok) and bool(digest_ok)
    return result


def main():
    ap = argparse.ArgumentParser(description="Verify autonomy invariants for a daemon iteration.")
    ap.add_argument("iteration_hash", help="12-char iteration hash (without ITERHASH- prefix)")
    ap.add_argument("--mode", choices=["full", "coms-only"], default="full",
                    help="full = COMS + digest, coms-only = COMS only (Rule 12)")
    args = ap.parse_args()

    r = verify(args.iteration_hash, args.mode)
    print(json.dumps(r))
    sys.exit(0 if r["pass"] else 2)


if __name__ == "__main__":
    main()
