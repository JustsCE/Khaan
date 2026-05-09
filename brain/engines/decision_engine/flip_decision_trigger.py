import sys, os
sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".claude", "brain"))
from engines._shared import write_bin


def trigger():
    for i in range(1, 6):
        write_bin(f"decision-hypothesis-{i}", 1)
    return True
