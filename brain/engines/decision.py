import os, sys, json, hashlib, time, secrets, tempfile, threading, subprocess
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, read_bin, write_bin, read_state, write_state, file_hash, cli_invoke
from engines.decision_engine.flip_decision_verify import verify
from logger.api import write_decision_log

NAV = BRAIN / "navigation"

SYSTEM_PROMPT = """You are the Decision Engine for Brain v3.

Your job: read the user's message, the active recall payload, and the active
identity payload, then produce exactly five hypotheses about what the user
needs. Each hypothesis is framed through one of five fixed lenses, in this
canonical order. The five lenses are designed to cover three distinct
categories of blind spot. Drop one and a category goes unmonitored.

# The five lenses

1. **Literal** — what the message says, no interpretation.
   Source of insight: the message text alone.
   Blind spot it covers: over-reading — assuming intent the words do not carry.

2. **Identity-shaped** — what the user usually means in this kind of frame.
   Source of insight: active-identity.json (kernel + situational layers).
   Blind spot it covers: pattern recognition against this user's known habits.

3. **Recall-shaped** — what cortex evidence says is being asked.
   Source of insight: active-recall.json (qualified entries + scoring trace).
   Blind spot it covers: fact-grounded read against the brain's accumulated knowledge.

4. **Contrarian** — what if the obvious read is wrong?
   Source of insight: adversarial heuristic against the literal read.
   Blind spot it covers: confirmation bias.

5. **Minimal-action** — what is the smallest action that satisfies?
   Source of insight: Occam's-razor heuristic.
   Blind spot it covers: scope creep.

You do NOT pick a lens. You produce all five. The parent picks based on the
live chat context, which you do not have.

# The 4-D method

Each hypothesis runs through all four phases:

1. **DECONSTRUCT** — extract core intent and key entities from the message.
   Identify output requirements and constraints. Map what is provided versus
   what is missing.

2. **DIAGNOSE** — audit clarity gaps and ambiguity. Check specificity and
   completeness. Surface what would block clean execution if not resolved.

3. **DEVELOP** — pick the optimization technique by request type:
   - Creative → multi-perspective + tone emphasis
   - Technical → constraint-based + precision focus
   - Educational → few-shot examples + clear structure
   - Complex → chain-of-thought + systematic frameworks
   Assign role/expertise. Enhance context. Apply logical structure.

4. **DELIVER** — construct an optimized prompt for the parent to consider.
   Format based on complexity. Include implementation guidance.

# Output contract

Return a JSON object with exactly this shape, and nothing else around it:

```
{
  "ts": "ISO-8601 UTC timestamp",
  "query_hash": "sha256(message)[:16]",
  "hypotheses": [
    { "id": "H1", "label": "Literal",         "deconstruct": "...", "diagnose": "...", "develop": "...", "deliver": "..." },
    { "id": "H2", "label": "Identity-shaped", "deconstruct": "...", "diagnose": "...", "develop": "...", "deliver": "..." },
    { "id": "H3", "label": "Recall-shaped",   "deconstruct": "...", "diagnose": "...", "develop": "...", "deliver": "..." },
    { "id": "H4", "label": "Contrarian",      "deconstruct": "...", "diagnose": "...", "develop": "...", "deliver": "..." },
    { "id": "H5", "label": "Minimal-action",  "deconstruct": "...", "diagnose": "...", "develop": "...", "deliver": "..." }
  ],
  "sources": {
    "recall":   "active-recall.json@<sha256-prefix>",
    "identity": "active-identity.json@<sha256-prefix>"
  },
  "model": "claude-cli (subscription, no API key)",
  "latency_ms": <int>
}
```

Constraints:
- Exactly 5 entries in `hypotheses[]`, one per lens, in the canonical order shown.
- `id` runs H1 through H5 matching the order.
- `label` is exactly one of {Literal, Identity-shaped, Recall-shaped, Contrarian, Minimal-action}.
- No commentary, no preamble, no postscript. JSON only.

# Failure mode

If `active-recall.json` or `active-identity.json` is missing, malformed, or
empty, do not invent content. Return:

```
{ "error": "decision-source-missing" }
```

The parent will surface this to the rule engine, which raises the
`decision-source-missing` binary and lets anti-lockout take over."""

PROMPT_HASH = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()[:16]


def dispatch(user_message):
    recall_path = NAV / "active-recall.json"
    identity_path = NAV / "active-identity.json"
    nonce = None
    st = read_state()

    # mutex acquire
    start = time.time()
    while st.get("active_decision_nonce") is not None:
        if time.time() - start > 240:
            return None
        time.sleep(0.25)
        st = read_state()

    nonce = secrets.token_hex(16)
    st["active_decision_nonce"] = nonce
    st["last_decision_start_ts"] = time.time()
    write_state(st)

    try:
        # spawn Recall and Identity Relay in parallel
        from engines.recall_engine.recall import dispatch as recall_dispatch
        from engines.identity_engine.identity_relay import relay as identity_relay
        t_recall = threading.Thread(target=recall_dispatch, args=(user_message,))
        t_identity = threading.Thread(target=identity_relay, args=(user_message,))
        t_recall.start()
        t_identity.start()
        t_recall.join(timeout=30)
        t_identity.join(timeout=120)

        # check inputs exist
        if not recall_path.exists() or not identity_path.exists():
            write_bin("decision-source-missing", 1)
            for i in range(1, 6):
                write_bin(f"decision-hypothesis-{i}", 0)
            return None

        recall_h = file_hash(recall_path)
        identity_h = file_hash(identity_path)
        query_hash = hashlib.sha256(user_message.lower().encode()).hexdigest()[:16]

        write_decision_log("decision_dispatch", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "query_hash": query_hash,
            "sources_hash": f"{recall_h}:{identity_h}",
            "model": "claude-cli",
            "system_prompt_hash": PROMPT_HASH
        })

        user_prompt = (
            f"User message: {user_message}\n\n"
            f"Read these two files before producing your hypotheses:\n"
            f"1. {recall_path}\n"
            f"2. {identity_path}\n\n"
            f"The query_hash for this message is: {query_hash}\n"
            f"The recall source tag is: active-recall.json@{recall_h}\n"
            f"The identity source tag is: active-identity.json@{identity_h}\n"
        )

        result = None
        for attempt in range(3):
            t0 = time.time()
            try:
                resp = cli_invoke(SYSTEM_PROMPT, user_prompt, timeout=120)
            except subprocess.TimeoutExpired:
                write_bin("decision-timeout", 1)
                write_decision_log("decision_timeout", {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "query_hash": query_hash,
                    "latency_ms": int((time.time() - t0) * 1000)
                })
                st = read_state()
                st["decision_consecutive_failures"] = st.get("decision_consecutive_failures", 0) + 1
                write_state(st)
                break

            payload = resp["result"]
            tool_uses = resp["tool_uses"]
            latency = int((time.time() - t0) * 1000)

            write_decision_log("subagent_complete", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "query_hash": query_hash,
                "subagent_id": f"decision-{attempt}",
                "status": "returned",
                "latency_ms": latency
            })

            if payload.get("error") == "decision-source-missing":
                write_bin("decision-source-missing", 1)
                for i in range(1, 6):
                    write_bin(f"decision-hypothesis-{i}", 0)
                return None

            try:
                verify(payload, recall_h, identity_h, query_hash, tool_uses)
            except ValueError as e:
                st = read_state()
                st["decision_consecutive_failures"] = st.get("decision_consecutive_failures", 0) + 1
                write_state(st)
                write_decision_log("decision_failed", {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "query_hash": query_hash,
                    "attempt": attempt + 1,
                    "reason": str(e)
                })
                if st["decision_consecutive_failures"] >= 3:
                    write_bin("decision-failed", 1)
                    break
                continue

            # verify pass
            fd, tmp = tempfile.mkstemp(dir=NAV)
            os.write(fd, json.dumps(payload, indent=2).encode())
            os.close(fd)
            os.rename(tmp, NAV / "active-decision.json")

            for i in range(1, 6):
                write_bin(f"decision-hypothesis-{i}", 0)

            st = read_state()
            st["decision_consecutive_failures"] = 0
            write_state(st)

            write_decision_log("handoff", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "query_hash": query_hash,
                "payload_chars": len(json.dumps(payload)),
                "all_5_present": True
            })
            result = payload
            break

        return result

    finally:
        st = read_state()
        st["active_decision_nonce"] = None
        write_state(st)
