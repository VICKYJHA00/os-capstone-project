"""
validation.py
=============
Input validation for the Integrated CPU Scheduling + Virtual Memory
Simulator.

Every user-supplied value passes through one of the validators below
before it reaches an algorithm.  Invalid input raises InputError with a
clear, user-facing message; the CLI catches it and re-prompts, so the
program never crashes on bad data.
"""

from __future__ import annotations

from typing import List

from scheduler import Process


class InputError(ValueError):
    """Raised when user input is invalid.  The message is shown to the
    user directly, so it must be plain and actionable."""


# --------------------------------------------------------------------------- #
#  Validators
# --------------------------------------------------------------------------- #


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_processes(processes: List[Process]) -> None:
    """Validate a process list (used before any scheduling run)."""
    if not processes:
        raise InputError("The process list is empty -- at least one "
                         "process is required.")

    seen = set()
    for p in processes:
        if not p.pid or not str(p.pid).strip():
            raise InputError("A PID cannot be empty.")

        if p.pid in seen:
            raise InputError("Duplicate PID '%s' -- every process needs a "
                             "unique PID." % p.pid)
        seen.add(p.pid)

        if not _is_int(p.arrival):
            raise InputError("%s: arrival time must be a whole number "
                             "(got %r)." % (p.pid, p.arrival))
        if p.arrival < 0:
            raise InputError("%s: arrival time cannot be negative "
                             "(got %d)." % (p.pid, p.arrival))

        if not _is_int(p.burst):
            raise InputError("%s: burst time must be a whole number "
                             "(got %r)." % (p.pid, p.burst))
        if p.burst < 1:
            raise InputError("%s: burst time must be at least 1 "
                             "(got %d)." % (p.pid, p.burst))

        if not _is_int(p.priority):
            raise InputError("%s: priority must be a whole number "
                             "(got %r)." % (p.pid, p.priority))
        if p.priority < 1:
            raise InputError("%s: priority must be >= 1, where 1 is the "
                             "highest priority (got %d)." % (p.pid,
                                                             p.priority))


def validate_quantum(quantum: int) -> None:
    if not _is_int(quantum):
        raise InputError("Time quantum must be a whole number (got %r)."
                         % (quantum,))
    if quantum < 1:
        raise InputError("Time quantum must be at least 1 (got %d)."
                         % quantum)


def validate_frames(frames: int) -> None:
    if not _is_int(frames):
        raise InputError("Number of frames must be a whole number "
                         "(got %r)." % (frames,))
    if frames < 1:
        raise InputError("Number of frames must be at least 1 (got %d)."
                         % frames)


def validate_reference_string(references: List[int]) -> None:
    if not references:
        raise InputError("The reference string is empty -- enter at least "
                         "one page number.")
    for i, page in enumerate(references, start=1):
        if not _is_int(page):
            raise InputError("Reference %d is not a valid page number: %r "
                             "-- pages must be whole numbers." % (i, page))
        if page < 0:
            raise InputError("Reference %d is negative: %d -- page numbers "
                             "cannot be negative." % (i, page))


def validate_pages_per_process(count: int) -> None:
    if not _is_int(count):
        raise InputError("Pages per process must be a whole number "
                         "(got %r)." % (count,))
    if count < 1:
        raise InputError("Pages per process must be at least 1 (got %d)."
                         % count)


# --------------------------------------------------------------------------- #
#  Parsing helpers
# --------------------------------------------------------------------------- #


def parse_reference_string(text: str) -> List[int]:
    """Parse '7 0 1 2, 0 3' into [7, 0, 1, 2, 0, 3].

    Raises InputError for empty input or anything that is not a whole
    number (floats, letters, symbols are all rejected).
    """
    if text is None:
        raise InputError("No input received.")
    cleaned = text.replace(",", " ").replace(";", " ").split()
    if not cleaned:
        raise InputError("No page numbers found -- enter numbers separated "
                         "by spaces or commas, e.g.  7 0 1 2 0 3.")
    pages: List[int] = []
    for token in cleaned:
        try:
            value = int(token)
        except ValueError:
            raise InputError("'%s' is not a valid page number -- enter "
                             "whole numbers only." % token)
        pages.append(value)
    validate_reference_string(pages)
    return pages
