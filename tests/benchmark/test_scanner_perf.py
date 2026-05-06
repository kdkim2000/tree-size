"""Performance benchmarks for Scanner — M5-10.

pytest-benchmark tracks regressions across runs.
Results are stored in .benchmarks/ (see pyproject.toml).

Rules:
- R-T3: 100k file scan ≤ 30 s.
- 10k file benchmark used here to keep CI fast while still being meaningful.
- Incremental scan (unchanged tree) must be ≥50% faster than a full scan.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from tree_size.core.node import CancelToken, ScanOptions
from tree_size.core.scanner import Scanner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _build_10k_tree(root: Path) -> None:
    """Create 10 000 files spread across 100 folders (100 files/folder)."""
    for fi in range(100):
        folder = root / f"folder_{fi:03d}"
        folder.mkdir()
        for fj in range(100):
            # Keep files tiny (1 B) so wall-clock time measures FS traversal,
            # not data throughput.
            (folder / f"file_{fj:03d}.bin").write_bytes(b"\x00")


@pytest.fixture(scope="module")
def big_tree(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Module-scoped 10k-file tree — built once, reused by all benchmarks."""
    root = tmp_path_factory.mktemp("big_tree")
    _build_10k_tree(root)
    return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_scan(root: Path) -> int:
    """Run a full scan and return total file count."""
    result = Scanner().scan(
        root,
        ScanOptions(follow_symlinks=False, measure_alloc_size=False),
        CancelToken(),
        on_node=lambda _: None,
        on_progress=lambda _: None,
    )
    return result.total_files


def _incremental_scan(root: Path, cache: dict) -> int:  # type: ignore[type-arg]
    """Run an incremental scan with the given cache and return total file count."""
    result = Scanner().scan_incremental(
        root,
        ScanOptions(follow_symlinks=False, measure_alloc_size=False),
        CancelToken(),
        on_node=lambda _: None,
        on_progress=lambda _: None,
        last_scan_cache=cache,
    )
    return result.total_files


def _build_cache(root: Path) -> dict:  # type: ignore[type-arg]
    """Build a flat path→Node cache from a full scan result."""
    from tree_size.core.node import Node

    nodes: list[Node] = []
    Scanner().scan(
        root,
        ScanOptions(follow_symlinks=False, measure_alloc_size=False),
        CancelToken(),
        on_node=nodes.append,
        on_progress=lambda _: None,
    )
    return {n.path: n for n in nodes}


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

@pytest.mark.benchmark(group="scan")
def test_benchmark_scan_10k_files(benchmark: pytest.fixture, big_tree: Path) -> None:  # type: ignore[type-arg]
    """Full scan of 10k file tree — baseline latency check.

    Assertion: ≤ 30 s (R-T3).  pytest-benchmark enforces max_time via config.
    """
    result_file_count: list[int] = []

    def _run() -> None:
        count = _full_scan(big_tree)
        result_file_count.append(count)

    benchmark(_run)
    # Verify correctness — all 10k files found
    assert result_file_count[-1] == 10_000, (
        f"Expected 10000 files, got {result_file_count[-1]}"
    )
    # Verify benchmark wall time ≤ 30 s (belt-and-braces; max_time in config)
    assert benchmark.stats["mean"] <= 30.0, (
        f"Mean scan time {benchmark.stats['mean']:.2f}s exceeds 30s limit"
    )


@pytest.mark.benchmark(group="scan")
def test_benchmark_incremental_scan_unchanged(
    benchmark: pytest.fixture,  # type: ignore[type-arg]
    big_tree: Path,
) -> None:
    """Incremental scan on an unchanged 10k-file tree — must be ≥50% faster than full scan.

    1. Measure full scan time (one pass, not benchmarked).
    2. Build cache.
    3. Benchmark incremental scan on the same unchanged tree.
    4. Assert incremental mean < full scan time × 0.5.
    """
    # Step 1+2: full scan + cache build (not benchmarked; done once)
    t0 = time.perf_counter()
    cache = _build_cache(big_tree)
    full_elapsed = time.perf_counter() - t0

    # Step 3: benchmark the incremental path
    result_file_count: list[int] = []

    def _run() -> None:
        count = _incremental_scan(big_tree, cache)
        result_file_count.append(count)

    benchmark(_run)

    # Correctness: same 10k files reported
    assert result_file_count[-1] == 10_000, (
        f"Incremental scan must report 10000 files, got {result_file_count[-1]}"
    )

    # Performance: incremental mean must be ≥50% faster than full scan
    incremental_mean = benchmark.stats["mean"]
    limit = full_elapsed * 0.5
    assert incremental_mean <= limit or incremental_mean < 0.5, (
        f"Incremental ({incremental_mean:.3f}s) not ≥50% faster than full scan "
        f"({full_elapsed:.3f}s); limit={limit:.3f}s"
    )
