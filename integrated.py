"""
integrated.py
=============
The integrated CPU scheduling + virtual memory simulation -- the
distinguishing feature of this capstone project.

Idea
----
A CPU scheduling policy decides WHICH process runs WHEN.  Every running
process references pages of its own working set, so the scheduling policy
directly shapes the page reference string that main memory sees:

    * each process owns a small, private, cyclic working set of pages
      (locality of reference):  P1 -> 1,2,3   P2 -> 4,5,6  ...
    * for every time unit a process spends on the CPU it references the
      NEXT page of its working set;
    * walking the Gantt chart of a scheduler therefore produces a
      realistic, interleaved reference string for that policy.

The generated string is then fed through FIFO / LRU / Optimal, so page
faults can be studied AS A FUNCTION OF THE SCHEDULING POLICY.

Typical finding (see the report): FCFS gives every process one long,
uninterrupted stretch of CPU time, so its working set stays resident and
faults are few.  Round Robin with a small quantum constantly interleaves
processes, each eviction throws out a page another process still needs,
and the fault count rises -- scheduling decisions degrade memory
performance even though the memory policy is unchanged.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from scheduler import (Process, ScheduleResult, fcfs, pid_sort_key,
                       priority_scheduling, round_robin, sjf)
from memory import PageResult, fifo, lru, optimal


def assign_pages(processes: List[Process],
                 pages_per_process: int = 3) -> Dict[str, List[int]]:
    """Give every process its own contiguous page range.

    P1 -> 1..k, P2 -> k+1..2k, ...  (k = pages_per_process)
    """
    page_map: Dict[str, List[int]] = {}
    base = 1
    for p in sorted(processes, key=lambda p: pid_sort_key(p.pid)):
        page_map[p.pid] = list(range(base, base + pages_per_process))
        base += pages_per_process
    return page_map


def build_reference_string(result: ScheduleResult,
                           page_map: Dict[str, List[int]]
                           ) -> Tuple[List[int], List[str]]:
    """Walk the Gantt chart and emit one page reference per time unit.

    Returns (references, owners) where owners[i] is the PID that made
    reference i.
    """
    references: List[int] = []
    owners: List[str] = []
    ptr = {pid: 0 for pid in page_map}

    for seg in result.gantt:
        if seg.is_idle:
            continue
        pages = page_map[seg.pid]
        for _ in range(seg.duration):
            references.append(pages[ptr[seg.pid] % len(pages)])
            owners.append(seg.pid)
            ptr[seg.pid] += 1
    return references, owners


def run_integrated(processes: List[Process], quantum: int = 4,
                   frames: int = 4,
                   pages_per_process: int = 3) -> Dict:
    """Run the full integrated experiment.

    Returns a dict with:
        page_map  : pid -> list of pages
        rows      : list of {scheduler, sched_result, memory_result}
                    -- one row per (scheduler, replacement) pair
        plus the parameters used.
    """
    page_map = assign_pages(processes, pages_per_process)

    sched_results = [
        fcfs(processes),
        sjf(processes),
        priority_scheduling(processes),
        round_robin(processes, quantum),
    ]

    rows: List[Dict] = []
    for sres in sched_results:
        references, owners = build_reference_string(sres, page_map)
        for pres in (fifo(references, frames),
                     lru(references, frames),
                     optimal(references, frames)):
            pres.owners = list(owners)
            rows.append({"scheduler": sres.algorithm,
                         "sched_result": sres,
                         "memory_result": pres})

    return {
        "page_map": page_map,
        "rows": rows,
        "frames": frames,
        "quantum": quantum,
        "pages_per_process": pages_per_process,
    }


def best_and_worst(rows: List[Dict]) -> Tuple[Dict, Dict]:
    """Return the (best, worst) integrated rows by page-fault count."""
    ordered = sorted(rows, key=lambda r: r["memory_result"].faults)
    return ordered[0], ordered[-1]
