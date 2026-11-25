"""
demo.py
=======
One-shot evidence pack generator for the Integrated CPU Scheduling +
Virtual Memory Simulator.

Runs every feature on the built-in textbook workloads and writes a
complete set of submission evidence to output/:

    scheduling_run.txt       full console transcript, all 4 algorithms
    gantt_*.png              Gantt chart per algorithm
    scheduling_comparison.png
    scheduling_*.csv         per-process detail / summary / segments

    memory_run.txt           transcripts for both reference strings
    page_faults_comparison_*.png
    page_trace_*.csv         step-by-step frame tables
    page_replacement_summary.csv

    integrated_run.txt       integrated simulation transcript
    integrated_heatmap.png   scheduler x replacement fault matrix
    integrated_*.csv

    thrashing_run.txt        faults-vs-frames transcript
    thrashing_curve.png
    thrashing.csv

    test_results.txt         PASS/FAIL table of the whole test suite
    run_log.txt              timestamp + environment + file inventory

Run:
    python3 demo.py
"""

from __future__ import annotations

import contextlib
import datetime
import os
import platform
import sys
from typing import List

import integrated as integrated_mod
import memory
import metrics
import sample_data as sd
import scheduler
import test_simulator
import visualizer
from memory import faults_per_owner
from scheduler import pid_sort_key

ALGO_SLUGS = ["fcfs", "sjf", "priority", "rr"]


class _Tee:
    """Write to several streams at once (console + transcript file)."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:                                  # noqa: BLE001
                pass


@contextlib.contextmanager
def transcript(path: str):
    """Print to the console AND capture the same text into `path`."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fh = open(path, "w")
    tee = _Tee(sys.stdout, fh)
    with contextlib.redirect_stdout(tee):
        try:
            yield
        finally:
            fh.close()


def _rule(title: str) -> None:
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


# --------------------------------------------------------------------------- #
#  Section 1 -- CPU scheduling
# --------------------------------------------------------------------------- #


def scheduling_section(outdir: str) -> List[str]:
    paths: List[str] = []
    tpath = os.path.join(outdir, "scheduling_run.txt")
    with transcript(tpath):
        _rule("SECTION 1 -- CPU SCHEDULING (4 algorithms, sample workload)")
        print("Workload (textbook 5-process set):")
        print(metrics.process_table(
            scheduler.fcfs(sd.SAMPLE_PROCESSES)))
        print("\nTime quantum for Round Robin: %d" % sd.DEFAULT_QUANTUM)

        results = scheduler.run_all(sd.SAMPLE_PROCESSES, sd.DEFAULT_QUANTUM)
        for res in results:
            print()
            print(metrics.scheduling_report(res))

        print("\nSIDE-BY-SIDE COMPARISON")
        print("-" * 74)
        print(metrics.comparison_table(results))

    for slug, res in zip(ALGO_SLUGS, results):
        paths.append(visualizer.save_gantt(
            res, os.path.join(outdir, "gantt_%s.png" % slug)))
    paths.append(visualizer.save_scheduling_comparison(
        results, os.path.join(outdir, "scheduling_comparison.png")))
    metrics.save_scheduling_csvs(results, outdir)
    paths += [os.path.join(outdir, f)
              for f in ("scheduling_detail.csv", "scheduling_summary.csv",
                        "gantt_segments.csv")]
    paths.append(tpath)
    return paths


# --------------------------------------------------------------------------- #
#  Section 2 -- Page replacement
# --------------------------------------------------------------------------- #


def memory_section(outdir: str) -> List[str]:
    paths: List[str] = []
    tpath = os.path.join(outdir, "memory_run.txt")
    labels = [("short", "A -- lab-manual string (10 refs, 3 frames)",
               sd.SAMPLE_REF_SHORT, 3),
              ("long", "B -- classic 20-reference string (3 frames)",
               sd.SAMPLE_REF_LONG, 3)]
    with transcript(tpath):
        _rule("SECTION 2 -- PAGE REPLACEMENT (FIFO / LRU / Optimal)")
        for slug, title, refs, frames in labels:
            _rule("Reference string %s" % title)
            print("Reference string : %s"
                  % " ".join(str(r) for r in refs))
            print("Frames           : %d    Distinct pages: %d"
                  % (frames, len(set(refs))))
            print()
            results = memory.run_all(refs, frames)
            print(metrics.memory_summary_table(results))
            print()
            for res in results:
                print("FRAME TABLE -- %s" % res.algorithm)
                print("-" * 74)
                print(metrics.frame_table(res))
                print()
            best = min(results, key=lambda r: r.faults)
            worst = max(results, key=lambda r: r.faults)
            print("Analysis: %s wins with %d faults vs %s with %d faults "
                  "(%.1f%% fewer)."
                  % (best.algorithm, best.faults, worst.algorithm,
                     worst.faults,
                     100.0 * (worst.faults - best.faults) / worst.faults))

    for (slug, title, refs, frames), png in zip(
            labels, ("page_faults_comparison_short.png",
                     "page_faults_comparison_long.png")):
        results = memory.run_all(refs, frames)
        paths.append(visualizer.save_memory_comparison(
            results, "Reference string %s" % title,
            os.path.join(outdir, png)))
        metrics.save_memory_csvs(results, slug, outdir)
        paths.append(os.path.join(outdir, "page_replacement_summary.csv"))
    paths += [os.path.join(outdir, n) for n in (
        "page_trace_short_fifo.csv", "page_trace_short_lru.csv",
        "page_trace_short_optimal.csv", "page_trace_long_fifo.csv",
        "page_trace_long_lru.csv", "page_trace_long_optimal.csv")]
    paths.append(tpath)
    return paths


# --------------------------------------------------------------------------- #
#  Section 3 -- Integrated simulation
# --------------------------------------------------------------------------- #


def integrated_section(outdir: str) -> List[str]:
    paths: List[str] = []
    tpath = os.path.join(outdir, "integrated_run.txt")
    data = integrated_mod.run_integrated(
        sd.SAMPLE_PROCESSES,
        quantum=sd.INTEGRATED_QUANTUM,
        frames=sd.INTEGRATED_FRAMES,
        pages_per_process=sd.INTEGRATED_PAGES_PER_PROCESS)

    with transcript(tpath):
        _rule("SECTION 3 -- INTEGRATED SIMULATION "
              "(CPU scheduling linked to virtual memory)")
        print("Every process owns a cyclic working set of %d pages; each "
              "time unit" % data["pages_per_process"])
        print("on the CPU it references the next page of that set.  The "
              "Gantt chart")
        print("of each scheduler therefore generates a different "
              "reference string.")
        print("Frames allocated: %d    Round Robin quantum: %d\n"
              % (data["frames"], data["quantum"]))

        print("Page assignment (working sets):")
        for pid, pages in sorted(data["page_map"].items(),
                                 key=lambda kv: pid_sort_key(kv[0])):
            print("  %s -> pages %s"
                  % (pid, ", ".join(str(x) for x in pages)))

        print("\nINTEGRATED PERFORMANCE MATRIX (scheduler x replacement)")
        print("-" * 74)
        print(metrics.integrated_matrix_table(data["rows"]))

        best, worst = integrated_mod.best_and_worst(data["rows"])
        print("\nBest combination : %s + %s -> %d faults"
              % (best["sched_result"].algorithm,
                 best["memory_result"].algorithm,
                 best["memory_result"].faults))
        print("Worst combination: %s + %s -> %d faults"
              % (worst["sched_result"].algorithm,
                 worst["memory_result"].algorithm,
                 worst["memory_result"].faults))

        # the key observation: FCFS vs RR under the same memory policy
        def faults_of(sched_prefix, algo):
            for row in data["rows"]:
                if (row["sched_result"].algorithm.startswith(sched_prefix)
                        and row["memory_result"].algorithm == algo):
                    return row["memory_result"].faults
            return None

        for algo in ("FIFO", "LRU", "Optimal"):
            fcfs = faults_of("FCFS", algo)
            rr = faults_of("Round Robin", algo)
            extra = rr - fcfs
            print("\n%s: FCFS causes %d faults, RR(q=%d) causes %d -- "
                  "interleaving costs %d extra faults (+%.0f%%)."
                  % (algo, fcfs, data["quantum"], rr, extra,
                     100.0 * extra / fcfs if fcfs else 0.0))

        rr_rows = [r for r in data["rows"]
                   if r["sched_result"].algorithm.startswith("Round Robin")]
        pres_by_algo = {r["memory_result"].algorithm: r["memory_result"]
                        for r in rr_rows}
        pids = sorted(data["page_map"], key=pid_sort_key)
        print("\nPER-PROCESS PAGE FAULTS (Round Robin scheduler)")
        print("-" * 74)
        print(metrics.per_process_fault_table(pres_by_algo, pids))

    paths.append(visualizer.save_integrated_heatmap(
        data["rows"], os.path.join(outdir, "integrated_heatmap.png")))
    metrics.save_integrated_csvs(data["rows"], outdir)
    paths += [os.path.join(outdir, n) for n in (
        "integrated_matrix.csv", "integrated_per_process.csv")]
    paths.append(tpath)
    return paths


# --------------------------------------------------------------------------- #
#  Section 4 -- Thrashing analysis
# --------------------------------------------------------------------------- #


def thrashing_section(outdir: str) -> List[str]:
    paths: List[str] = []
    tpath = os.path.join(outdir, "thrashing_run.txt")
    sweep = list(range(1, sd.THRASHING_MAX_FRAMES + 1))
    refs = sd.SAMPLE_REF_LONG

    results_by_frames = {f: memory.run_all(refs, f) for f in sweep}
    algo_names = ["FIFO", "LRU", "Optimal"]
    series = {a: [results_by_frames[f][i].faults for f in sweep]
              for i, a in enumerate(algo_names)}
    knees = {a: metrics.knee_frame_count(sweep, series[a])
             for a in algo_names}

    with transcript(tpath):
        _rule("SECTION 4 -- THRASHING ANALYSIS (faults vs frame count)")
        print("Reference string: %s" % " ".join(str(r) for r in refs))
        print("Distinct pages   : %d" % len(set(refs)))
        print("Frames swept     : 1 to %d\n" % sweep[-1])

        header = "{:<8}".format("Frames") + "".join(
            "{:>9}".format(a) for a in algo_names)
        print(header)
        print("-" * len(header))
        for i, f in enumerate(sweep):
            print("{:<8}".format(f)
                  + "".join("{:>9}".format(series[a][i]) for a in algo_names))

        print("\nKnee analysis (smallest frame count reaching 90% of the "
              "maximum fault reduction):")
        for a in algo_names:
            print("  %-8s -> %d frame(s)" % (a, knees[a]))

        anomaly = []
        for a in algo_names:
            faults = series[a]
            for i in range(1, len(faults)):
                if faults[i] > faults[i - 1]:
                    anomaly.append((a, sweep[i - 1], sweep[i],
                                    faults[i - 1], faults[i]))
        if anomaly:
            print("\nBelady's anomaly detected (faults INCREASED when "
                  "frames were added):")
            for a, f_prev, f_now, v_prev, v_now in anomaly:
                print("  %s: %d faults with %d frames -> %d faults with %d "
                      "frames" % (a, v_prev, f_prev, v_now, f_now))
        else:
            print("\nNo Belady's anomaly in this sweep: fault counts are "
                  "monotonically non-increasing for all three algorithms.")

    paths.append(visualizer.save_thrashing(
        sweep, series, os.path.join(outdir, "thrashing_curve.png"),
        knees=knees))
    metrics.save_thrashing_csv(sweep, series, outdir)
    paths += [os.path.join(outdir, "thrashing.csv"), tpath]
    return paths


# --------------------------------------------------------------------------- #
#  Section 5 -- Test suite
# --------------------------------------------------------------------------- #


def tests_section(outdir: str) -> List[str]:
    print("Running test suite (output also saved to test_results.txt)...\n")
    test_simulator.run_all_tests(write_file=True, outdir=outdir)
    return [os.path.join(outdir, "test_results.txt")]


# --------------------------------------------------------------------------- #
#  Orchestrator
# --------------------------------------------------------------------------- #


def generate_all(outdir: str = None) -> List[str]:
    base = os.path.dirname(os.path.abspath(__file__))
    outdir = outdir or os.path.join(base, "output")
    os.makedirs(outdir, exist_ok=True)

    started = datetime.datetime.now()
    print("Generating evidence pack in %s ...\n" % outdir)

    files = []
    files += scheduling_section(outdir)
    files += memory_section(outdir)
    files += integrated_section(outdir)
    files += thrashing_section(outdir)
    files += tests_section(outdir)

    # de-duplicate while preserving order
    seen, unique = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    log = os.path.join(outdir, "run_log.txt")
    with open(log, "w") as f:
        f.write("EVIDENCE PACK -- Integrated CPU Scheduling + Virtual "
                "Memory Simulator\n")
        f.write("Generated : %s\n" % started.isoformat(timespec="seconds"))
        f.write("Python    : %s\n" % platform.python_version())
        f.write("Platform  : %s\n" % platform.platform())
        f.write("Files     : %d\n\n" % len(unique))
        for p in unique:
            f.write("  %s\n" % os.path.basename(p))
    unique.append(log)

    print("\n" + "=" * 74)
    print("EVIDENCE PACK COMPLETE -- %d files in %s"
          % (len(unique), outdir))
    print("=" * 74)
    for p in unique:
        print("  %s" % os.path.basename(p))
    return unique


if __name__ == "__main__":
    generate_all()
