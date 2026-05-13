import os, sys, json, time, secrets, subprocess
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import BRAIN, write_bin, read_state, write_state, file_hash
from engines.cycle_phases import (phase_ingest, phase_hippocampus, phase_consolidate,
                                   phase_index_rebuild, phase_synthesis, phase_eval,
                                   phase_hygiene, phase_commit, _read_thalamus)
from logger.api import write_learning_log

HIPPO = BRAIN / "hippocampus.md"


def _check_timeout(t0):
    if time.time() - t0 > 900:
        raise TimeoutError("cycle exceeded 300s")


def run_cycle():
    thal = _read_thalamus()
    cycle_id = thal["cycleCount"] + 1
    config = thal.get("config", {})
    eval_window = config.get("eval", {}).get("window", 30)

    for attempt in range(3):
        write_learning_log("cycle_start", {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cycle_id": cycle_id,
            "counter_at_start": read_state().get("message_counter", 0)
        })

        write_bin("learning-cycle-running", 1)
        st = read_state()
        st["fsm"] = "CYCLE_RUNNING"
        nonce = secrets.token_hex(16)
        st["active_cycle_nonce"] = nonce
        write_state(st)

        hippo_hash_start = file_hash(HIPPO) if HIPPO.exists() else ""
        t0 = time.time()
        ledger = []

        try:
            observations, l1 = phase_ingest()
            ledger.append(l1)
            _check_timeout(t0)

            l2 = phase_hippocampus(observations)
            ledger.append(l2)
            _check_timeout(t0)

            l3 = phase_consolidate()
            ledger.append(l3)
            _check_timeout(t0)

            l4 = phase_index_rebuild()
            ledger.append(l4)
            _check_timeout(t0)

            l5 = phase_synthesis(cycle_id)
            ledger.append(l5)
            _check_timeout(t0)

            if cycle_id % eval_window == 0:
                l6 = phase_eval(cycle_id)
                ledger.append(l6)
                _check_timeout(t0)
            else:
                ledger.append({"phase": "eval", "executed": False, "detail": "not due"})

            if cycle_id % eval_window == 0:
                l7 = phase_hygiene(cycle_id)
                ledger.append(l7)
                _check_timeout(t0)
            else:
                ledger.append({"phase": "hygiene", "executed": False, "detail": "not due"})

            l8 = phase_commit(cycle_id, ledger, hippo_hash_start, nonce)
            ledger.append(l8)

            # success -- clear escalation and ALL stale failure flags
            write_bin("learning-cycle-overdue", 0)
            write_bin("learning-cycle-running", 0)
            write_bin("learning-cycle-failed", 0)
            write_bin("learning-cycle-timeout", 0)
            write_bin("cycle-empty", 0)
            st = read_state()
            st["escalation_count"] = 0
            st["last_cycle_outcome"] = "success"
            st["fsm"] = "NORMAL"
            write_state(st)
            return ledger

        except TimeoutError:
            write_bin("learning-cycle-timeout", 1)
            write_bin("learning-cycle-overdue", 0)
            write_learning_log("cycle_timeout", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "cycle_id": cycle_id, "latency_ms": int((time.time() - t0) * 1000)
            })
            write_bin("learning-cycle-running", 0)
            st = read_state()
            st["active_cycle_nonce"] = None
            write_state(st)
            return None

        except Exception as e:
            st = read_state()
            esc = st.get("escalation_count", 0) + 1
            st["escalation_count"] = esc
            st["last_cycle_outcome"] = "failed"
            st["active_cycle_nonce"] = None
            write_state(st)

            write_learning_log("cycle_failed", {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "cycle_id": cycle_id, "attempt": attempt + 1, "reason": str(e)
            })

            if esc >= 3:
                write_bin("learning-cycle-failed", 1)
                write_bin("learning-cycle-overdue", 0)
                st["fsm"] = "MAINTENANCE_FAILED"
                write_state(st)
                write_bin("learning-cycle-running", 0)
                return None

            write_bin("learning-cycle-running", 0)
            continue

    write_bin("learning-cycle-overdue", 0)
    write_bin("learning-cycle-running", 0)
    return None
