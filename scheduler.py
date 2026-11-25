"""
scheduler.py
============
CPU scheduling algorithms for the Integrated CPU Scheduling + Virtual
Memory Simulator (OS Capstone Project).

Implements four textbook scheduling policies over a validated set of
processes:

    1. First-Come First-Served (FCFS)      -- non-preemptive
    2. Shortest Job First (SJF)            -- non-preemptive
    3. Priority Scheduling (1 = highest)   -- non-preemptive
    4. Round Robin (RR)                    -- preemptive, configurable quantum

Every algorithm returns a ScheduleResult containing:

    gantt   : list of Segment(pid, start, end); pid is None for CPU idle time
    records : list of ProcRecord with start_time / completion filled in,
              from which Turnaround, Waiting and Response times are derived.

Formulas used throughout (standard OS textbook definitions):

    Turnaround Time (TAT) = Completion Time - Arrival Time
    Waiting Time    (WT)  = Turnaround Time - Burst Time
    Response Time   (RT)  = First dispatch time - Arrival Time

Input is expected to be already validated (see validation.validate_processes).
"""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Callable, List, Optional

# --------------------------------------------------------------------------- #
#  Data structures
# --------------------------------------------------------------------------- #


@dataclass
class Process:
    """A process description as supplied by the user (already validated)."""
    pid: str
    arrival: int
    burst: int
    priority: int = 1


@dataclass
class Segment:
    """One contiguous CPU allocation on the Gantt timeline.

    pid is None when the CPU sits idle waiting for the next arrival.
    """
    pid: Optional[str]
    start: int
    end: int

    @property
    def duration(self) -> int:
        return self.end - self.start

    @property
    def is_idle(self) -> bool:
        return self.pid is None


@dataclass
class ProcRecord:
    """Per-process timing information produced by a scheduling algorithm."""
    pid: str
    arrival: int
    burst: int
    priority: int
    start_time: Optional[int] = None    # first time the process gets the CPU
    completion: Optional[int] = None    # time the process finishes

    @property
    def turnaround(self) -> int:
        """TAT = Completion - Arrival."""
        return self.completion - self.arrival

    @property
    def waiting(self) -> int:
        """WT = Turnaround - Burst."""
        return self.turnaround - self.burst

    @property
    def response(self) -> int:
        """RT = first dispatch - Arrival."""
        return self.start_time - self.arrival


@dataclass
class ScheduleResult:
    """Everything a scheduling algorithm produces."""
    algorithm: str
    gantt: List[Segment]
    records: List[ProcRecord]

    def record(self, pid: str) -> ProcRecord:
        for r in self.records:
            if r.pid == pid:
                return r
        raise KeyError("unknown pid: %s" % pid)

    @property
    def makespan(self) -> int:
        """Total elapsed time of the schedule (end of the last segment)."""
        return self.gantt[-1].end if self.gantt else 0


_PID_RE = re.compile(r"^([A-Za-z]*)(\d+)$")


def pid_sort_key(pid: str):
    """Natural sort key so that P2 comes before P10."""
    m = _PID_RE.match(pid)
    if m:
        return (0, m.group(1), int(m.group(2)), "")
    return (1, "", 0, pid)


# --------------------------------------------------------------------------- #
#  Non-preemptive engine (FCFS / SJF / Priority share this skeleton)
# --------------------------------------------------------------------------- #


def _non_preemptive(processes: List[Process], name: str,
                    key: Callable[[ProcRecord], tuple]) -> ScheduleResult:
    """Run a non-preemptive scheduler.

    `key` picks the next process among those that have already arrived:
        FCFS     -> (arrival, pid)
        SJF      -> (burst, arrival, pid)
        Priority -> (priority, arrival, pid)
    If no process has arrived yet the CPU idles until the next arrival.
    """
    pending = [ProcRecord(p.pid, p.arrival, p.burst, p.priority)
               for p in processes]
    gantt: List[Segment] = []
    time = 0

    while pending:
        available = [p for p in pending if p.arrival <= time]
        if not available:                       # CPU must idle for a while
            nxt = min(p.arrival for p in pending)
            gantt.append(Segment(None, time, nxt))
            time = nxt
            continue

        chosen = min(available, key=key)
        chosen.start_time = time
        gantt.append(Segment(chosen.pid, time, time + chosen.burst))
        time += chosen.burst
        chosen.completion = time
        pending.remove(chosen)

    records = sorted((r for r in _all_records(processes, gantt)),
                     key=lambda r: pid_sort_key(r.pid))
    return ScheduleResult(name, gantt, records)


def _all_records(processes: List[Process],
                 gantt: List[Segment]) -> List[ProcRecord]:
    """Rebuild ProcRecords (with start/completion) from the Gantt segments.

    Used by the non-preemptive engine; the Round Robin engine fills the
    records directly while it runs.
    """
    by_pid = {p.pid: ProcRecord(p.pid, p.arrival, p.burst, p.priority)
              for p in processes}
    for seg in gantt:
        if seg.is_idle:
            continue
        rec = by_pid[seg.pid]
        if rec.start_time is None:
            rec.start_time = seg.start
        rec.completion = seg.end          # updated for each (single) segment
    return list(by_pid.values())


# --------------------------------------------------------------------------- #
#  The four scheduling algorithms
# --------------------------------------------------------------------------- #


def fcfs(processes: List[Process]) -> ScheduleResult:
    """First-Come First-Served: run processes in arrival order."""
    return _non_preemptive(processes, "FCFS",
                           lambda r: (r.arrival, pid_sort_key(r.pid)))


def sjf(processes: List[Process]) -> ScheduleResult:
    """Shortest Job First (non-preemptive): among the arrived processes
    pick the one with the smallest burst time."""
    return _non_preemptive(processes, "SJF (non-preemptive)",
                           lambda r: (r.burst, r.arrival, pid_sort_key(r.pid)))


def priority_scheduling(processes: List[Process]) -> ScheduleResult:
    """Priority scheduling (non-preemptive).  Priority 1 is the HIGHEST
    priority; ties are broken by arrival time, then by PID."""
    return _non_preemptive(processes, "Priority (1 = highest)",
                           lambda r: (r.priority, r.arrival,
                                      pid_sort_key(r.pid)))


def round_robin(processes: List[Process], quantum: int = 4) -> ScheduleResult:
    """Round Robin (preemptive).

    Standard textbook behaviour:
      * a ready FIFO queue is used;
      * every process runs for at most `quantum` time units;
      * processes that arrive while another process is executing enter the
        queue BEFORE the preempted process is re-queued;
      * if the queue is empty the CPU idles until the next arrival.
    """
    arrivals = sorted(processes, key=lambda p: (p.arrival, pid_sort_key(p.pid)))
    records = {p.pid: ProcRecord(p.pid, p.arrival, p.burst, p.priority)
               for p in processes}
    remaining = {p.pid: p.burst for p in processes}
    queue: deque = deque()
    gantt: List[Segment] = []
    time = 0
    i = 0                                   # next arrival not yet queued
    n = len(arrivals)

    def feed(now: int) -> None:
        """Enqueue every process that has arrived by `now`."""
        nonlocal i
        while i < n and arrivals[i].arrival <= now:
            queue.append(arrivals[i].pid)
            i += 1

    feed(time)
    while any(r > 0 for r in remaining.values()):
        if not queue:
            nxt = arrivals[i].arrival       # safe: an unfinished process
            gantt.append(Segment(None, time, nxt))   # is either queued or
            time = nxt                      # still to arrive
            feed(time)
            continue

        pid = queue.popleft()
        rec = records[pid]
        if rec.start_time is None:
            rec.start_time = time

        run = min(quantum, remaining[pid])
        gantt.append(Segment(pid, time, time + run))
        time += run
        remaining[pid] -= run

        feed(time)                          # new arrivals enter first ...
        if remaining[pid] > 0:
            queue.append(pid)               # ... then the preempted process
        else:
            rec.completion = time

    ordered = sorted(records.values(), key=lambda r: pid_sort_key(r.pid))
    return ScheduleResult("Round Robin (q=%d)" % quantum, gantt, ordered)


def run_all(processes: List[Process], quantum: int = 4) -> List[ScheduleResult]:
    """Run all four algorithms on the same workload, in display order."""
    return [fcfs(processes),
            sjf(processes),
            priority_scheduling(processes),
            round_robin(processes, quantum)]
