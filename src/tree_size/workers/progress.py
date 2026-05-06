"""Progress tracking and ETA calculation for scan workers.

ProgressTracker is instantiated once per ScanWorker and updated on every
ProgressEvent emitted by the scanner.  It uses a sliding window of the last
10 samples to compute a recent-rate ETA, which avoids early-scan bias on
very large trees.

No Qt imports — this module is pure Python so it can be unit-tested without
a QApplication instance.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class ProgressStats:
    elapsed_sec: float
    estimated_remaining_sec: float | None
    files_per_sec: float
    bytes_per_sec: float

    @property
    def total_estimated_sec(self) -> float | None:
        """Elapsed + remaining, or None when ETA is not yet available."""
        if self.estimated_remaining_sec is None:
            return None
        return self.elapsed_sec + self.estimated_remaining_sec


class ProgressTracker:
    """Sliding-window ETA estimator for an ongoing directory scan.

    ETA is computed from the average file rate over the most-recent 10
    history samples.  To avoid a wild early estimate we suppress ETA for
    the first two seconds and until at least two history points exist with
    a measurable rate difference.

    The remaining-time formula uses a fixed horizon of 120 s worth of files
    at the observed rate, which gives a conservative upper-bound placeholder
    when the true total is not known in advance.  The UI should treat the
    value as "at least this long" rather than an exact countdown.

    Thread-safety: this class is not thread-safe.  It must be accessed only
    from the single worker thread that drives the scan.
    """

    # Suppress ETA for the first N seconds of scanning.
    _WARMUP_SEC: float = 2.0

    # Minimum recent file rate (files/s) before we bother producing an ETA.
    _MIN_RATE: float = 0.05

    # How many history samples to keep total; sliding window uses the last 10.
    _MAX_HISTORY: int = 100

    def __init__(self) -> None:
        self._start_time: float = time.monotonic()
        # Each element: (elapsed_sec, total_files, total_bytes)
        self._history: list[tuple[float, int, int]] = []

    def update(self, elapsed_sec: float, total_files: int, total_bytes: int) -> ProgressStats:
        """Record a new data point and return current stats with ETA.

        Parameters
        ----------
        elapsed_sec:
            Seconds since scan start, taken from ProgressEvent.elapsed_sec.
        total_files:
            Cumulative file count so far.
        total_bytes:
            Cumulative logical bytes so far.
        """
        self._history.append((elapsed_sec, total_files, total_bytes))
        if len(self._history) > self._MAX_HISTORY:
            self._history.pop(0)

        files_per_sec = total_files / elapsed_sec if elapsed_sec > 0 else 0.0
        bytes_per_sec = total_bytes / elapsed_sec if elapsed_sec > 0 else 0.0

        estimated_remaining: float | None = None

        # Require warm-up period and at least 2 samples before estimating.
        if (
            elapsed_sec >= self._WARMUP_SEC
            and len(self._history) >= 2
            and files_per_sec > self._MIN_RATE
        ):
            window = self._history[-10:]
            t_vals = [t for t, _, _ in window]
            f_vals = [f for _, f, _ in window]

            # Only compute rate when we have distinct time and file values.
            if len(set(f_vals)) > 1 and t_vals[-1] > t_vals[0]:
                avg_file_rate = (f_vals[-1] - f_vals[0]) / (t_vals[-1] - t_vals[0])
                if avg_file_rate >= self._MIN_RATE:
                    # 120-second horizon: how long to process another 120 s
                    # worth of files at the current observed rate.
                    estimated_remaining = 120.0 / avg_file_rate

        return ProgressStats(
            elapsed_sec=elapsed_sec,
            estimated_remaining_sec=estimated_remaining,
            files_per_sec=files_per_sec,
            bytes_per_sec=bytes_per_sec,
        )


def format_eta(seconds: float | None) -> str:
    """Format a duration in seconds to a human-readable ETA string.

    Returns
    -------
    str
        Examples: ``'—'``, ``'45s'``, ``'3m 05s'``, ``'2h 30m'``.

    Parameters
    ----------
    seconds:
        Remaining seconds, or ``None`` when ETA is unavailable.
    """
    if seconds is None or seconds < 0:
        return "—"  # em dash: —
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs:02d}s" if secs else f"{minutes}m"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}h {minutes:02d}m" if minutes else f"{hours}h"
