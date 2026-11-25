"""
test_simulator.py
=================
Self-contained test suite for the Integrated CPU Scheduling + Virtual
Memory Simulator.  No external test framework required -- run it
directly:

    python3 test_simulator.py

The suite covers the three test categories required by the capstone
manual:

    normal_*    -- textbook workloads with hand-computed expected values
    boundary_*  -- edge conditions (1 process, 1 frame, all arrive at 0,
                   frames >= distinct pages, quantum >= max burst ...)
    invalid_*   -- malformed input that must be rejected with a clear
                   InputError (empty list, zero burst, negative arrival,
                   duplicate PID, non-integer reference ...)

Results are printed as a PASS/FAIL table and (optionally) written to
output/test_results.txt for the report's evidence section.
"""

from __future__ import annotations

import os
import sys
from typing import Callable, List, Tuple

import memory
import metrics
import sample_data as sd
import scheduler
import validation
from scheduler import Process

TESTS: List[Tuple[str, Callable[[], None]]] = []


def test(fn):
    """Register a test function."""
    TESTS.append((fn.__name__, fn))
    return fn


def approx(a, b, tol=1e-9):
    assert abs(a - b) <= tol, "expected %.6f, got %.6f" % (b, a)


def expect_input_error(fn, what: str):
    try:
        fn()
    except validation.InputError:
        return
    raise AssertionError("invalid input was accepted: " + what)


# =========================================================================== #
#  NORMAL TEST CASES -- hand-verified textbook values
# =========================================================================== #


@test
def normal_fcfs_textbook_metrics():
    """FCFS on the sample workload: Avg WT 9.60, TAT 14.80, RT 9.60."""
    res = scheduler.fcfs(sd.SAMPLE_PROCESSES)
    s = metrics.summarize(res)
    approx(s["avg_waiting"], 9.60)
    approx(s["avg_turnaround"], 14.80)
    approx(s["avg_response"], 9.60)
    assert s["makespan"] == 26
    assert s["preemptions"] == 0


@test
def normal_sjf_textbook_metrics():
    """SJF on the sample workload: Avg WT 8.00, TAT 13.20."""
    res = scheduler.sjf(sd.SAMPLE_PROCESSES)
    s = metrics.summarize(res)
    approx(s["avg_waiting"], 8.00)
    approx(s["avg_turnaround"], 13.20)


@test
def normal_sjf_execution_order():
    """SJF must run P1, P3, P5, P2, P4 after P1 finishes at t=10."""
    res = scheduler.sjf(sd.SAMPLE_PROCESSES)
    order = [seg.pid for seg in res.gantt if not seg.is_idle]
    assert order == ["P1", "P3", "P5", "P2", "P4"], "got %s" % order


@test
def normal_priority_textbook_metrics():
    """Priority (1 = highest): Avg WT 10.40, TAT 15.60."""
    res = scheduler.priority_scheduling(sd.SAMPLE_PROCESSES)
    s = metrics.summarize(res)
    approx(s["avg_waiting"], 10.40)
    approx(s["avg_turnaround"], 15.60)


@test
def normal_priority_execution_order():
    """Priority order after P1: P2 (pri 1), P4 (pri 2), P3 (pri 4), P5."""
    res = scheduler.priority_scheduling(sd.SAMPLE_PROCESSES)
    order = [seg.pid for seg in res.gantt if not seg.is_idle]
    assert order == ["P1", "P2", "P4", "P3", "P5"], "got %s" % order


@test
def normal_rr_textbook_metrics():
    """RR q=4: Avg WT 12.00, TAT 17.20, RT 5.40, 9 dispatches, 4 preemptions."""
    res = scheduler.round_robin(sd.SAMPLE_PROCESSES, 4)
    s = metrics.summarize(res)
    approx(s["avg_waiting"], 12.00)
    approx(s["avg_turnaround"], 17.20)
    approx(s["avg_response"], 5.40)
    assert s["dispatches"] == 9
    assert s["preemptions"] == 4


@test
def normal_rr_completion_times():
    """RR q=4 completion times: P5 -> 21, P2 -> 22, P1 -> 24, P4 -> 26."""
    res = scheduler.round_robin(sd.SAMPLE_PROCESSES, 4)
    assert res.record("P5").completion == 21
    assert res.record("P2").completion == 22
    assert res.record("P1").completion == 24
    assert res.record("P4").completion == 26


@test
def normal_gantt_timeline_is_continuous():
    """Every algorithm must produce a gapless, non-overlapping timeline."""
    for res in scheduler.run_all(sd.SAMPLE_PROCESSES, 4):
        cursor = 0
        for seg in res.gantt:
            assert seg.start == cursor, \
                "%s: gap/overlap at %d" % (res.algorithm, seg.start)
            assert seg.end > seg.start
            cursor = seg.end
        assert cursor == res.makespan


@test
def normal_metric_identities_hold():
    """For every record: TAT = CT - AT, WT = TAT - BT, RT = WT when the
    algorithm is non-preemptive."""
    for res in (scheduler.fcfs(sd.SAMPLE_PROCESSES),
                scheduler.sjf(sd.SAMPLE_PROCESSES),
                scheduler.priority_scheduling(sd.SAMPLE_PROCESSES),
                scheduler.round_robin(sd.SAMPLE_PROCESSES, 4)):
        for r in res.records:
            assert r.turnaround == r.completion - r.arrival
            assert r.waiting == r.turnaround - r.burst
            assert r.waiting >= 0 and r.response >= 0
        if not res.algorithm.startswith("Round Robin"):
            for r in res.records:
                assert r.response == r.waiting, \
                    "%s %s: RT != WT in non-preemptive run" % (res.algorithm,
                                                               r.pid)


@test
def normal_cpu_utilization_is_correct():
    """Sample workload has no idle time -> 100% utilization everywhere."""
    for res in scheduler.run_all(sd.SAMPLE_PROCESSES, 4):
        s = metrics.summarize(res)
        assert s["busy"] == 26
        approx(s["cpu_utilization"], 100.0)


@test
def normal_fifo_short_reference_string():
    """FIFO, 10-ref manual string, 3 frames -> 9 faults, 1 hit."""
    res = memory.fifo(sd.SAMPLE_REF_SHORT, 3)
    assert res.faults == 9 and res.hits == 1
    approx(res.hit_ratio, 0.1)


@test
def normal_lru_short_reference_string():
    """LRU, 10-ref manual string, 3 frames -> 8 faults, 2 hits."""
    res = memory.lru(sd.SAMPLE_REF_SHORT, 3)
    assert res.faults == 8 and res.hits == 2


@test
def normal_optimal_short_reference_string():
    """Optimal, 10-ref manual string, 3 frames -> 6 faults, 4 hits."""
    res = memory.optimal(sd.SAMPLE_REF_SHORT, 3)
    assert res.faults == 6 and res.hits == 4


@test
def normal_fifo_long_reference_string():
    """FIFO, classic 20-ref string, 3 frames -> 15 faults (Silberschatz)."""
    res = memory.fifo(sd.SAMPLE_REF_LONG, 3)
    assert res.faults == 15


@test
def normal_lru_long_reference_string():
    """LRU, classic 20-ref string, 3 frames -> 12 faults."""
    res = memory.lru(sd.SAMPLE_REF_LONG, 3)
    assert res.faults == 12


@test
def normal_optimal_long_reference_string():
    """Optimal, classic 20-ref string, 3 frames -> 9 faults."""
    res = memory.optimal(sd.SAMPLE_REF_LONG, 3)
    assert res.faults == 9


@test
def normal_optimal_never_worse_than_fifo_or_lru():
    """Optimal is the theoretical minimum -> faults <= FIFO and <= LRU."""
    for frames in (2, 3, 4):
        for refs in (sd.SAMPLE_REF_SHORT, sd.SAMPLE_REF_LONG):
            assert memory.optimal(refs, frames).faults \
                <= memory.fifo(refs, frames).faults
            assert memory.optimal(refs, frames).faults \
                <= memory.lru(refs, frames).faults


# =========================================================================== #
#  BOUNDARY TEST CASES
# =========================================================================== #


@test
def boundary_single_process():
    """One process only: WT = RT = 0, TAT = burst, for FCFS and RR."""
    solo = [Process("P1", 5, 7, 1)]
    for res in (scheduler.fcfs(solo), scheduler.round_robin(solo, 3)):
        r = res.record("P1")
        assert r.waiting == 0 and r.response == 0
        assert r.turnaround == 7
        assert r.completion == 12          # arrival 5 + burst 7


@test
def boundary_all_arrive_at_zero():
    """All 5 processes arrive at t=0: schedules stay valid, FCFS runs in
    PID order."""
    procs = [Process("P%d" % i, 0, b, p) for i, (b, p)
             in enumerate([(10, 3), (5, 1), (2, 4), (6, 2), (3, 5)], 1)]
    for res in scheduler.run_all(procs, 4):
        assert metrics.summarize(res)["makespan"] == 26
    order = [seg.pid for seg in scheduler.fcfs(procs).gantt]
    assert order == ["P1", "P2", "P3", "P4", "P5"]


@test
def boundary_rr_large_quantum_equals_fcfs():
    """RR with quantum >= every burst degenerates to FCFS."""
    rr = scheduler.round_robin(sd.SAMPLE_PROCESSES, 999)
    fc = scheduler.fcfs(sd.SAMPLE_PROCESSES)
    approx(metrics.summarize(rr)["avg_waiting"],
           metrics.summarize(fc)["avg_waiting"])


@test
def boundary_cpu_idle_gap():
    """A gap before the first arrival must appear as idle time."""
    procs = [Process("P1", 4, 3, 1)]
    res = scheduler.fcfs(procs)
    idle = [s for s in res.gantt if s.is_idle]
    assert idle and idle[0].start == 0 and idle[0].end == 4
    s = metrics.summarize(res)
    assert s["idle"] == 4
    approx(s["cpu_utilization"], 3.0 / 7.0 * 100.0)


@test
def boundary_single_frame():
    """With 1 frame every change of page is a fault: [1,2,1,2,1] -> 5."""
    refs = [1, 2, 1, 2, 1]
    for algo in (memory.fifo, memory.lru, memory.optimal):
        res = algo(refs, 1)
        assert res.faults == 5, "%s: %d" % (algo.__name__, res.faults)
        assert res.hits == 0


@test
def boundary_frames_cover_distinct_pages():
    """Frames >= distinct pages -> exactly one fault per distinct page."""
    distinct = len(set(sd.SAMPLE_REF_LONG))          # = 6
    for res in memory.run_all(sd.SAMPLE_REF_LONG, distinct):
        assert res.faults == distinct, \
            "%s: %d != %d" % (res.algorithm, res.faults, distinct)


@test
def boundary_single_page_repeated():
    """[5] x 10 with 3 frames -> 1 fault, 9 hits, hit ratio 90%."""
    res = memory.fifo([5] * 10, 3)
    assert res.faults == 1 and res.hits == 9
    approx(res.hit_ratio, 0.9)


@test
def boundary_equal_burst_tie_break():
    """Equal bursts break the tie by arrival then PID, deterministically."""
    procs = [Process("P1", 0, 4, 1), Process("P2", 0, 4, 1),
             Process("P3", 0, 4, 1)]
    order = [seg.pid for seg in scheduler.sjf(procs).gantt]
    assert order == ["P1", "P2", "P3"]


@test
def boundary_integrated_reference_count_equals_total_burst():
    """The integrated run emits exactly one reference per executed time
    unit, so total refs == total burst."""
    import integrated
    data = integrated.run_integrated(sd.SAMPLE_PROCESSES, 4, 4, 3)
    total_burst = sum(p.burst for p in sd.SAMPLE_PROCESSES)
    for row in data["rows"]:
        assert row["memory_result"].total == total_burst


@test
def boundary_integrated_fcfs_has_contiguous_refs():
    """Under FCFS each process runs in one stretch, so its references
    form one contiguous block; under RR they do not (interleaving)."""
    import integrated
    page_map = integrated.assign_pages(sd.SAMPLE_PROCESSES, 3)

    fcfs_refs, fcfs_owners = integrated.build_reference_string(
        scheduler.fcfs(sd.SAMPLE_PROCESSES), page_map)
    rr_refs, rr_owners = integrated.build_reference_string(
        scheduler.round_robin(sd.SAMPLE_PROCESSES, 4), page_map)

    def blocks(owners, pid):
        idx = [i for i, o in enumerate(owners) if o == pid]
        return idx == list(range(idx[0], idx[-1] + 1))

    for pid in page_map:
        assert blocks(fcfs_owners, pid), "FCFS refs of %s not contiguous" % pid
    assert not blocks(rr_owners, "P1"), "RR refs of P1 should interleave"


@test
def boundary_integrated_per_process_fault_attribution():
    """Faults attributed to owners must sum to the total fault count."""
    import integrated
    from memory import faults_per_owner
    data = integrated.run_integrated(sd.SAMPLE_PROCESSES, 4, 4, 3)
    for row in data["rows"]:
        per = faults_per_owner(row["memory_result"])
        assert sum(per.values()) == row["memory_result"].faults


# =========================================================================== #
#  INVALID INPUT TEST CASES -- must raise InputError, never crash
# =========================================================================== #


@test
def invalid_empty_process_list():
    expect_input_error(
        lambda: validation.validate_processes([]), "empty process list")


@test
def invalid_duplicate_pid():
    procs = [Process("P1", 0, 5, 1), Process("P1", 1, 2, 1)]
    expect_input_error(lambda: validation.validate_processes(procs),
                       "duplicate PID")


@test
def invalid_zero_burst():
    procs = [Process("P1", 0, 0, 1)]
    expect_input_error(lambda: validation.validate_processes(procs),
                       "zero burst")


@test
def invalid_negative_burst():
    procs = [Process("P1", 0, -3, 1)]
    expect_input_error(lambda: validation.validate_processes(procs),
                       "negative burst")


@test
def invalid_negative_arrival():
    procs = [Process("P1", -2, 4, 1)]
    expect_input_error(lambda: validation.validate_processes(procs),
                       "negative arrival")


@test
def invalid_zero_priority():
    procs = [Process("P1", 0, 4, 0)]
    expect_input_error(lambda: validation.validate_processes(procs),
                       "priority 0")


@test
def invalid_empty_pid():
    procs = [Process("", 0, 4, 1)]
    expect_input_error(lambda: validation.validate_processes(procs),
                       "empty PID")


@test
def invalid_zero_quantum():
    expect_input_error(lambda: validation.validate_quantum(0),
                       "quantum 0")


@test
def invalid_negative_quantum():
    expect_input_error(lambda: validation.validate_quantum(-2),
                       "negative quantum")


@test
def invalid_zero_frames():
    expect_input_error(lambda: validation.validate_frames(0),
                       "zero frames")


@test
def invalid_empty_reference_string():
    expect_input_error(lambda: validation.validate_reference_string([]),
                       "empty reference string")


@test
def invalid_negative_page_number():
    expect_input_error(
        lambda: validation.validate_reference_string([7, 0, -1]),
        "negative page number")


@test
def invalid_non_integer_reference():
    expect_input_error(
        lambda: validation.validate_reference_string([7, "a", 1]),
        "letter as page number")


@test
def invalid_parse_reference_rejects_floats_and_letters():
    for bad in ("7 0.5 1", "7 x 1", "", "   ", "7,8,banana"):
        expect_input_error(
            lambda b=bad: validation.parse_reference_string(b),
            "bad token in %r" % bad)


@test
def invalid_pages_per_process_zero():
    expect_input_error(lambda: validation.validate_pages_per_process(0),
                       "zero pages per process")


# =========================================================================== #
#  Runner
# =========================================================================== #


def _category(name: str) -> str:
    for prefix in ("normal_", "boundary_", "invalid_"):
        if name.startswith(prefix):
            return prefix.rstrip("_").capitalize()
    return "Other"


def run_all_tests(write_file: bool = True,
                  outdir: str = "output") -> bool:
    """Run every registered test, print a PASS/FAIL table and return
    True when everything passed."""
    rows = []
    passed = 0
    for name, fn in TESTS:
        try:
            fn()
            rows.append((_category(name), name, "PASS", ""))
            passed += 1
        except AssertionError as exc:
            rows.append((_category(name), name, "FAIL", str(exc)[:70]))
        except Exception as exc:                      # noqa: BLE001
            rows.append((_category(name), name, "ERROR",
                         "%s: %s" % (type(exc).__name__, str(exc)[:50])))

    header = "%-10s %-52s %-6s %s" % ("Category", "Test", "Result",
                                      "Detail")
    line = "-" * len(header)
    body = [header, line]
    for cat, name, status, detail in rows:
        body.append("%-10s %-52s %-6s %s" % (cat, name, status, detail))
    body.append(line)
    body.append("Total: %d tests   Passed: %d   Failed: %d"
                % (len(rows), passed, len(rows) - passed))

    counts = {}
    for cat, _, status, _ in rows:
        key = (cat, status)
        counts[key] = counts.get(key, 0) + 1
    body.append("By category: " + "; ".join(
        "%s %s=%d" % (cat, st, c)
        for (cat, st), c in sorted(counts.items())))
    body.append("Overall: " + ("ALL TESTS PASSED" if passed == len(rows)
                               else "FAILURES PRESENT"))

    text = "\n".join(body)
    print(text)

    if write_file:
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, "test_results.txt")
        with open(path, "w") as f:
            f.write("TEST SUITE RESULTS -- Integrated CPU Scheduling + "
                    "Virtual Memory Simulator\n")
            f.write("(generated by test_simulator.py)\n\n")
            f.write(text + "\n")
    return passed == len(rows)


if __name__ == "__main__":
    ok = run_all_tests(write_file=True,
                       outdir=os.path.join(os.path.dirname(
                           os.path.abspath(__file__)), "output"))
    sys.exit(0 if ok else 1)
