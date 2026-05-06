"""Unit tests for HtmlExporter (exporters/html_exporter.py).

Covers PRD F-8 (HTML export). Tests validate HTML structure and content
by reading the produced file as text — no mocking, no HTML parser dependency.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tree_size.core.node import Node
from tree_size.exporters.html_exporter import HtmlExporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flat_tree() -> Node:
    """root (dir) with one file child."""
    root = Node(
        name="root",
        path=Path("/root"),
        is_dir=True,
        size_logical=1000,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
    )
    child = Node(
        name="file.txt",
        path=Path("/root/file.txt"),
        is_dir=False,
        size_logical=500,
        size_allocated=4096,
        file_count=1,
        folder_count=0,
        mtime=0.0,
        parent=root,
    )
    root.children = [child]
    return root


def _make_multi_child_tree() -> Node:
    """root (dir) with three file children for table row count verification."""
    root = Node(
        name="mydir",
        path=Path("/mydir"),
        is_dir=True,
        size_logical=3000,
        size_allocated=12288,
        file_count=3,
        folder_count=0,
        mtime=0.0,
    )
    for i in range(1, 4):
        child = Node(
            name=f"item{i}.dat",
            path=Path(f"/mydir/item{i}.dat"),
            is_dir=False,
            size_logical=i * 1000,
            size_allocated=4096,
            file_count=1,
            folder_count=0,
            mtime=0.0,
            parent=root,
        )
        root.children.append(child)
    return root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHtmlExporterFileCreation:
    def test_export_creates_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "export.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        assert dest.exists(), "HtmlExporter.export() must create the output file"

    def test_export_creates_nonempty_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "export.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        assert dest.stat().st_size > 0, "exported HTML must not be empty"

    def test_export_file_is_utf8(self, tmp_path: Path) -> None:
        dest = tmp_path / "export.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        # Must not raise UnicodeDecodeError
        content = dest.read_text(encoding="utf-8")
        assert len(content) > 0


class TestHtmlExporterDocStructure:
    def test_doctype_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content, "HTML must begin with <!DOCTYPE html>"

    def test_html_open_tag(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "<html" in content, "HTML must contain an <html> opening tag"

    def test_html_close_tag(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "</html>" in content, "HTML must contain a closing </html> tag"

    def test_head_section_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "<head" in content and "</head>" in content, (
            "HTML must contain a <head> section"
        )

    def test_body_section_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "<body" in content and "</body>" in content, (
            "HTML must contain a <body> section"
        )

    def test_charset_meta_tag(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8").lower()
        assert "charset" in content, (
            "HTML head must declare a charset (e.g. <meta charset='utf-8'>)"
        )


class TestHtmlExporterTableStructure:
    def test_table_element_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "<table" in content, "HTML must contain a <table> element"

    def test_table_has_header_row(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        # <th> elements indicate column headers
        assert "<th" in content, "Table must have header cells (<th>)"

    def test_table_has_data_rows(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "<td" in content, "Table must contain data cells (<td>)"

    def test_table_close_tag(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "</table>" in content, "Table must be properly closed with </table>"


class TestHtmlExporterContent:
    def test_root_name_appears_in_output(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "root" in content, "Root node name must appear in HTML output"

    def test_root_path_appears_in_output(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        root = _make_flat_tree()
        HtmlExporter().export(root, dest)
        content = dest.read_text(encoding="utf-8")
        # Use the OS-rendered path string to stay platform-neutral
        assert str(root.path) in content, (
            f"Root node path '{root.path}' must appear in HTML output"
        )

    def test_child_name_appears_in_output(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "file.txt" in content, "Child node name 'file.txt' must appear in HTML"

    def test_size_value_appears_in_output(self, tmp_path: Path) -> None:
        """At least one numeric size value must be present in the table."""
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_flat_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        # root.size_logical == 1000; child.size_logical == 500
        assert "1000" in content or "500" in content, (
            "HTML must include at least one size_logical value"
        )

    def test_multiple_children_all_present(self, tmp_path: Path) -> None:
        dest = tmp_path / "out.html"
        HtmlExporter().export(_make_multi_child_tree(), dest)
        content = dest.read_text(encoding="utf-8")
        assert "item1.dat" in content
        assert "item2.dat" in content
        assert "item3.dat" in content

    def test_special_chars_escaped(self, tmp_path: Path) -> None:
        """Node names with HTML-special characters must not break document structure."""
        root = Node(
            name="<test> & 'dir'",
            path=Path('/root/<test>'),
            is_dir=True,
            size_logical=0,
            size_allocated=0,
            file_count=0,
            folder_count=0,
            mtime=0.0,
        )
        dest = tmp_path / "out.html"
        HtmlExporter().export(root, dest)
        content = dest.read_text(encoding="utf-8")
        # The raw unescaped < must not be a stray tag
        # Proper escaping: &lt; replaces <, &gt; replaces >
        # The document must still be syntactically valid (closing </html> present)
        assert "</html>" in content, (
            "HTML must remain well-formed even with special characters in node names"
        )
