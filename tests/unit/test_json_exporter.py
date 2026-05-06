"""Unit tests for JsonExporter (exporters/json_exporter.py).

Covers PRD F-8 (JSON export). Tests validate round-trip fidelity through
json.load() — no mocking.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tree_size.core.node import Node
from tree_size.exporters.json_exporter import JsonExporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flat_tree() -> Node:
    """root (dir) with two file children."""
    root = Node(
        name="root",
        path=Path("/root"),
        is_dir=True,
        size_logical=1000,
        size_allocated=4096,
        file_count=2,
        folder_count=0,
        mtime=1_700_000_000.0,
    )
    child1 = Node(
        name="alpha.txt",
        path=Path("/root/alpha.txt"),
        is_dir=False,
        size_logical=400,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=1_700_000_001.0,
        parent=root,
    )
    child2 = Node(
        name="beta.txt",
        path=Path("/root/beta.txt"),
        is_dir=False,
        size_logical=600,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=1_700_000_002.0,
        parent=root,
    )
    root.children = [child1, child2]
    return root


def _make_nested_tree() -> Node:
    """root -> subdir (dir) -> leaf.bin (file): 3-level depth."""
    root = Node(
        name="root",
        path=Path("/root"),
        is_dir=True,
        size_logical=2048,
        size_allocated=8192,
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


def _load(dest: Path) -> Any:
    with open(dest, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJsonExporterFileCreation:
    def test_export_creates_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "export.json"
        JsonExporter().export(_make_flat_tree(), dest)
        assert dest.exists(), "JsonExporter.export() must create the output file"

    def test_export_creates_nonempty_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "export.json"
        JsonExporter().export(_make_flat_tree(), dest)
        assert dest.stat().st_size > 0, "exported JSON must not be empty"

    def test_export_creates_valid_json(self, tmp_path: Path) -> None:
        dest = tmp_path / "export.json"
        JsonExporter().export(_make_flat_tree(), dest)
        # json.load raises on invalid JSON — that is the assertion
        data = _load(dest)
        assert data is not None


class TestJsonExporterRootFields:
    def test_root_name(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert data["name"] == "root", f"root name mismatch: {data.get('name')}"

    def test_root_is_dir_true(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert data["is_dir"] is True, "root is_dir must be true"

    def test_root_size_logical(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert data["size_logical"] == 1000, (
            f"root size_logical must be 1000, got {data.get('size_logical')}"
        )

    def test_root_file_count(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert data["file_count"] == 2, (
            f"root file_count must be 2, got {data.get('file_count')}"
        )

    def test_root_folder_count(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert "folder_count" in data, "root node must include folder_count field"

    def test_root_mtime_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert "mtime" in data, "root node must include mtime field"

    def test_all_required_fields_present(self, tmp_path: Path) -> None:
        required = {"name", "path", "is_dir", "size_logical", "size_allocated",
                    "file_count", "folder_count", "mtime"}
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        missing = required - set(data.keys())
        assert not missing, f"Root node is missing fields: {missing}"


class TestJsonExporterTreeStructure:
    def test_flat_tree_children_count(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        assert len(data["children"]) == 2, (
            f"root must have 2 children, got {len(data.get('children', []))}"
        )

    def test_flat_tree_child_names(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        names = {c["name"] for c in data["children"]}
        assert "alpha.txt" in names
        assert "beta.txt" in names

    def test_flat_tree_children_is_dir_false(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        for child in data["children"]:
            assert child["is_dir"] is False, (
                f"File child '{child['name']}' must have is_dir=false"
            )

    def test_nested_tree_structure_preserved(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_nested_tree(), dest)
        data = _load(dest)

        assert len(data["children"]) == 1
        subdir_data = data["children"][0]
        assert subdir_data["name"] == "subdir"
        assert subdir_data["is_dir"] is True
        assert len(subdir_data["children"]) == 1
        assert subdir_data["children"][0]["name"] == "leaf.bin"

    def test_leaf_node_has_empty_children(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_nested_tree(), dest)
        data = _load(dest)
        leaf = data["children"][0]["children"][0]
        assert leaf["children"] == [], (
            "Leaf file node must have an empty children list"
        )

    def test_child_size_logical_preserved(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        data = _load(dest)
        sizes = {c["name"]: c["size_logical"] for c in data["children"]}
        assert sizes["alpha.txt"] == 400
        assert sizes["beta.txt"] == 600

    def test_no_parent_reference_in_output(self, tmp_path: Path) -> None:
        """Serialized JSON must not contain a 'parent' key (circular reference guard)."""
        dest = tmp_path / "out.json"
        JsonExporter().export(_make_flat_tree(), dest)
        raw = dest.read_text(encoding="utf-8")
        # 'parent' as a JSON key would appear as '"parent":'
        assert '"parent":' not in raw, (
            "JSON output must not serialize the 'parent' back-reference"
        )
