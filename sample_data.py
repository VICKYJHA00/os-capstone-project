"""
sample_data.py
==============
Built-in textbook workloads used by the demo, the test suite and the
sample runs in the report.

Workload A -- the classic 5-process set used in OS laboratory manuals:

    PID   Arrival   Burst   Priority
    P1       0        10        3
    P2       1         5        1
    P3       3         2        4
    P4       5         6        2
    P5       8         3        5

Reference string A (10 references) -- the example from the lab manual:
    7 0 1 2 0 3 0 4 2 3

Reference string B (20 references) -- the classic demand-paging example
(Silberschatz, Operating System Concepts):
    7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1
    With 3 frames: FIFO = 15 faults, LRU = 12 faults, Optimal = 9 faults.
"""

from scheduler import Process

SAMPLE_PROCESSES = [
    Process("P1", 0, 10, 3),
    Process("P2", 1, 5, 1),
    Process("P3", 3, 2, 4),
    Process("P4", 5, 6, 2),
    Process("P5", 8, 3, 5),
]

SAMPLE_REF_SHORT = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3]

SAMPLE_REF_LONG = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]

# Defaults used across the application
DEFAULT_QUANTUM = 4          # Round Robin time quantum
DEFAULT_FRAMES = 3           # frames for standalone page replacement
INTEGRATED_QUANTUM = 4       # integrated simulation defaults
INTEGRATED_FRAMES = 4
INTEGRATED_PAGES_PER_PROCESS = 3
THRASHING_MAX_FRAMES = 10    # thrashing analysis sweep limit


def describe_processes(processes) -> str:
    """One-line summary of a process workload (for menu status lines)."""
    if not processes:
        return "no processes loaded"
    if len(processes) == 1:
        return "1 process (%s)" % processes[0].pid
    return "%d processes (%s..%s)" % (len(processes), processes[0].pid,
                                      processes[-1].pid)
