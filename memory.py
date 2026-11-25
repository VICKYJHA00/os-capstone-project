"""
memory.py
=========
Virtual-memory page replacement algorithms for the Integrated CPU
Scheduling + Virtual Memory Simulator (OS Capstone Project).

Implements the three classic demand-paging policies:

    1. FIFO    -- evict the page that was loaded earliest
    2. LRU     -- evict the least recently used page
    3. Optimal -- evict the page whose next use lies farthest in the
                  future (Belady's theoretical optimum; needs future
                  knowledge, so it is only a benchmark)

Every algorithm returns a PageResult with:

    faults / hits   : final counters
    hit_ratio       : hits / total references
    fault_ratio     : faults / total references
    trace           : one row per reference showing the page, the result
                      (HIT/FAULT), the full frame contents afterwards and
                      the page that was evicted (if any)

`owners` optionally records which process made each reference; it is used
by the integrated simulation (integrated.py) to attribute page faults to
processes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PageResult:
    """Result of one page-replacement simulation run."""
    algorithm: str
    frames: int
    references: List[int]
    owners: Optional[List[str]] = None          # pid per reference (optional)
    faults: int = 0
    hits: int = 0
    trace: List[Dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.references)

    @property
    def hit_ratio(self) -> float:
        return self.hits / self.total if self.total else 0.0

    @property
    def fault_ratio(self) -> float:
        return self.faults / self.total if self.total else 0.0


def _row(index: int, page: int, hit: bool, frames: List[int],
         evicted: Optional[int], capacity: int) -> Dict:
    """Build one trace row, padding the frame list to full capacity."""
    padded = list(frames) + [None] * (capacity - len(frames))
    return {"ref": index + 1,           # 1-based reference number
            "page": page,
            "hit": hit,
            "frames": tuple(padded),
            "evicted": evicted}


# --------------------------------------------------------------------------- #
#  1. FIFO -- First In, First Out
# --------------------------------------------------------------------------- #


def fifo(references: List[int], num_frames: int) -> PageResult:
    """FIFO: the page loaded earliest is the eviction victim."""
    result = PageResult("FIFO", num_frames, list(references))
    frames: List[int] = []                       # index 0 = oldest page

    for i, page in enumerate(references):
        if page in frames:
            result.hits += 1
            result.trace.append(_row(i, page, True, frames, None, num_frames))
        else:
            result.faults += 1
            evicted = None
            if len(frames) == num_frames:        # memory full -> evict oldest
                evicted = frames.pop(0)
            frames.append(page)
            result.trace.append(_row(i, page, False, frames, evicted,
                                     num_frames))
    return result


# --------------------------------------------------------------------------- #
#  2. LRU -- Least Recently Used
# --------------------------------------------------------------------------- #


def lru(references: List[int], num_frames: int) -> PageResult:
    """LRU: evict the page that has gone unused for the longest time.

    The frames list is kept in recency order -- least recently used first,
    most recently used last -- so the victim is always frames[0].
    """
    result = PageResult("LRU", num_frames, list(references))
    frames: List[int] = []                       # LRU order: oldest use first

    for i, page in enumerate(references):
        if page in frames:
            result.hits += 1
            frames.remove(page)                  # refresh recency:
            frames.append(page)                  # move to "most recent" end
            result.trace.append(_row(i, page, True, frames, None, num_frames))
        else:
            result.faults += 1
            evicted = None
            if len(frames) == num_frames:
                evicted = frames.pop(0)          # least recently used page
            frames.append(page)
            result.trace.append(_row(i, page, False, frames, evicted,
                                     num_frames))
    return result


# --------------------------------------------------------------------------- #
#  3. Optimal (Belady's MIN)
# --------------------------------------------------------------------------- #


def _farthest_next_use(frames: List[int], references: List[int],
                       current: int) -> int:
    """Return the frame whose next use lies farthest in the future.

    A page that is never referenced again is the perfect victim
    (distance = infinity).
    """
    best, best_distance = None, -1
    for f in frames:
        distance = float("inf")
        for j in range(current + 1, len(references)):
            if references[j] == f:
                distance = j - current
                break
        if distance > best_distance:
            best, best_distance = f, distance
    return best


def optimal(references: List[int], num_frames: int) -> PageResult:
    """Optimal: replace the page that will not be used for the longest
    period of time.  Requires future knowledge, so it serves as the
    theoretical lower bound on page faults."""
    result = PageResult("Optimal", num_frames, list(references))
    frames: List[int] = []

    for i, page in enumerate(references):
        if page in frames:
            result.hits += 1
            result.trace.append(_row(i, page, True, frames, None, num_frames))
            continue

        result.faults += 1
        evicted = None
        if len(frames) < num_frames:
            frames.append(page)                  # free frame still available
        else:
            evicted = _farthest_next_use(frames, references, i)
            frames.remove(evicted)
            frames.append(page)
        result.trace.append(_row(i, page, False, frames, evicted, num_frames))
    return result


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #


def run_all(references: List[int], num_frames: int) -> List[PageResult]:
    """Run all three algorithms on the same reference string."""
    return [fifo(references, num_frames),
            lru(references, num_frames),
            optimal(references, num_frames)]


_ALGORITHMS = {"fifo": fifo, "lru": lru, "optimal": optimal}


def simulate(name: str, references: List[int],
             num_frames: int) -> PageResult:
    """Run one algorithm selected by (case-insensitive) name."""
    key = name.strip().lower()
    if key not in _ALGORITHMS:
        raise ValueError("unknown page replacement algorithm: %r "
                         "(expected one of FIFO / LRU / Optimal)" % name)
    return _ALGORITHMS[key](references, num_frames)


def faults_per_owner(result: PageResult) -> Dict[str, int]:
    """Attribute every page fault to the process that caused it.

    Requires result.owners to be set (integrated simulation mode).
    """
    if result.owners is None:
        raise ValueError("owners not attached -- run via integrated.py")
    per: Dict[str, int] = {}
    for row in result.trace:
        if not row["hit"]:
            owner = result.owners[row["ref"] - 1]
            per[owner] = per.get(owner, 0) + 1
    return dict(sorted(per.items(), key=lambda kv: (len(kv[0]), kv[0])))
