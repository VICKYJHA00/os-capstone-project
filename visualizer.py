"""
visualizer.py
=============
Chart generation (matplotlib) for the Integrated CPU Scheduling +
Virtual Memory Simulator.

Produces the PNG figures used on screen, in the output/ evidence folder
and in the project report:

    save_gantt                 -- one Gantt chart per scheduling algorithm
    save_scheduling_comparison -- grouped bars of Avg WT / TAT / RT
    save_memory_comparison     -- page faults + hit ratio per algorithm
    save_thrashing             -- page faults vs frame count curve
    save_integrated_heatmap    -- faults by scheduler x replacement policy

All figures are saved at 150 dpi with constrained layout; colours are
consistent across charts (process i always gets palette colour i).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")                     # headless rendering, no display needed
import matplotlib.pyplot as plt
import numpy as np

import metrics
from scheduler import ScheduleResult, pid_sort_key
from memory import PageResult

PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
           "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD"]
IDLE_COLOR = "#B8B8B8"

plt.rcParams.update({
    "figure.dpi": 100,
    "savefig.dpi": 150,
    "font.size": 10,
    "axes.titlesize": 11.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "axes.grid": True,
    "grid.alpha": 0.30,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
})


def _pid_colors(records) -> Dict[str, str]:
    """Stable PID -> colour mapping shared by every chart."""
    ordered = sorted(records, key=lambda r: pid_sort_key(r.pid))
    return {r.pid: PALETTE[i % len(PALETTE)] for i, r in enumerate(ordered)}


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d:
        os.makedirs(d, exist_ok=True)


# --------------------------------------------------------------------------- #
#  1. Gantt chart
# --------------------------------------------------------------------------- #


def save_gantt(result: ScheduleResult, path: str) -> str:
    """Draw the classic single-lane Gantt chart for one schedule."""
    colors = _pid_colors(result.records)
    s = metrics.summarize(result)
    makespan = result.makespan or 1

    fig, ax = plt.subplots(figsize=(10, 3.4), constrained_layout=True)
    for seg in result.gantt:
        if seg.is_idle:
            ax.broken_barh([(seg.start, seg.duration)], (-0.32, 0.64),
                           facecolors=IDLE_COLOR, edgecolor="white",
                           hatch="//", linewidth=1.0)
            ax.text((seg.start + seg.end) / 2, 0, "idle", ha="center",
                    va="center", fontsize=8, color="#404040")
        else:
            ax.broken_barh([(seg.start, seg.duration)], (-0.32, 0.64),
                           facecolors=colors[seg.pid], edgecolor="white",
                           linewidth=1.2)
            if seg.duration / makespan >= 0.075:
                # wide enough for the label inside the bar
                ax.text((seg.start + seg.end) / 2, 0, seg.pid, ha="center",
                        va="center", fontsize=9, fontweight="bold",
                        color="white")
            else:
                # narrow segment: print the PID just above the bar
                ax.text((seg.start + seg.end) / 2, 0.52, seg.pid,
                        ha="center", va="bottom", fontsize=8,
                        fontweight="bold", color="#000000")

    boundaries = sorted({seg.start for seg in result.gantt}
                        | {seg.end for seg in result.gantt})
    ax.set_xticks(boundaries)
    ax.set_xticklabels([str(b) for b in boundaries], fontsize=8)
    ax.set_yticks([])
    ax.set_xlabel("Time units")
    ax.set_xlim(-0.5, result.makespan + 0.5)
    ax.set_ylim(-0.75, 0.95)
    ax.set_title("%s -- Gantt chart\nAvg WT %.2f | Avg TAT %.2f | "
                 "Avg RT %.2f | CPU utilization %.1f%%"
                 % (result.algorithm, s["avg_waiting"], s["avg_turnaround"],
                    s["avg_response"], s["cpu_utilization"]), fontsize=11)

    _ensure_dir(path)
    fig.savefig(path)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
#  2. Scheduling comparison
# --------------------------------------------------------------------------- #


def save_scheduling_comparison(results: List[ScheduleResult], path: str) -> str:
    """Grouped bar chart: Avg WT / Avg TAT / Avg RT for every algorithm."""
    sums = [metrics.summarize(r) for r in results]
    names = [s["algorithm"] for s in sums]
    series = [("avg_waiting", "Avg waiting time"),
              ("avg_turnaround", "Avg turnaround time"),
              ("avg_response", "Avg response time")]

    x = np.arange(len(names))
    width = 0.26
    fig, ax = plt.subplots(figsize=(9.2, 4.2), constrained_layout=True)
    for i, (key, label) in enumerate(series):
        vals = [s[key] for s in sums]
        bars = ax.bar(x + (i - 1) * width, vals, width, label=label,
                      color=PALETTE[i], edgecolor="white")
        ax.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel("Time units")
    ax.set_title("CPU scheduling algorithms -- performance comparison "
                 "(sample workload)")
    ax.set_ylim(0, max(s["avg_turnaround"] for s in sums) * 1.28)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))

    _ensure_dir(path)
    fig.savefig(path)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
#  3. Page replacement comparison
# --------------------------------------------------------------------------- #


def save_memory_comparison(pres_list: List[PageResult], title: str,
                           path: str) -> str:
    """Two panels: page faults (lower is better) and hit ratio %."""
    names = [p.algorithm for p in pres_list]
    faults = [p.faults for p in pres_list]
    hit_pct = [p.hit_ratio * 100 for p in pres_list]

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9),
                             constrained_layout=True)

    bars = axes[0].bar(names, faults, color=PALETTE[:len(names)],
                       edgecolor="white", width=0.62)
    axes[0].bar_label(bars, fontsize=10, fontweight="bold", padding=2)
    axes[0].set_title("Page faults (lower is better)")
    axes[0].set_ylabel("Faults")
    axes[0].set_ylim(0, max(faults) * 1.22)

    bars2 = axes[1].bar(names, hit_pct, color=PALETTE[:len(names)],
                        edgecolor="white", width=0.62)
    axes[1].bar_label(bars2, fmt="%.1f%%", fontsize=10, fontweight="bold",
                      padding=2)
    axes[1].set_title("Hit ratio (higher is better)")
    axes[1].set_ylabel("Hit ratio (%)")
    axes[1].set_ylim(0, 108)

    fig.suptitle(title, fontsize=12, fontweight="bold")

    _ensure_dir(path)
    fig.savefig(path)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
#  4. Thrashing curve
# --------------------------------------------------------------------------- #


def save_thrashing(frames: List[int], series: Dict[str, List[int]],
                   path: str, knees: Optional[Dict[str, int]] = None) -> str:
    """Page faults vs frame count for each algorithm, with knee markers."""
    fig, ax = plt.subplots(figsize=(8.6, 4.4), constrained_layout=True)
    for i, (name, faults) in enumerate(series.items()):
        ax.plot(frames, faults, marker="o", linewidth=2, markersize=5,
                color=PALETTE[i], label=name)
    if knees:
        for i, (name, knee) in enumerate(knees.items()):
            faults = series[name]
            idx = frames.index(knee) if knee in frames else -1
            if idx >= 0:
                ax.plot(knee, faults[idx], marker="*", markersize=16,
                        color=PALETTE[i], markeredgecolor="#333333",
                        zorder=5)
        ax.axvline(min(knees.values()), color="#888888", linestyle="--",
                   linewidth=1)
        ax.annotate("knee ~ %d frame(s)" % min(knees.values()),
                    xy=(min(knees.values()),
                        max(max(v) for v in series.values())),
                    xytext=(6, -2), textcoords="offset points",
                    fontsize=9, color="#555555")

    ax.set_xlabel("Number of memory frames allocated")
    ax.set_ylabel("Page faults")
    ax.set_title("Thrashing analysis -- page faults vs frame count")
    ax.set_xticks(frames)
    ax.set_ylim(0, max(max(v) for v in series.values()) * 1.15)
    ax.legend(loc="upper right")

    _ensure_dir(path)
    fig.savefig(path)
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
#  5. Integrated heatmap
# --------------------------------------------------------------------------- #


def save_integrated_heatmap(rows: List[Dict], path: str) -> str:
    """Faults for every (scheduler, replacement policy) combination."""
    sched_names = [r["sched_result"].algorithm for r in rows[::3]]
    algo_names = [r["memory_result"].algorithm for r in rows[:3]]
    data = np.array([[row["memory_result"].faults
                      for row in rows[i * 3:i * 3 + 3]]
                     for i in range(len(sched_names))])

    fig, ax = plt.subplots(figsize=(7.4, 4.4), constrained_layout=True)
    im = ax.imshow(data, cmap="Reds", aspect="auto", vmin=0)

    threshold = data.max() * 0.62 if data.max() else 0
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(data[i, j]), ha="center", va="center",
                    fontsize=11, fontweight="bold",
                    color="white" if data[i, j] > threshold else "#333333")

    ax.set_xticks(range(len(algo_names)))
    ax.set_xticklabels(algo_names)
    ax.set_yticks(range(len(sched_names)))
    ax.set_yticklabels(sched_names, fontsize=9)
    ax.set_xlabel("Page replacement policy")
    ax.set_ylabel("CPU scheduling policy")
    ax.set_title("Integrated simulation -- page faults by\n"
                 "scheduling policy x replacement policy", fontsize=11)
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Page faults", shrink=0.85)

    _ensure_dir(path)
    fig.savefig(path)
    plt.close(fig)
    return path
