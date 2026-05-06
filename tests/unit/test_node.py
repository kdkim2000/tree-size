"""Unit tests for Node, CancelToken, ProgressEvent, ScanResult, ScanOptions."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from tree_size.core.node import (
    CancelToken,
    Node,
    ProgressEvent,
    ScanOptions,
    ScanResult,
)


def _make_node(name: str = "test", is_dir: bool = False) -> Node:
    return Node(
        name=name,
        path=Path(f"/{name}"),
        is_dir=is_dir,
        size_logical=100,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
    )


class TestNode:
    def test_file_node_fields(self) -> None:
        n = _make_node("foo.txt", is_dir=False)
        assert n.name == "foo.txt"
        assert not n.is_dir
        assert n.size_logical == 100
        assert n.parent is None
        assert n.children == []

    def test_dir_node_children(self) -> None:
        parent = _make_node("parent", is_dir=True)
        child = _make_node("child", is_dir=False)
        child.parent = parent
        parent.children.append(child)
        assert len(parent.children) == 1
        assert parent.children[0].name == "child"

    def test_flags_default_zero(self) -> None:
        n = _make_node()
        assert n.flags == 0

    def test_compressed_flag_bit0(self) -> None:
        n = _make_node()
        n.flags = 0x1
        assert n.flags & 0x1, "compressed bit (0x1) should be set"

    def test_reparse_flag_bit1(self) -> None:
        n = _make_node()
        n.flags = 0x2
        assert n.flags & 0x2, "reparse point bit (0x2) should be set"

    def test_children_list_is_per_instance(self) -> None:
        # Verify slots=True + field(default_factory=list) avoids mutable default sharing
        n1 = _make_node("a", is_dir=True)
        n2 = _make_node("b", is_dir=True)
        n1.children.append(_make_node("child"))
        assert len(n2.children) == 0, "children lists must be independent per instance"

    def test_path_is_pathlib(self) -> None:
        n = _make_node("file.txt")
        assert isinstance(n.path, Path)

    def test_node_size_fields_are_ints(self) -> None:
        n = _make_node()
        assert isinstance(n.size_logical, int)
        assert isinstance(n.size_allocated, int)
        assert isinstance(n.file_count, int)
        assert isinstance(n.folder_count, int)

    def test_mtime_is_float(self) -> None:
        n = _make_node()
        assert isinstance(n.mtime, float)


class TestProgressEvent:
    def test_fields(self) -> None:
        p = ProgressEvent(
            current_path=Path("/some/path"),
            total_files=42,
            total_bytes=1024,
            elapsed_sec=1.5,
        )
        assert p.current_path == Path("/some/path")
        assert p.total_files == 42
        assert p.total_bytes == 1024
        assert p.elapsed_sec == 1.5


class TestScanResult:
    def test_fields(self) -> None:
        root = _make_node("root", is_dir=True)
        r = ScanResult(
            root=root,
            total_files=10,
            total_bytes=2048,
            elapsed_sec=0.5,
            error_count=0,
        )
        assert r.root is root
        assert r.total_files == 10
        assert r.total_bytes == 2048
        assert r.elapsed_sec == 0.5
        assert r.error_count == 0

    def test_error_count_nonzero(self) -> None:
        root = _make_node("root", is_dir=True)
        r = ScanResult(root=root, total_files=0, total_bytes=0, elapsed_sec=0.0, error_count=3)
        assert r.error_count == 3


class TestCancelToken:
    def test_initial_not_cancelled(self) -> None:
        token = CancelToken()
        assert not token.is_cancelled()

    def test_cancel_sets_flag(self) -> None:
        token = CancelToken()
        token.cancel()
        assert token.is_cancelled()

    def test_cancel_is_idempotent(self) -> None:
        token = CancelToken()
        token.cancel()
        token.cancel()
        assert token.is_cancelled()

    def test_wait_if_paused_returns_immediately_when_not_paused(self) -> None:
        token = CancelToken()
        # Must not block — would time out the test if it did
        token.wait_if_paused()

    def test_pause_blocks_worker_thread(self) -> None:
        token = CancelToken()
        token.pause()
        resumed = threading.Event()

        def _worker() -> None:
            token.wait_if_paused()
            resumed.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        assert not resumed.wait(timeout=0.05), "worker should be blocked while paused"
        token.resume()
        assert resumed.wait(timeout=2.0), "worker should unblock after resume"
        t.join(timeout=3.0)

    def test_resume_unblocks_paused_worker(self) -> None:
        token = CancelToken()
        token.pause()
        unblocked = threading.Event()

        def _worker() -> None:
            token.wait_if_paused()
            unblocked.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        token.resume()
        assert unblocked.wait(timeout=2.0), "resume must unblock wait_if_paused"
        t.join(timeout=3.0)

    def test_cancel_unblocks_paused_worker(self) -> None:
        token = CancelToken()
        token.pause()
        done = threading.Event()

        def _worker() -> None:
            token.wait_if_paused()
            done.set()

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        token.cancel()
        assert done.wait(timeout=2.0), "cancel must unblock a paused worker"
        assert token.is_cancelled()
        t.join(timeout=3.0)

    def test_pause_after_cancel_is_noop(self) -> None:
        """Pausing an already-cancelled token must not re-block wait_if_paused."""
        token = CancelToken()
        token.cancel()
        token.pause()  # should be ignored since already cancelled
        # Must return immediately
        token.wait_if_paused()

    def test_resume_without_pause_is_safe(self) -> None:
        token = CancelToken()
        token.resume()  # should not raise
        assert not token.is_cancelled()


class TestScanOptions:
    def test_defaults(self) -> None:
        opts = ScanOptions()
        assert not opts.follow_symlinks
        assert opts.measure_alloc_size
        assert opts.max_workers >= 1

    def test_custom_values(self) -> None:
        opts = ScanOptions(follow_symlinks=True, measure_alloc_size=False, max_workers=4)
        assert opts.follow_symlinks
        assert not opts.measure_alloc_size
        assert opts.max_workers == 4

    def test_max_workers_positive(self) -> None:
        opts = ScanOptions()
        assert opts.max_workers > 0
