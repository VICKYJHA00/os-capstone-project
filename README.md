# Integrated CPU Scheduling + Virtual Memory Simulator

**Operating Systems Capstone Project** -- a menu-driven Python simulator that
unifies **CPU scheduling** (FCFS, SJF, Priority, Round Robin) with **virtual
memory** (FIFO, LRU, Optimal page replacement) in a single integrated
experiment, so memory performance can be studied *as a function of the CPU
scheduling policy*.

Pure Python 3.8+ -- the only third-party dependency is `matplotlib` for the
charts. No OS-level privileges, no root, nothing to install beyond pip.

---

## 1. Problem Statement

Individual scheduling and paging exercises treat the CPU scheduler and main
memory as independent boxes. In a real system they are coupled: **which
process runs, and for how long, decides which pages get referenced and which
get evicted**. This project simulates that coupling. It runs a workload under
four scheduling policies, derives the page-reference string each policy
produces, pages it through three replacement policies, and reports the
resulting page faults -- plus the classic standalone scheduling and paging
experiments, performance metrics, Gantt charts, thrashing analysis and a full
normal/boundary/invalid test suite.

## 2. OS Concepts Covered

| Area | Concepts exercised |
|---|---|
| CPU scheduling | FCFS, SJF (non-preemptive), Priority, Round Robin, time quantum, preemption, convoy effect |
| Scheduling metrics | waiting / turnaround / response time, CPU utilization, throughput, Gantt chart |
| Virtual memory | paging, page fault, hit ratio, demand paging, working set, locality of reference |
| Page replacement | FIFO, LRU, Optimal (Belady's MIN), Belady's anomaly, stack property |
| Memory analysis | faults vs frame count, thrashing, knee/elbow detection |
| Software engineering | input validation, boundary/invalid testing, CSV evidence, reproducible runs |

## 3. Features (>= 2 significant functionalities, as required)

1. **CPU scheduling suite** -- all four algorithms on one workload with
   per-process tables, Gantt charts (ASCII + PNG) and a side-by-side
   comparison of Avg WT / TAT / RT / CPU utilization / throughput.
2. **Page replacement suite** -- FIFO / LRU / Optimal with step-by-step frame
   tables, hit/fault ratios and comparison charts on any reference string.
3. **Integrated simulation** (the capstone feature) -- each process owns a
   cyclic working set of pages; walking a scheduler's Gantt chart generates
   that policy's reference string; a 4 x 3 (scheduler x replacement) matrix
   of fault counts shows how scheduling decisions degrade or improve memory
   performance.
4. **Thrashing analysis** -- page faults swept against frame count (1..N)
   with knee detection and Belady's anomaly reporting.
5. **Test suite** -- 43 tests in three categories (normal / boundary /
   invalid), runnable from the menu or standalone.
6. **Evidence pack** -- one command regenerates every chart, CSV and
   transcript used in the report.

## 4. Project Structure

```
os-cpu-mem-simulator/
|-- main.py              menu-driven CLI (start here)
|-- scheduler.py         Process/Segment/ProcRecord + FCFS, SJF, Priority, RR
|-- memory.py            PageResult + FIFO, LRU, Optimal (+ fault attribution)
|-- integrated.py        scheduling-linked-to-memory experiment
|-- metrics.py           metrics, console tables, ASCII Gantt, CSV export
|-- visualizer.py        matplotlib charts (Gantt, bars, curves, heatmap)
|-- validation.py        InputError + all input validators / parsers
|-- sample_data.py       textbook workloads (5-process set, 2 ref strings)
|-- test_simulator.py    43-test suite: normal / boundary / invalid
|-- demo.py              regenerates the complete output/ evidence pack
|-- requirements.txt     matplotlib>=3.4 (the only dependency)
|-- README.md            this file
`-- output/              charts (.png), tables (.csv), transcripts (.txt)
```

## 5. Setup and Usage

```bash
# 1. Python 3.8+ and matplotlib
pip install -r requirements.txt

# 2. Interactive menu
python3 main.py

# 3. Regenerate the full evidence pack (output/)
python3 demo.py

# 4. Run the test suite alone
python3 test_simulator.py
```

Menu map:

| Option | What it does |
|---|---|
| 1-3 | show / load / enter the process workload (validated, re-prompts on bad input) |
| 4 | run all four scheduling algorithms + comparison table + charts |
| 5 | one algorithm in detail (tables + Gantt) |
| 6-7 | show / enter reference string; run FIFO vs LRU vs Optimal with frame tables |
| 8 | **integrated simulation** (scheduler x replacement fault matrix + heatmap) |
| 9 | thrashing analysis (faults vs frames, knee, Belady check) |
| 10 | test suite (writes output/test_results.txt) |
| 11 | regenerate the complete evidence pack |

## 6. Algorithms and Pseudocode

All pseudocode appears in the capstone report (`docs/`). Quick summary:

* **FCFS** -- ready queue in arrival order; run to completion. Simple, but
  short jobs queue behind long ones (convoy effect).
* **SJF (non-preemptive)** -- among arrived processes pick the smallest
  burst; provably optimal for average waiting time on a fixed batch.
* **Priority (non-preemptive, 1 = highest)** -- pick the highest priority;
  ties broken by arrival then PID.
* **Round Robin** -- FIFO ready queue, fixed quantum; the preempted process
  re-enters the queue *after* processes that arrived during its slice.
* **FIFO** -- evict the oldest-loaded page (suffers Belady's anomaly).
* **LRU** -- evict the least recently used page (stack algorithm).
* **Optimal** -- evict the page used farthest in the future (theoretical
  lower bound; needs future knowledge).

## 7. Sample Results

Sample workload: P1(0,10,3) P2(1,5,1) P3(3,2,4) P4(5,6,2) P5(8,3,5),
RR quantum 4. Classic reference string (20 refs), 3 frames.

| Algorithm | Avg WT | Avg TAT | Avg RT |
|---|---|---|---|
| FCFS | 9.60 | 14.80 | 9.60 |
| SJF | **8.00** | **13.20** | **8.00** |
| Priority | 10.40 | 15.60 | 10.40 |
| Round Robin (q=4) | 12.00 | 17.20 | 5.40 |

| Replacement | Faults | Hit ratio |
|---|---|---|
| FIFO | 15 | 25% |
| LRU | 12 | 40% |
| Optimal | **9** | 55% |

**Integrated finding** (4 frames, 3 pages/process): every non-preemptive
scheduler produces 14 faults, but Round Robin (q=4) causes **22 faults with
FIFO/LRU (+57%)** and 17 with Optimal (+21%) -- the scheduler's interleaving,
not the replacement policy, is responsible. See
`output/integrated_heatmap.png`.

| Chart | File |
|---|---|
| Gantt charts | `output/gantt_fcfs.png` ... `gantt_rr.png` |
| Scheduling comparison | `output/scheduling_comparison.png` |
| Page fault comparison | `output/page_faults_comparison_short.png`, `..._long.png` |
| Integrated heatmap | `output/integrated_heatmap.png` |
| Thrashing curve | `output/thrashing_curve.png` |

## 8. Testing

`python3 test_simulator.py` runs 43 tests in the three categories the manual
requires:

* **Normal (17)** -- textbook workloads with hand-computed expected metrics
  (e.g. FCFS Avg WT 9.60; FIFO 15 / LRU 12 / Optimal 9 faults on the classic
  20-reference string).
* **Boundary (11)** -- single process, all processes arriving at t=0, RR
  quantum larger than every burst (must equal FCFS), 1 frame, frames >=
  distinct pages, a single page repeated, idle-gap handling, integrated
  reference-string structure.
* **Invalid (15)** -- empty process list, duplicate PIDs, zero/negative
  burst, negative arrival, zero priority, empty PID, zero/negative quantum,
  zero frames, empty/negative/non-integer reference strings, zero pages per
  process. Every case must raise `InputError` with a clear message; the CLI
  re-prompts instead of crashing.

Current status: **43 / 43 PASS** (see `output/test_results.txt`).

## 9. Capstone Requirement Compliance

| # | Requirement | Where it is satisfied |
|---|---|---|
| 1 | Problem statement | README section 1 / report section 1 |
| 2 | OS concepts involved | README section 2 / report section 2 |
| 3 | >= 2 significant functionalities | 6 features (README section 3) |
| 4 | Algorithm / pseudocode | report section 6 (7 algorithms) |
| 5 | Working implementation | `scheduler.py`, `memory.py`, `integrated.py`, ... |
| 6 | Normal test cases | `test_simulator.py` `normal_*` (17 tests) |
| 7 | Boundary test cases | `test_simulator.py` `boundary_*` (11 tests) |
| 8 | Invalid-input handling | `validation.py` + `invalid_*` tests (15) |
| 9 | Performance metrics | WT / TAT / RT / utilization / throughput / faults / hit ratio |
| 10 | Graphs / visualization | 9 PNG charts in `output/` |
| 11 | GitHub repository | upload this folder; suggested layout kept flat and importable |
| 12 | README / documentation | this file + capstone report |
| 13 | Screenshots / output evidence | `output/*.txt` transcripts + charts |
| 14 | Limitations | README section 10 / report section 12 |
| 15 | Future enhancements | README section 11 / report section 13 |
| 16 | Live demonstration | `python3 demo.py` (60-second full walkthrough) |
| 17 | Individual viva | report includes a how-to-demo guide |

## 10. Limitations

* Scheduling is simulated at the algorithm level, not via real OS threads;
  timings are integer time units, not wall-clock microseconds.
* SJF and Priority are non-preemptive (aging / SRTF variants are future work).
* The integrated model assumes perfect per-process locality (cyclic private
  working sets); it does not model shared pages or TLB effects.
* Optimal replacement "cheats" by design -- it is a benchmark, not a real
  policy.
* Belady's anomaly is *reported* when found but no dedicated anomaly hunt
  string is built in.

## 11. Future Enhancements

* SRTF (preemptive SJF) and Priority with aging to show starvation relief.
* Round Robin quantum sweep (auto-tuning the best quantum).
* Shared pages and a TLB model in the integrated simulation.
* Multi-level feedback queue and a working-set-based frame-allocation policy.
* Export charts to PDF and results to a single self-contained HTML report.

## 12. Suggested Team Roles (3-member groups)

* **Member 1 -- core algorithms:** `scheduler.py`, `memory.py`,
  `integrated.py`
* **Member 2 -- interface & visualization:** `main.py`, `visualizer.py`,
  `metrics.py` tables
* **Member 3 -- testing & documentation:** `test_simulator.py`,
  `validation.py`, `demo.py`, README/report, GitHub workflow

All members should be able to explain every module in the viva.
