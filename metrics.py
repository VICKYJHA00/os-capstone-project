"""
metrics.py
==========
Performance metrics, console tables and CSV export for the Integrated
CPU Scheduling + Virtual Memory Simulator.

Console tables are plain fixed-width text so they render identically in
any terminal and can be pasted straight into a report as output evidence.
"""

from __future__ import annotations

import csv
import os
from typing import Dict, Iterable, List, Optional

from scheduler import ScheduleResult, pid_sort_key
from memory import PageResult

# --------------------------------------------------------------------------- #
#  Scheduling metrics
# --------------------------------------------------------------------------- #


def knee_frame_count(sweep: List[int], faults: List[int],
                     fraction: float = 0.9) -> int:
    """Smallest frame count in the sweep that achieves `fraction` (90%)
    of the maximum possible fault reduction -- the 'knee' of the curve,
    i.e. the point after which adding frames barely helps.

    Used by the thrashing analysis to recommend a frame allocation.
    """
    f1, fmin = faults[0], min(faults)
    span = f1 - fmin
    if span <= 0:
        return sweep[0]
    for f, v in zip(sweep, faults):
        if f1 - v >= fraction * span:
            return f
    return sweep[-1]


def summarize(result: ScheduleResult) -> Dict:
    """Aggregate performance metrics for one scheduling run."""
    records = result.records
    n = len(records)
    busy = sum(s.duration for s in result.gantt if not s.is_idle)
    idle = sum(s.duration for s in result.gantt if s.is_idle)
    makespan = result.makespan

    dispatch_counts: Dict[str, int] = {}
    for s in result.gantt:
        if not s.is_idle:
            dispatch_counts[s.pid] = dispatch_counts.get(s.pid, 0) + 1
    # a process dispatched k times was preempted k-1 times
    preemptions = sum(max(0, c - 1) for c in dispatch_counts.values())

    def avg(attr: str) -> float:
        return sum(getattr(r, attr) for r in records) / n if n else 0.0

    return {
        "algorithm": result.algorithm,
        "n": n,
        "avg_waiting": avg("waiting"),
        "avg_turnaround": avg("turnaround"),
        "avg_response": avg("response"),
        "makespan": makespan,
        "busy": busy,
        "idle": idle,
        "cpu_utilization": (100.0 * busy / makespan) if makespan else 0.0,
        "throughput": (n / makespan) if makespan else 0.0,
        "dispatches": sum(dispatch_counts.values()),
        "preemptions": preemptions,
    }


# --------------------------------------------------------------------------- #
#  Console tables (fixed-width, terminal friendly)
# --------------------------------------------------------------------------- #


def pid_symbols(records) -> Dict[str, str]:
    """One-character symbol per PID for the ASCII Gantt bar.

    Processes 1-9 use digits, the rest letters (10 -> A, 11 -> B, ...).
    """
    syms: Dict[str, str] = {}
    for idx, r in enumerate(sorted(records, key=lambda r: pid_sort_key(r.pid)),
                            start=1):
        syms[r.pid] = str(idx) if idx <= 9 else chr(ord("A") + idx - 10)
    return syms


def process_table(result: ScheduleResult) -> str:
    """Per-process timing table (PID, arrival, burst, priority, ...)."""
    header = ("{:<6}{:>8}{:>7}{:>9}{:>7}{:>8}{:>6}{:>6}{:>6}"
              .format("PID", "Arrival", "Burst", "Priority", "Start",
                      "Compl.", "TAT", "WT", "RT"))
    lines = [header, "-" * len(header)]
    for r in sorted(result.records, key=lambda r: pid_sort_key(r.pid)):
        lines.append("{:<6}{:>8}{:>7}{:>9}{:>7}{:>8}{:>6}{:>6}{:>6}".format(
            r.pid, r.arrival, r.burst, r.priority, r.start_time,
            r.completion, r.turnaround, r.waiting, r.response))
    return "\n".join(lines)


def gantt_ascii(result: ScheduleResult, width: int = 62) -> str:
    """Render the Gantt chart as a scaled one-line ASCII bar."""
    gantt = result.gantt
    makespan = result.makespan
    if not gantt or makespan == 0:
        return "(nothing was executed)"

    scale = width / makespan
    syms = pid_symbols(result.records)
    bar: List[str] = []
    marks = []                                   # (char position, time)

    for seg in gantt:
        w = max(1, int(round(seg.duration * scale)))
        marks.append((len(bar), seg.start))
        if seg.is_idle:
            bar.extend("-" * w)
        else:
            bar.extend(syms[seg.pid] * w)
    marks.append((len(bar), makespan))

    # time ruler: label each boundary unless it collides with the previous one
    ruler = [" "] * (len(bar) + 12)
    last_end = -10
    for pos, t in marks:
        label = str(t)
        if pos < last_end + 1:
            continue
        for k, ch in enumerate(label):
            if pos + k < len(ruler):
                ruler[pos + k] = ch
        last_end = pos + len(label) - 1

    legend = "   ".join(
        "%s=%s" % (sym, pid)
        for pid, sym in sorted(syms.items(),
                               key=lambda kv: pid_sort_key(kv[0])))
    legend += "   -=idle"

    return "\n".join([
        "Gantt chart (1 character ~ %.2f time units):" % (1.0 / scale),
        "".join(bar),
        "".join(ruler).rstrip(),
        "Legend: " + legend,
    ])


def summary_lines(result: ScheduleResult) -> str:
    s = summarize(result)
    return "\n".join([
        "Average Waiting Time    : %8.2f" % s["avg_waiting"],
        "Average Turnaround Time : %8.2f" % s["avg_turnaround"],
        "Average Response Time   : %8.2f" % s["avg_response"],
        "CPU Utilization         : %7.2f %%" % s["cpu_utilization"],
        "Throughput              : %7.3f processes / time unit"
        % s["throughput"],
        "Total time (makespan)   : %8d" % s["makespan"],
        "CPU dispatches          : %8d" % s["dispatches"],
        "Preemptions             : %8d" % s["preemptions"],
    ])


def comparison_table(results: List[ScheduleResult]) -> str:
    """Side-by-side comparison of all scheduling algorithms."""
    header = ("{:<26}{:>9}{:>9}{:>9}{:>8}{:>9}{:>8}"
              .format("Algorithm", "Avg WT", "Avg TAT", "Avg RT",
                      "CPU %", "Thruput", "Preempt"))
    lines = [header, "-" * len(header)]
    best_wt = min(summarize(r)["avg_waiting"] for r in results) if results \
        else 0.0
    for r in results:
        s = summarize(r)
        marker = " *" if abs(s["avg_waiting"] - best_wt) < 1e-9 else ""
        lines.append("{:<26}{:>9.2f}{:>9.2f}{:>9.2f}{:>8.1f}{:>9.3f}{:>8d}{}"
                     .format(s["algorithm"], s["avg_waiting"],
                             s["avg_turnaround"], s["avg_response"],
                             s["cpu_utilization"], s["throughput"],
                             s["preemptions"], marker))
    lines.append("-" * len(header))
    lines.append("* = lowest average waiting time on this workload")
    return "\n".join(lines)


def scheduling_report(result: ScheduleResult) -> str:
    """Full console block for one scheduling run."""
    sep = "=" * 74
    return "\n".join([
        sep,
        "ALGORITHM : %s" % result.algorithm,
        sep,
        process_table(result),
        "",
        gantt_ascii(result),
        "",
        summary_lines(result),
        sep,
    ])


# --------------------------------------------------------------------------- #
#  Memory (page replacement) tables
# --------------------------------------------------------------------------- #


def memory_summary_table(results: List[PageResult]) -> str:
    header = ("{:<10}{:>7}{:>6}{:>7}{:>6}{:>11}{:>12}"
              .format("Algorithm", "Frames", "Refs", "Faults", "Hits",
                      "Hit Ratio", "Fault Ratio"))
    lines = [header, "-" * len(header)]
    best = min((p.faults for p in results), default=0)
    for p in results:
        marker = " *" if p.faults == best and results else ""
        lines.append("{:<10}{:>7}{:>6}{:>7}{:>6}{:>11.2%}{:>12.2%}{}".format(
            p.algorithm, p.frames, p.total, p.faults, p.hits,
            p.hit_ratio, p.fault_ratio, marker))
    lines.append("-" * len(header))
    lines.append("* = fewest page faults on this reference string")
    return "\n".join(lines)


def frame_table(result: PageResult) -> str:
    """Step-by-step frame contents for one replacement algorithm."""
    k = result.frames
    header = ("{:>4}{:>6}{:>8}".format("Ref", "Page", "Result")
              + "".join("%4s" % ("F%d" % (i + 1)) for i in range(k))
              + "{:>9}".format("Evicted"))
    lines = [header, "-" * len(header)]
    for row in result.trace:
        cells = "".join("%4s" % (p if p is not None else "-")
                        for p in row["frames"])
        status = "HIT" if row["hit"] else "FAULT"
        ev = "-" if row["evicted"] is None else str(row["evicted"])
        lines.append("{:>4}{:>6}{:>8}{}{:>9}".format(
            row["ref"], row["page"], status, cells, ev))
    lines.append("-" * len(header))
    lines.append("Page faults : %d    Hits : %d    "
                 "Hit ratio : %.2f%%    Fault ratio : %.2f%%"
                 % (result.faults, result.hits,
                    result.hit_ratio * 100, result.fault_ratio * 100))
    return "\n".join(lines)


def integrated_matrix_table(rows: List[Dict]) -> str:
    """rows: list of dicts with scheduler / sched_result / memory_result."""
    header = ("{:<26}{:<10}{:>7}{:>6}{:>8}{:>10}"
              .format("Scheduler", "Memory", "Faults", "Hits", "Hit %",
                      "Avg WT*"))
    lines = [header, "-" * len(header)]
    for row in rows:
        sres, pres = row["sched_result"], row["memory_result"]
        s = summarize(sres)
        lines.append("{:<26}{:<10}{:>7}{:>6}{:>8.1f}{:>10.2f}".format(
            sres.algorithm, pres.algorithm, pres.faults, pres.hits,
            pres.hit_ratio * 100, s["avg_waiting"]))
    lines.append("-" * len(header))
    lines.append("* Avg WT = waiting time of the CPU scheduler itself")
    return "\n".join(lines)


def per_process_fault_table(pres_by_algo: Dict[str, PageResult],
                            pids: List[str]) -> str:
    """Per-process page faults for several replacement algorithms."""
    from memory import faults_per_owner
    fault_maps = {algo: faults_per_owner(pres)
                  for algo, pres in pres_by_algo.items()}
    header = "{:<8}".format("PID") + "".join(
        "{:>10}".format(a) for a in pres_by_algo)
    lines = [header, "-" * len(header)]
    for pid in pids:
        lines.append("{:<8}".format(pid)
                     + "".join("{:>10}".format(fault_maps[a].get(pid, 0))
                                for a in pres_by_algo))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  CSV export
# --------------------------------------------------------------------------- #


def write_csv(path: str, header: List[str], rows: Iterable) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def save_scheduling_csvs(results: List[ScheduleResult], outdir: str) -> None:
    """Write per-process detail, per-algorithm summary and Gantt segments."""
    detail, summary, gantt_rows = [], [], []
    for r in results:
        for rec in sorted(r.records, key=lambda x: pid_sort_key(x.pid)):
            detail.append([r.algorithm, rec.pid, rec.arrival, rec.burst,
                           rec.priority, rec.start_time, rec.completion,
                           rec.turnaround, rec.waiting, rec.response])
        s = summarize(r)
        summary.append([s["algorithm"], round(s["avg_waiting"], 3),
                        round(s["avg_turnaround"], 3),
                        round(s["avg_response"], 3), s["makespan"],
                        round(s["cpu_utilization"], 2),
                        round(s["throughput"], 4), s["dispatches"],
                        s["preemptions"]])
        for idx, seg in enumerate(r.gantt, start=1):
            gantt_rows.append([r.algorithm, idx, seg.pid or "IDLE",
                               seg.start, seg.end, seg.duration])

    write_csv(os.path.join(outdir, "scheduling_detail.csv"),
              ["Algorithm", "PID", "Arrival", "Burst", "Priority", "Start",
               "Completion", "Turnaround", "Waiting", "Response"], detail)
    write_csv(os.path.join(outdir, "scheduling_summary.csv"),
              ["Algorithm", "AvgWaiting", "AvgTurnaround", "AvgResponse",
               "Makespan", "CPUUtil%", "Throughput", "Dispatches",
               "Preemptions"], summary)
    write_csv(os.path.join(outdir, "gantt_segments.csv"),
              ["Algorithm", "Segment", "PID", "Start", "End", "Duration"],
              gantt_rows)


def save_memory_csvs(results: List[PageResult], label: str,
                     outdir: str) -> None:
    """Write the summary table plus a full trace per algorithm."""
    summary = [[label, p.total, p.frames, p.algorithm, p.faults, p.hits,
                round(p.hit_ratio, 4), round(p.fault_ratio, 4)]
               for p in results]
    write_csv(os.path.join(outdir, "page_replacement_summary.csv"),
              ["ReferenceString", "Refs", "Frames", "Algorithm", "Faults",
               "Hits", "HitRatio", "FaultRatio"], summary)

    for p in results:
        trace_rows = [[row["ref"], row["page"],
                       "HIT" if row["hit"] else "FAULT",
                       *row["frames"],
                       "-" if row["evicted"] is None else row["evicted"]]
                      for row in p.trace]
        write_csv(os.path.join(outdir, "page_trace_%s_%s.csv"
                               % (label.lower(), p.algorithm.lower())),
                  ["RefNo", "Page", "Result"]
                  + ["Frame%d" % (i + 1) for i in range(p.frames)]
                  + ["Evicted"], trace_rows)


def save_integrated_csvs(rows: List[Dict], outdir: str) -> None:
    matrix = []
    for row in rows:
        sres, pres = row["sched_result"], row["memory_result"]
        s = summarize(sres)
        matrix.append([sres.algorithm, pres.algorithm, pres.total,
                       pres.faults, pres.hits,
                       round(pres.hit_ratio, 4), round(s["avg_waiting"], 3),
                       round(s["avg_turnaround"], 3)])
    write_csv(os.path.join(outdir, "integrated_matrix.csv"),
              ["Scheduler", "Replacement", "Refs", "Faults", "Hits",
               "HitRatio", "SchedAvgWT", "SchedAvgTAT"], matrix)

    from memory import faults_per_owner
    per_proc = []
    for row in rows:
        pres = row["memory_result"]
        try:
            per = faults_per_owner(pres)
        except ValueError:
            continue
        for pid, faults in per.items():
            per_proc.append([row["sched_result"].algorithm,
                             pres.algorithm, pid, faults])
    write_csv(os.path.join(outdir, "integrated_per_process.csv"),
              ["Scheduler", "Replacement", "PID", "Faults"], per_proc)


def save_thrashing_csv(frames: List[int], series: Dict[str, List[int]],
                       outdir: str) -> None:
    header = ["Frames"] + list(series.keys())
    rows = [[f] + [series[a][i] for a in series]
            for i, f in enumerate(frames)]
    write_csv(os.path.join(outdir, "thrashing.csv"), header, rows)
