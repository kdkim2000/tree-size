"""Unit tests for CsvExporter (exporters/csv_exporter.py).

CsvExporter.export() accepts list[Node] — pass [root] for single-tree tests.
Covers PRD F-8 (CSV export). Uses real tmp_path writes; no mocking.
"""
from __future__ import annotations

import csv
from pathlib import Path

from tree_size.core.node import Node
from tree_size.exporters.csv_exporter import CsvExporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flat_tree() -> Node:
    """root (dir, 1000 B) with two file children (500 B each)."""
    root = Node(
        name="root",
        path=Path("/root"),
        is_dir=True,
        size_logical=1000,
        size_allocated=4096,
        file_count=2,
        folder_count=0,
        mtime=0.0,
    )
    child1 = Node(
        name="file1.txt",
        path=Path("/root/file1.txt"),
        is_dir=False,
        size_logical=500,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
        parent=root,
    )
    child2 = Node(
        name="file2.txt",
        path=Path("/root/file2.txt"),
        is_dir=False,
        size_logical=500,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
        parent=root,
    )
    root.children = [child1, child2]
    return root


def _make_deep_tree() -> Node:
    """root -> subdir -> leaf.bin (3-level depth)."""
    root = Node(
        name="root",
        path=Path("/root"),
        is_dir=True,
        size_logical=2048,
        size_allocated=4096,
        file_count=1,
        folder_count=1,
        mtime=0.0,
    )
    subdir = Node(
        name="subdir",
        path=Path("/root/subdir"),
        is_dir=True,
        size_logical=2048,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
        parent=root,
    )
    leaf = Node(
        name="leaf.bin",
        path=Path("/root/subdir/leaf.bin"),
        is_dir=False,
        size_logical=2048,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
        parent=subdir,
    )
    subdir.children = [leaf]
    root.children = [subdir]
    return root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCsvExporterFileCreation:
    def test_export_creates_file(self, tmp_path: Path) -> None:
        root = _make_flat_tree()
        dest = tmp_path / "export.csv"

        CsvExporter().export([root], dest)

        assert dest.exists(), "CsvExporter.export() must create the output file"

    def test_export_creates_nonempty_file(self, tmp_path: Path) -> None:
        root = _make_flat_tree()
        dest = tmp_path / "export.csv"

        CsvExporter().export([root], dest)

        assert dest.stat().st_size > 0, "exported CSV must not be empty"

    def test_export_overwrites_existing_file(self, tmp_path: Path) -> None:
        root = _make_flat_tree()
        dest = tmp_path / "export.csv"
        dest.write_text("old content", encoding="utf-8")

        CsvExporter().export([root], dest)

        content = dest.read_text(encoding="utf-8")
        assert "old content" not in content, "export must overwrite existing file"


class TestCsvExporterHeader:
    def test_header_contains_name_column(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))

        assert "Name" in header, f"Expected 'Name' column in header, got: {header}"

    def test_header_contains_path_column(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))

        assert "Path" in header, f"Expected 'Path' column in header, got: {header}"

    def test_header_contains_type_column(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))

        assert "Type" in header, f"Expected 'Type' column in header, got: {header}"

    def test_header_contains_size_column(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))

        assert "Size (bytes)" in header, (
            f"Expected 'Size (bytes)' column in header, got: {header}"
        )

    def test_header_is_first_row(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # First row must be the header — a column name cannot be purely numeric
        assert not rows[0][0].isdigit(), "First row must be the header, not a data row"


class TestCsvExporterRows:
    def test_flat_tree_row_count(self, tmp_path: Path) -> None:
        """root + 2 children = 3 data rows (excluding header)."""
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)

        assert len(rows) == 3, (
            f"Expected 3 data rows (root + 2 children), got {len(rows)}"
        )

    def test_flat_tree_contains_root_name(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            names = [row[0] for row in reader]

        assert "root" in names, "CSV must include root node name"

    def test_flat_tree_contains_child_names(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            names = [row[0] for row in reader]

        assert "file1.txt" in names, "CSV must include file1.txt"
        assert "file2.txt" in names, "CSV must include file2.txt"

    def test_deep_tree_all_nodes_present(self, tmp_path: Path) -> None:
        """3-level tree: root, subdir, leaf.bin — all 3 must appear."""
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_deep_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            names = [row[0] for row in reader]

        assert "root" in names
        assert "subdir" in names
        assert "leaf.bin" in names

    def test_size_column_contains_numeric_value(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            size_idx = header.index("Size (bytes)")
            rows = list(reader)

        size_values = [row[size_idx] for row in rows if len(row) > size_idx]
        assert any(v.isdigit() for v in size_values), (
            "Size (bytes) column must contain numeric values"
        )

    def test_type_column_distinguishes_dir_and_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            type_idx = header.index("Type")
            rows = list(reader)

        type_values = {row[type_idx] for row in rows if len(row) > type_idx}
        assert len(type_values) >= 2, (
            f"Type column must distinguish directories from files, got: {type_values}"
        )

    def test_csv_is_parseable_with_standard_reader(self, tmp_path: Path) -> None:
        """Ensure the file is valid CSV (all rows have consistent column count)."""
        dest = tmp_path / "out.csv"
        CsvExporter().export([_make_flat_tree()], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))

        # Header + 3 data rows
        assert len(rows) >= 4, "CSV must have header + at least 3 data rows"
        col_count = len(rows[0])
        assert all(len(r) == col_count for r in rows), (
            "All CSV rows must have the same number of columns"
        )

    def test_multiple_root_nodes_flattened(self, tmp_path: Path) -> None:
        """Two separate root nodes must appear as separate rows in output."""
        root_a = Node(
            name="dir_a",
            path=Path("/dir_a"),
            is_dir=True,
            size_logical=100,
            size_allocated=4096,
            file_count=0,
            folder_count=0,
            mtime=0.0,
        )
        root_b = Node(
            name="dir_b",
            path=Path("/dir_b"),
            is_dir=True,
            size_logical=200,
            size_allocated=4096,
            file_count=0,
            folder_count=0,
            mtime=0.0,
        )
        dest = tmp_path / "out.csv"
        CsvExporter().export([root_a, root_b], dest)

        with open(dest, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            names = [row[0] for row in reader]

        assert "dir_a" in names, "First root node must appear in CSV"
        assert "dir_b" in names, "Second root node must appear in CSV"
