"""Human-readable size and count formatting."""
from __future__ import annotations

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")
_THRESHOLD = 1024.0


def fmt_size(bytes_: int, decimal_places: int = 1) -> str:
    """Return a human-readable size string (e.g. '1.5 GB')."""
    value = float(bytes_)
    for unit in _UNITS[:-1]:
        if abs(value) < _THRESHOLD:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.{decimal_places}f} {unit}"
        value /= _THRESHOLD
    return f"{value:.{decimal_places}f} {_UNITS[-1]}"


def fmt_size_tooltip(bytes_: int) -> str:
    """Return full byte count for tooltip (e.g. '1,572,864 bytes')."""
    return f"{bytes_:,} bytes"


def fmt_count(count: int) -> str:
    """Return a formatted file/folder count (e.g. '1,234')."""
    return f"{count:,}"
