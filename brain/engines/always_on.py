import os, sys, json, time, subprocess, traceback, datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN

GATE = BRAIN / "binaries" / "always-on.bin"
QUEUE = BRAIN / "queue" / "inbox.jsonl"
LOG_DIR = BRAIN / "logger" / "always-on"
TURN_LOG = BRAIN / "logger" / "handler" / "turn_complete.jsonl"
STATE_FILE = BRAIN / "state.json"
CYCLE_RUNNING = BRAIN / "binaries" / "learning-cycle-running.bin"

SELF_PROMPT = "Iterate. Find what matters most. Move on it. If you need to communicate with Justs, use COMS at https://goodhealth.lv/playground — POST to /api/chat with role=khaan. During always-on time, COMS is the ONLY communication channel. Tonight: work on TCG handover tasks. Check COMS for details from Justs."

LIVE_SESSION_WINDOW_S = 90
DECISION_INFLIGHT_WINDOW_S = 120


def gate_on():
    try:
        return GATE.read_text().strip() == "1"
    except Exception:
        return False


def live_session_active():
    if not TURN_LOG.exists():
        return False
    try:
        with open(TURN_LOG) as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 4096))
            tail = [l for l in f.read().splitlines() if l.strip()]
        if not tail:
            return False
        last = json.loads(tail[-1])
        last_ts = last.get("ts", "")
        if not last_ts:
            return False
        t = datetime.datetime.strptime(last_ts, "%Y-%m-%dT%H:%M:%SZ")
        age = (datetime.datetime.utcnow() - t).total_seconds()
        return age < LIVE_SESSION_WINDOW_S
    except Exception:
        return False


def cycle_in_flight():
    try:
        return CYCLE_RUNNING.read_text().strip() == "1"
    except Exception:
        return False


def decision_in_flight():
    if not STATE_FILE.exists():
        return False
    try:
        st = json.loads(STATE_FILE.read_text())
        nonce = st.get("active_decision_nonce")
        if nonce is None:
            return False
        ts = st.get("last_decision_start_ts", 0)
        age = time.time() - ts
        return age < DECISION_INFLIGHT_WINDOW_S
    except Exception:
        return False


def dequeue_one():
    if not QUEUE.exists():
        return None
    lines = [l for l in QUEUE.read_text().splitlines() if l.strip()]
    if not lines:
        return None
    first = lines[0]
    QUEUE.write_text("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""))
    try:
        return json.loads(first)
    except Exception:
        return {"source": "malformed", "prompt": first}


def log_event(event, data):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = LOG_DIR / f"{time.strftime('%Y-%m-%d')}.jsonl"
    with open(p, "a") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "event": event, **data}) + "\n")


def iteration():
    if live_session_active():
        log_event("iteration_skipped", {"reason": "live_session_active"})
        time.sleep(30)
        return
    if cycle_in_flight():
        log_event("iteration_skipped", {"reason": "cycle_in_flight"})
        time.sleep(15)
        return
    if decision_in_flight():
        log_event("iteration_skipped", {"reason": "decision_in_flight"})
        time.sleep(15)
        return

    queued = dequeue_one()
    if queued:
        prompt = queued["prompt"]
        source = queued.get("source", "queue")
    else:
        prompt = SELF_PROMPT
        source = "self"

    t0 = time.time()
    log_event("iteration_start", {"source": source, "prompt": prompt[:200]})

    env = {**os.environ}
    env.pop("BRAIN_SKIP_HOOKS", None)

    try:
        r = subprocess.run(
            ["claude", "-p", "--model", "sonnet"],
            input=prompt, capture_output=True, text=True, env=env
        )
        log_event("iteration_complete", {
            "source": source,
            "latency_ms": int((time.time() - t0) * 1000),
            "exit_code": r.returncode,
            "stdout_chars": len(r.stdout),
            "stderr_chars": len(r.stderr),
        })
    except Exception as e:
        log_event("iteration_failed", {
            "source": source, "latency_ms": int((time.time() - t0) * 1000),
            "reason": str(e)[:500]
        })


def main():
    log_event("daemon_start", {"pid": os.getpid()})
    while True:
        try:
            if not gate_on():
                time.sleep(10)
                continue
            iteration()
        except KeyboardInterrupt:
            log_event("daemon_stop", {"reason": "keyboard_interrupt"})
            return
        except Exception as e:
            log_event("loop_error", {"reason": str(e), "trace": traceback.format_exc()[:1000]})
            time.sleep(30)


if __name__ == "__main__":
    main()
