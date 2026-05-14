import os, sys
sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import read_bin, write_bin, read_state, write_state

LEARNING_BINS = [
    "learning-cycle-overdue", "learning-cycle-running", "learning-cycle-failed",
    "learning-cycle-timeout", "consolidation-pending", "promote-scan-stale", "cycle-empty"
]


def check_overdue():
    # anti-lockout: if failed/timeout, clear all learning bins, return False
    if read_bin("learning-cycle-failed") == 1 or read_bin("learning-cycle-timeout") == 1:
        for b in LEARNING_BINS:
            write_bin(b, 0)
        st = read_state()
        st["escalation_count"] = 0
        write_state(st)
        return False

    st = read_state()
    gap = st.get("message_counter", 0) - st.get("last_brain_update", 0)
    if gap >= 10:
        write_bin("learning-cycle-overdue", 1)
        if st.get("fsm") == "NORMAL":
            st["fsm"] = "MAINTENANCE_DUE"
            write_state(st)
        return True
    return False
