#!/usr/bin/env python3
"""
engine.py — Autonomy Engine v1.2 CLI
Usage:
    python engine.py status
    python engine.py triage [--mode solo|joint]
"""

import sys
import json
from pathlib import Path



sys.path.insert(0, str(Path(__file__).parent))
import integrate, recurrence


def cmd_status():
    patterns_path = Path(__file__).parent / "patterns.json"
    charter_path = Path(__file__).parent / "charter.json"

    if patterns_path.exists():
        data = json.loads(patterns_path.read_text())
        n_patterns = len(data.get("patterns", []))
        flagged = sum(1 for p in data.get("patterns", []) if len(p.get("occurrences", [])) >= 3)
    else:
        n_patterns = 0
        flagged = 0

    charter_ok = charter_path.exists()

    print(f"Autonomy Engine v1.2")
    print(f"  Charter:  {'loaded' if charter_ok else 'MISSING'}")
    print(f"  Patterns: {n_patterns} tracked, {flagged} flagged for automation")


def cmd_triage(mode: str = "solo"):
    import sys as _sys
    try:
        raw = _sys.stdin.read()
        tasks = json.loads(raw)
        if isinstance(tasks, dict) and "tasks" in tasks:
            tasks = tasks["tasks"]
    except Exception as e:
        print(f"ERROR: could not parse tasks from stdin: {e}", file=sys.stderr)
        sys.exit(1)

    result = integrate.triage_tasks(tasks, mode=mode)

    total = sum(len(v) for v in result.values())
    print(f"Triage complete — {total} tasks")
    for verdict, entries in result.items():
        if entries:
            print(f"\n  {verdict} ({len(entries)}):")
            for e in entries:
                title = e["task"].get("title", "(no title)")
                print(f"    - {title}")
                print(f"      {e['reason']}")


def main():
    args = sys.argv[1:]
    if not args or args[0] == "status":
        cmd_status()
    elif args[0] == "triage":
        mode = "solo"
        if "--mode" in args:
            idx = args.index("--mode")
            if idx + 1 < len(args):
                mode = args[idx + 1]
        cmd_triage(mode=mode)
    else:
        print(f"Unknown command: {args[0]}")
        print("Usage: engine.py status | triage [--mode solo|joint]")
        sys.exit(1)


if __name__ == "__main__":
    main()
