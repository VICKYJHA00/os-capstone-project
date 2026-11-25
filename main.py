#!/usr/bin/env python3
"""
main.py
=======
Menu-driven front end for the Integrated CPU Scheduling + Virtual Memory
Simulator (OS Capstone Project).

Run:
    python3 main.py

Everything you see on screen can also be exported as PNG charts, CSV
files and text transcripts to the output/ folder (menu option 11 runs
the complete evidence pack in one shot).
"""

from __future__ import annotations

import os
import sys

import integrated as integrated_mod
import memory
import metrics
import sample_data
import scheduler
import validation
import visualizer
from scheduler import Process

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

ALGO_SLUGS = ["fcfs", "sjf", "priority", "rr"]


# --------------------------------------------------------------------------- #
#  Application state
# --------------------------------------------------------------------------- #


class State:
    """Everything the user has loaded/entered so far."""

    def __init__(self):
        self.processes = list(sample_data.SAMPLE_PROCESSES)
        self.refs = list(sample_data.SAMPLE_REF_SHORT)
        self.frames = sample_data.DEFAULT_FRAMES
        self.quantum = sample_data.DEFAULT_QUANTUM

    def status_line(self) -> str:
        return ("%s | %d page refs, %d frames | quantum=%d"
                % (sample_data.describe_processes(self.processes),
                   len(self.refs), self.frames, self.quantum))


# --------------------------------------------------------------------------- #
#  Small input helpers (with invalid-input re-prompting)
# --------------------------------------------------------------------------- #


def ask(prompt: str, default=None) -> str:
    suffix = " [%s]" % (default,) if default is not None else ""
    try:
        raw = input("%s%s: " % (prompt, suffix)).strip()
    except EOFError:
        print()
        raise SystemExit(0)
    return raw if raw else (str(default) if default is not None else "")


def ask_int(prompt: str, minimum=None, maximum=None, default=None) -> int:
    """Read an integer, re-prompting with a clear message on bad input."""
    while True:
        raw = ask(prompt, default)
        try:
            value = int(raw)
        except ValueError:
            print("  x  '%s' is not a whole number -- please try again."
                  % raw)
            continue
        if minimum is not None and value < minimum:
            print("  x  Value must be at least %d." % minimum)
            continue
        if maximum is not None and value > maximum:
            print("  x  Value must be at most %d." % maximum)
            continue
        return value


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    raw = ask("%s (y/n)" % prompt,
              "Y" if default else "n").lower()
    return default if not raw else raw in ("y", "yes")


def header(title: str) -> None:
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


# --------------------------------------------------------------------------- #
#  Menu actions -- process workload
# --------------------------------------------------------------------------- #


def show_processes(state: State) -> None:
    header("CURRENT PROCESS WORKLOAD")
    if not state.processes:
        print("(no processes loaded)")
        return
    print("%-6s %10s %8s %10s" % ("PID", "Arrival", "Burst", "Priority"))
    for p in state.processes:
        print("%-6s %10d %8d %10d" % (p.pid, p.arrival, p.burst, p.priority))
    print("\nPriority: 1 = highest priority.")


def load_sample_processes(state: State) -> None:
    state.processes = list(sample_data.SAMPLE_PROCESSES)
    header("LOADED SAMPLE WORKLOAD (textbook 5-process set)")
    show_processes(state)


def enter_processes(state: State) -> None:
    header("ENTER A CUSTOM PROCESS SET")
    n = ask_int("How many processes do you want to enter", minimum=1,
                maximum=25)
    procs: list = []
    for i in range(n):
        print("\n--- Process %d of %d ---" % (i + 1, n))
        while True:                       # re-prompt until the row is valid
            pid = ask("  PID", default="P%d" % (i + 1))
            arrival = ask_int("  Arrival time (>= 0)", minimum=0, default=0)
            burst = ask_int("  Burst time (>= 1)", minimum=1, default=1)
            priority = ask_int("  Priority (1 = highest)", minimum=1,
                               default=1)
            candidate = procs + [Process(pid, arrival, burst, priority)]
            try:
                validation.validate_processes(candidate)
            except validation.InputError as exc:
                print("  x  %s" % exc)
                print("  (re-entering this process)")
                continue
            procs.append(candidate[-1])
            break
    state.processes = procs
    print("\nAccepted %d processes." % len(procs))
    show_processes(state)


# --------------------------------------------------------------------------- #
#  Menu actions -- CPU scheduling
# --------------------------------------------------------------------------- #


def save_scheduling_outputs(results, state) -> None:
    if not ask_yes_no("Save charts + CSV to output/"):
        return
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    paths = []
    for slug, res in zip(ALGO_SLUGS, results):
        paths.append(visualizer.save_gantt(
            res, os.path.join(OUTPUT_DIR, "gantt_%s.png" % slug)))
    paths.append(visualizer.save_scheduling_comparison(
        results, os.path.join(OUTPUT_DIR, "scheduling_comparison.png")))
    metrics.save_scheduling_csvs(results, OUTPUT_DIR)
    paths.append(os.path.join(OUTPUT_DIR, "scheduling_detail.csv"))
    print("Saved: " + ", ".join(os.path.basename(p) for p in paths)
          + " (+ scheduling_summary.csv, gantt_segments.csv)")


def run_scheduling_all(state: State) -> None:
    header("CPU SCHEDULING -- ALL FOUR ALGORITHMS")
    print("Workload: %s\n" % sample_data.describe_processes(state.processes))
    results = scheduler.run_all(state.processes, state.quantum)
    for res in results:
        print(metrics.scheduling_report(res))
        print()
    print("COMPARISON OF ALL ALGORITHMS")
    print("-" * 74)
    print(metrics.comparison_table(results))
    save_scheduling_outputs(results, state)


def run_scheduling_one(state: State) -> None:
    header("CPU SCHEDULING -- SINGLE ALGORITHM (detailed)")
    print("  1. FCFS\n  2. SJF (non-preemptive)\n"
          "  3. Priority (1 = highest)\n  4. Round Robin")
    choice = ask_int("Choose algorithm", minimum=1, maximum=4, default=1)
    if choice == 4:
        state.quantum = ask_int("Round Robin time quantum", minimum=1,
                                default=state.quantum)
    runners = [scheduler.fcfs, scheduler.sjf, scheduler.priority_scheduling,
               lambda ps: scheduler.round_robin(ps, state.quantum)]
    res = runners[choice - 1](state.processes)
    print(metrics.scheduling_report(res))
    if ask_yes_no("Save Gantt chart + CSV to output/"):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = visualizer.save_gantt(
            res, os.path.join(OUTPUT_DIR, "gantt_%s.png"
                              % ALGO_SLUGS[choice - 1]))
        metrics.save_scheduling_csvs([res], OUTPUT_DIR)
        print("Saved: %s (+ scheduling_detail.csv, scheduling_summary.csv, "
              "gantt_segments.csv)" % os.path.basename(path))


# --------------------------------------------------------------------------- #
#  Menu actions -- virtual memory
# --------------------------------------------------------------------------- #


def show_reference_string(state: State) -> None:
    header("CURRENT PAGE REFERENCE STRING")
    print("Reference string (%d refs): %s"
          % (len(state.refs), " ".join(str(r) for r in state.refs)))
    print("Frames: %d" % state.frames)
    print("Distinct pages: %d" % len(set(state.refs)))


def enter_reference_string(state: State) -> None:
    header("ENTER A PAGE REFERENCE STRING")
    while True:                          # re-prompt until valid or cancelled
        text = ask("Pages separated by spaces or commas "
                   "(e.g. 7 0 1 2 0 3), or q to cancel")
        if text.lower() in ("q", "quit", "cancel"):
            return
        try:
            refs = validation.parse_reference_string(text)
        except validation.InputError as exc:
            print("  x  %s" % exc)
            continue
        break
    state.refs = refs
    state.frames = ask_int("Number of frames", minimum=1,
                           default=state.frames)
    show_reference_string(state)


def run_memory_all(state: State) -> None:
    header("PAGE REPLACEMENT -- FIFO / LRU / OPTIMAL")
    show_reference_string(state)
    print()
    results = memory.run_all(state.refs, state.frames)
    print(metrics.memory_summary_table(results))
    print()
    if len(state.refs) <= 25:
        for res in results:
            print("FRAME TABLE -- %s" % res.algorithm)
            print("-" * 74)
            print(metrics.frame_table(res))
            print()
    best = min(results, key=lambda r: r.faults)
    worst = max(results, key=lambda r: r.faults)
    print("Analysis: %s performs best on this string with %d faults; "
          "%s performs worst with %d faults (%d fewer faults, %.1f%% "
          "improvement)."
          % (best.algorithm, best.faults, worst.algorithm, worst.faults,
             worst.faults - best.faults,
             100.0 * (worst.faults - best.faults) / worst.faults
             if worst.faults else 0.0))
    if ask_yes_no("Save comparison chart + CSV traces to output/"):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        png = visualizer.save_memory_comparison(
            results,
            "Page replacement comparison (%d refs, %d frames)"
            % (len(state.refs), state.frames),
            os.path.join(OUTPUT_DIR, "page_faults_comparison.png"))
        metrics.save_memory_csvs(results, "current", OUTPUT_DIR)
        print("Saved: %s (+ page_replacement_summary.csv, page_trace_*.csv)"
              % os.path.basename(png))


# --------------------------------------------------------------------------- #
#  Menu actions -- integrated simulation
# --------------------------------------------------------------------------- #


def run_integrated(state: State) -> None:
    header("INTEGRATED SIMULATION -- SCHEDULING LINKED TO MEMORY")
    print("Each process gets its own cyclic working set of pages; while it")
    print("runs on the CPU it references the next page of that set.  The")
    print("resulting reference string is then paged through FIFO/LRU/")
    print("Optimal -- so memory performance depends on the SCHEDULER.\n")
    print("Workload: %s\n" % sample_data.describe_processes(state.processes))

    quantum = ask_int("Round Robin quantum", minimum=1,
                      default=sample_data.INTEGRATED_QUANTUM)
    frames = ask_int("Memory frames", minimum=1,
                     default=sample_data.INTEGRATED_FRAMES)
    ppp = ask_int("Pages per process (working-set size)", minimum=1,
                  default=sample_data.INTEGRATED_PAGES_PER_PROCESS)

    try:
        validation.validate_processes(state.processes)
        validation.validate_quantum(quantum)
        validation.validate_frames(frames)
        validation.validate_pages_per_process(ppp)
    except validation.InputError as exc:
        print("  x  %s" % exc)
        return

    data = integrated_mod.run_integrated(state.processes, quantum, frames,
                                         ppp)

    print("\nPage assignment (working sets):")
    for pid, pages in sorted(data["page_map"].items()):
        print("  %s -> pages %s" % (pid, ", ".join(str(x) for x in pages)))

    print("\nINTEGRATED PERFORMANCE MATRIX (12 combinations)")
    print("-" * 74)
    print(metrics.integrated_matrix_table(data["rows"]))

    best, worst = integrated_mod.best_and_worst(data["rows"])
    print("\nBest combination : %s + %s -> %d faults"
          % (best["sched_result"].algorithm,
             best["memory_result"].algorithm, best["memory_result"].faults))
    print("Worst combination: %s + %s -> %d faults"
          % (worst["sched_result"].algorithm,
             worst["memory_result"].algorithm, worst["memory_result"].faults))

    # per-process fault attribution for Round Robin (the instructive case)
    rr_rows = [r for r in data["rows"]
               if r["sched_result"].algorithm.startswith("Round Robin")]
    pres_by_algo = {r["memory_result"].algorithm: r["memory_result"]
                    for r in rr_rows}
    pids = sorted(data["page_map"], key=scheduler.pid_sort_key)
    print("\nPER-PROCESS PAGE FAULTS (Round Robin scheduler)")
    print("-" * 74)
    print(metrics.per_process_fault_table(pres_by_algo, pids))
    print("\nObservation: interleaved execution (RR) evicts pages that")
    print("another process still needs, so fault counts rise compared with")
    print("the long uninterrupted CPU stretches given by FCFS -- even")
    print("though the page replacement policy is identical.")

    if ask_yes_no("Save heatmap + CSVs to output/"):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        png = visualizer.save_integrated_heatmap(
            data["rows"], os.path.join(OUTPUT_DIR, "integrated_heatmap.png"))
        metrics.save_integrated_csvs(data["rows"], OUTPUT_DIR)
        print("Saved: %s (+ integrated_matrix.csv, "
              "integrated_per_process.csv)" % os.path.basename(png))


# --------------------------------------------------------------------------- #
#  Menu actions -- thrashing analysis
# --------------------------------------------------------------------------- #


def run_thrashing(state: State) -> None:
    header("THRASHING ANALYSIS -- PAGE FAULTS VS FRAME COUNT")
    show_reference_string(state)
    print()
    max_frames = ask_int("Sweep frames from 1 up to",
                         minimum=1, maximum=25,
                         default=sample_data.THRASHING_MAX_FRAMES)
    sweep = list(range(1, max_frames + 1))

    results_by_frames = {f: memory.run_all(state.refs, f) for f in sweep}
    series = {algo: [results_by_frames[f][i].faults for f in sweep]
              for i, algo in enumerate(["FIFO", "LRU", "Optimal"])}

    header_line = ("{:<8}".format("Frames")
                   + "".join("{:>9}".format(a) for a in series))
    print(header_line)
    print("-" * len(header_line))
    for i, f in enumerate(sweep):
        print("{:<8}".format(f)
              + "".join("{:>9}".format(series[a][i]) for a in series))

    # knee = smallest frame count reaching 90% of the maximum possible
    # fault reduction (the "enough memory" recommendation)
    knees = {algo: metrics.knee_frame_count(sweep, faults)
             for algo, faults in series.items()}

    print("\nKnee analysis (smallest frame count reaching 90% of the "
          "maximum possible fault reduction):")
    for algo, knee in knees.items():
        print("  %-8s -> %d frame(s)" % (algo, knee))

    anomaly = False
    for algo, faults in series.items():
        for i in range(1, len(faults)):
            if faults[i] > faults[i - 1]:
                anomaly = True
                print("  NOTE: %s shows Belady's anomaly -- faults rose "
                      "from %d to %d when frames went %d -> %d."
                      % (algo, faults[i - 1], faults[i], sweep[i - 1],
                         sweep[i]))
    if not anomaly:
        print("  No Belady's anomaly detected in this sweep "
              "(fault counts are monotonically non-increasing).")

    if ask_yes_no("Save thrashing chart + CSV to output/"):
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        png = visualizer.save_thrashing(
            sweep, series, os.path.join(OUTPUT_DIR, "thrashing_curve.png"),
            knees=knees)
        metrics.save_thrashing_csv(sweep, series, OUTPUT_DIR)
        print("Saved: %s (+ thrashing.csv)" % os.path.basename(png))


# --------------------------------------------------------------------------- #
#  Menu actions -- tests and evidence
# --------------------------------------------------------------------------- #


def run_tests() -> None:
    header("TEST SUITE -- NORMAL / BOUNDARY / INVALID CASES")
    import test_simulator
    ok = test_simulator.run_all_tests(write_file=True, outdir=OUTPUT_DIR)
    print("\nOverall result: %s"
          % ("ALL TESTS PASSED" if ok else "SOME TESTS FAILED -- see above"))
    print("Written to output/test_results.txt")


def generate_evidence() -> None:
    header("GENERATE COMPLETE EVIDENCE PACK (output/)")
    import demo
    files = demo.generate_all(OUTPUT_DIR)
    print("\nEvidence pack written: %d files" % len(files))


# --------------------------------------------------------------------------- #
#  Main loop
# --------------------------------------------------------------------------- #

MENU = """
----------------------------------------------------------------
 1. Show current process workload
 2. Load sample process set (textbook)
 3. Enter a custom process set
 4. Run ALL CPU scheduling algorithms (comparison + charts)
 5. Run ONE scheduling algorithm (detailed trace)
 6. Show / enter page reference string
 7. Run ALL page replacement algorithms (comparison + charts)
 8. INTEGRATED simulation (scheduling linked to memory)
 9. Thrashing analysis (page faults vs frame count)
10. Run test suite (normal / boundary / invalid)
11. Generate complete evidence pack (output/ folder)
 0. Exit
----------------------------------------------------------------"""


def main() -> None:
    state = State()
    print("=" * 74)
    print("   INTEGRATED CPU SCHEDULING + VIRTUAL MEMORY SIMULATOR")
    print("   OS Capstone Project  |  Python 3  |  FCFS / SJF / Priority /")
    print("   RR  +  FIFO / LRU / Optimal")
    print("=" * 74)
    print("Tip: start with option 4, then option 8 for the integrated run.")

    while True:
        print("\nCurrent setup: %s" % state.status_line())
        print(MENU)
        choice = ask_int("Choose an option", minimum=0, maximum=11,
                         default=0)
        try:
            if choice == 0:
                print("Goodbye!")
                return
            elif choice == 1:
                show_processes(state)
            elif choice == 2:
                load_sample_processes(state)
            elif choice == 3:
                enter_processes(state)
            elif choice == 4:
                run_scheduling_all(state)
            elif choice == 5:
                run_scheduling_one(state)
            elif choice == 6:
                show_reference_string(state)
                if ask_yes_no("Enter a new reference string"):
                    enter_reference_string(state)
            elif choice == 7:
                run_memory_all(state)
            elif choice == 8:
                run_integrated(state)
            elif choice == 9:
                run_thrashing(state)
            elif choice == 10:
                run_tests()
            elif choice == 11:
                generate_evidence()
        except validation.InputError as exc:
            print("  x  Input error: %s" % exc)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted -- goodbye!")
        sys.exit(0)
