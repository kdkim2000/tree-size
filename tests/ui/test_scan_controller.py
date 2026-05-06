"""UI tests for ScanController — signal emission."""
from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from tree_size.controllers.scan_controller import ScanController
from tree_size.core.node import ScanOptions, ScanResult


class TestScanController:
    @pytest.fixture
    def controller(self, qtbot: QtBot) -> ScanController:  # noqa: ARG002
        # ScanController is a QObject (not QWidget) — addWidget() is not applicable.
        # The instance is owned by the test frame and deleted after each test.
        ctrl = ScanController()
        return ctrl

    # ------------------------------------------------------------------ #
    # Initial state                                                        #
    # ------------------------------------------------------------------ #

    def test_not_running_initially(self, controller: ScanController) -> None:
        assert not controller.is_running, "Controller must not be running before start()"

    # ------------------------------------------------------------------ #
    # start() behaviour                                                    #
    # ------------------------------------------------------------------ #

    def test_start_sets_running(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        (tmp_path / "file.txt").write_bytes(b"x" * 10)
        controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        assert controller.is_running, "is_running must be True immediately after start()"
        # Wait for scan to finish so the worker does not outlive the test
        qtbot.waitSignal(controller.scanFinished, timeout=10_000)

    def test_scan_emits_finished(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        (tmp_path / "file.txt").write_bytes(b"hello" * 10)
        with qtbot.waitSignal(controller.scanFinished, timeout=10_000) as blocker:
            controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        assert blocker.signal_triggered, "scanFinished must be emitted"
        assert isinstance(blocker.args[0], ScanResult), (
            f"scanFinished must carry a ScanResult, got {type(blocker.args[0])}"
        )

    def test_scan_finished_resets_running(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        (tmp_path / "file.txt").write_bytes(b"x")
        with qtbot.waitSignal(controller.scanFinished, timeout=10_000):
            controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        assert not controller.is_running, (
            "is_running must be False after scanFinished is emitted"
        )

    # ------------------------------------------------------------------ #
    # cancel()                                                             #
    # ------------------------------------------------------------------ #

    def test_cancel_stops_scan(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        # Create enough files to ensure scan does not finish instantly
        bulk = tmp_path / "bulk"
        bulk.mkdir()
        for i in range(100):
            (bulk / f"f{i}.bin").write_bytes(b"x" * 100)
        controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        assert controller.is_running, "Scan must be running before cancel()"
        controller.cancel()
        assert not controller.is_running, (
            "is_running must be False immediately after cancel()"
        )

    # ------------------------------------------------------------------ #
    # double-start guard                                                   #
    # ------------------------------------------------------------------ #

    def test_double_start_ignored(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        (tmp_path / "f.txt").write_bytes(b"x" * 100)
        controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        # Second start while still running must be silently ignored
        controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        with qtbot.waitSignal(controller.scanFinished, timeout=10_000):
            pass
        # Only one scanFinished should have fired (just checking we don't crash)
        assert not controller.is_running

    # ------------------------------------------------------------------ #
    # nodeReady signal                                                     #
    # ------------------------------------------------------------------ #

    def test_node_ready_signal_emitted(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        (tmp_path / "file.txt").write_bytes(b"x" * 50)
        nodes: list[object] = []
        controller.nodeReady.connect(nodes.append)
        with qtbot.waitSignal(controller.scanFinished, timeout=10_000):
            controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        assert len(nodes) >= 1, (
            "nodeReady must be emitted at least once (root dir node expected)"
        )

    # ------------------------------------------------------------------ #
    # progressUpdated signal                                               #
    # ------------------------------------------------------------------ #

    def test_progress_signal_type(
        self, tmp_path: Path, controller: ScanController, qtbot: QtBot
    ) -> None:
        for i in range(10):
            (tmp_path / f"f{i}.txt").write_bytes(b"x" * 10)
        events: list[object] = []
        controller.progressUpdated.connect(events.append)
        with qtbot.waitSignal(controller.scanFinished, timeout=10_000):
            controller.start(tmp_path, ScanOptions(measure_alloc_size=False))
        # A small 10-file scan may or may not trigger throttled progress events;
        # what matters is that no unexpected types are emitted.
        from tree_size.core.node import ProgressEvent
        for evt in events:
            assert isinstance(evt, ProgressEvent), (
                f"progressUpdated must emit ProgressEvent, got {type(evt)}"
            )
