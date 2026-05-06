"""Unit tests for core.filter — FilterSpec and FilterEngine."""
from __future__ import annotations

from pathlib import Path

import pytest

from tree_size.core.filter import FilterEngine, FilterSpec
from tree_size.core.node import Node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(
    name: str,
    *,
    is_dir: bool = False,
    size: int = 0,
    mtime: float = 0.0,
) -> Node:
    return Node(
        name=name,
        path=Path("C:/fake") / name,
        is_dir=is_dir,
        size_logical=size,
        size_allocated=size,
        file_count=0 if is_dir else 1,
        folder_count=0,
        mtime=mtime,
    )


# ---------------------------------------------------------------------------
# FilterSpec.is_empty
# ---------------------------------------------------------------------------

class TestFilterSpecIsEmpty:
    def test_default_is_empty(self) -> None:
        assert FilterSpec().is_empty()

    def test_name_pattern_not_empty(self) -> None:
        assert not FilterSpec(name_pattern="foo").is_empty()

    def test_extensions_not_empty(self) -> None:
        assert not FilterSpec(extensions=[".mp4"]).is_empty()

    def test_min_size_not_empty(self) -> None:
        assert not FilterSpec(min_size=1).is_empty()

    def test_max_size_not_empty(self) -> None:
        assert not FilterSpec(max_size=1).is_empty()

    def test_modified_after_not_empty(self) -> None:
        assert not FilterSpec(modified_after=1.0).is_empty()

    def test_modified_before_not_empty(self) -> None:
        assert not FilterSpec(modified_before=1.0).is_empty()

    def test_use_regex_alone_is_empty(self) -> None:
        # use_regex without a pattern is still a no-op filter.
        assert FilterSpec(use_regex=True).is_empty()


# ---------------------------------------------------------------------------
# FilterEngine.apply — empty spec
# ---------------------------------------------------------------------------

class TestApplyEmptySpec:
    def test_empty_spec_returns_all(self) -> None:
        nodes = [_node("a.txt"), _node("b.mp4"), _node("dir", is_dir=True)]
        engine = FilterEngine()
        result = engine.apply(nodes, FilterSpec())
        assert result == nodes

    def test_empty_input_returns_empty(self) -> None:
        assert FilterEngine().apply([], FilterSpec(name_pattern="x")) == []


# ---------------------------------------------------------------------------
# Name pattern — substring
# ---------------------------------------------------------------------------

class TestNamePatternSubstring:
    def test_substring_match(self) -> None:
        nodes = [_node("report_2024.csv"), _node("summary.txt"), _node("report_q1.xlsx")]
        result = FilterEngine().apply(nodes, FilterSpec(name_pattern="report"))
        assert [n.name for n in result] == ["report_2024.csv", "report_q1.xlsx"]

    def test_substring_case_insensitive(self) -> None:
        nodes = [_node("README.md"), _node("notes.txt")]
        result = FilterEngine().apply(nodes, FilterSpec(name_pattern="readme"))
        assert len(result) == 1
        assert result[0].name == "README.md"

    def test_no_match_returns_empty(self) -> None:
        nodes = [_node("alpha.py"), _node("beta.py")]
        result = FilterEngine().apply(nodes, FilterSpec(name_pattern="gamma"))
        assert result == []

    def test_empty_pattern_matches_all(self) -> None:
        nodes = [_node("a"), _node("b")]
        result = FilterEngine().apply(nodes, FilterSpec(name_pattern=""))
        assert result == nodes


# ---------------------------------------------------------------------------
# Name pattern — regex
# ---------------------------------------------------------------------------

class TestNamePatternRegex:
    def test_regex_match(self) -> None:
        nodes = [_node("file001.log"), _node("file002.log"), _node("other.txt")]
        result = FilterEngine().apply(nodes, FilterSpec(name_pattern=r"file\d+", use_regex=True))
        assert [n.name for n in result] == ["file001.log", "file002.log"]

    def test_regex_case_insensitive(self) -> None:
        nodes = [_node("Report.CSV"), _node("data.csv")]
        result = FilterEngine().apply(
            nodes, FilterSpec(name_pattern=r"\.csv$", use_regex=True)
        )
        assert len(result) == 2

    def test_invalid_regex_matches_nothing(self) -> None:
        nodes = [_node("anything.txt")]
        # "[unclosed bracket" is an invalid regex — should silently return no match.
        result = FilterEngine().apply(
            nodes, FilterSpec(name_pattern="[unclosed", use_regex=True)
        )
        assert result == []

    def test_regex_cache_reused(self) -> None:
        engine = FilterEngine()
        spec = FilterSpec(name_pattern=r"\d+", use_regex=True)
        nodes = [_node("123.bin"), _node("abc.bin")]
        engine.apply(nodes, spec)
        # Second call should hit the cache (no exception means it worked).
        engine.apply(nodes, spec)
        assert r"\d+" in engine._regex_cache  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Extension filter
# ---------------------------------------------------------------------------

class TestExtensionFilter:
    def test_single_extension(self) -> None:
        nodes = [_node("video.mp4"), _node("doc.txt"), _node("clip.mp4")]
        result = FilterEngine().apply(nodes, FilterSpec(extensions=[".mp4"]))
        assert [n.name for n in result] == ["video.mp4", "clip.mp4"]

    def test_multiple_extensions(self) -> None:
        nodes = [_node("a.jpg"), _node("b.png"), _node("c.txt")]
        result = FilterEngine().apply(nodes, FilterSpec(extensions=[".jpg", ".png"]))
        assert [n.name for n in result] == ["a.jpg", "b.png"]

    def test_extension_case_insensitive(self) -> None:
        nodes = [_node("IMAGE.JPG"), _node("photo.jpg")]
        result = FilterEngine().apply(nodes, FilterSpec(extensions=[".jpg"]))
        assert len(result) == 2

    def test_directory_excluded_when_extension_filter_set(self) -> None:
        nodes = [_node("folder.mp4", is_dir=True), _node("video.mp4")]
        result = FilterEngine().apply(nodes, FilterSpec(extensions=[".mp4"]))
        # The directory must be excluded regardless of its name.
        assert [n.name for n in result] == ["video.mp4"]

    def test_no_extension_file_excluded(self) -> None:
        nodes = [_node("Makefile"), _node("script.sh")]
        result = FilterEngine().apply(nodes, FilterSpec(extensions=[".sh"]))
        assert [n.name for n in result] == ["script.sh"]

    def test_dotfile_has_no_extension(self) -> None:
        # ".gitignore" — rfind('.') returns 0 → extension would be ".gitignore"
        node = _node(".gitignore")
        engine = FilterEngine()
        # Should NOT match ".txt"
        assert not engine.matches(node, FilterSpec(extensions=[".txt"]))
        # Should match its own "extension" token
        assert engine.matches(node, FilterSpec(extensions=[".gitignore"]))


# ---------------------------------------------------------------------------
# Size filter
# ---------------------------------------------------------------------------

class TestSizeFilter:
    def test_min_size(self) -> None:
        nodes = [_node("small.bin", size=100), _node("large.bin", size=1000)]
        result = FilterEngine().apply(nodes, FilterSpec(min_size=500))
        assert [n.name for n in result] == ["large.bin"]

    def test_max_size(self) -> None:
        nodes = [_node("small.bin", size=100), _node("large.bin", size=1000)]
        result = FilterEngine().apply(nodes, FilterSpec(max_size=500))
        assert [n.name for n in result] == ["small.bin"]

    def test_min_and_max_size(self) -> None:
        nodes = [
            _node("tiny.bin", size=10),
            _node("mid.bin", size=500),
            _node("huge.bin", size=2000),
        ]
        result = FilterEngine().apply(nodes, FilterSpec(min_size=100, max_size=1000))
        assert [n.name for n in result] == ["mid.bin"]

    def test_exact_boundary_inclusive(self) -> None:
        node = _node("exact.bin", size=512)
        engine = FilterEngine()
        assert engine.matches(node, FilterSpec(min_size=512, max_size=512))

    def test_zero_min_size_is_no_constraint(self) -> None:
        node = _node("zero.bin", size=0)
        assert FilterEngine().matches(node, FilterSpec(min_size=0))

    def test_zero_max_size_is_no_constraint(self) -> None:
        node = _node("huge.bin", size=10**12)
        assert FilterEngine().matches(node, FilterSpec(max_size=0))


# ---------------------------------------------------------------------------
# Modification date filter
# ---------------------------------------------------------------------------

class TestModifiedDateFilter:
    def test_modified_after(self) -> None:
        nodes = [
            _node("old.txt", mtime=1_000_000.0),
            _node("new.txt", mtime=2_000_000.0),
        ]
        result = FilterEngine().apply(nodes, FilterSpec(modified_after=1_500_000.0))
        assert [n.name for n in result] == ["new.txt"]

    def test_modified_before(self) -> None:
        nodes = [
            _node("old.txt", mtime=1_000_000.0),
            _node("new.txt", mtime=2_000_000.0),
        ]
        result = FilterEngine().apply(nodes, FilterSpec(modified_before=1_500_000.0))
        assert [n.name for n in result] == ["old.txt"]

    def test_modified_after_and_before(self) -> None:
        nodes = [
            _node("a.txt", mtime=1_000_000.0),
            _node("b.txt", mtime=1_500_000.0),
            _node("c.txt", mtime=2_000_000.0),
        ]
        result = FilterEngine().apply(
            nodes,
            FilterSpec(modified_after=1_200_000.0, modified_before=1_800_000.0),
        )
        assert [n.name for n in result] == ["b.txt"]

    def test_boundary_inclusive(self) -> None:
        ts = 1_234_567.0
        node = _node("exact.txt", mtime=ts)
        engine = FilterEngine()
        # Exactly at the boundary must still match.
        assert engine.matches(node, FilterSpec(modified_after=ts, modified_before=ts))

    def test_zero_timestamps_are_no_constraint(self) -> None:
        node = _node("any.txt", mtime=0.0)
        assert FilterEngine().matches(
            node, FilterSpec(modified_after=0.0, modified_before=0.0)
        )


# ---------------------------------------------------------------------------
# Combined (AND) conditions
# ---------------------------------------------------------------------------

class TestCombinedConditions:
    def test_name_and_extension(self) -> None:
        nodes = [
            _node("report.csv"),
            _node("report.txt"),
            _node("data.csv"),
        ]
        result = FilterEngine().apply(
            nodes, FilterSpec(name_pattern="report", extensions=[".csv"])
        )
        assert [n.name for n in result] == ["report.csv"]

    def test_all_conditions_must_pass(self) -> None:
        node = _node("big_report.csv", size=5000, mtime=1_500_000.0)
        engine = FilterEngine()
        spec = FilterSpec(
            name_pattern="report",
            extensions=[".csv"],
            min_size=1000,
            max_size=10000,
            modified_after=1_000_000.0,
            modified_before=2_000_000.0,
        )
        assert engine.matches(node, spec)

    def test_one_failing_condition_rejects_node(self) -> None:
        node = _node("report.csv", size=5000, mtime=1_500_000.0)
        engine = FilterEngine()
        # max_size fails
        spec = FilterSpec(
            name_pattern="report",
            extensions=[".csv"],
            min_size=1000,
            max_size=100,  # too small — should reject
        )
        assert not engine.matches(node, spec)


# ---------------------------------------------------------------------------
# _get_extension static method
# ---------------------------------------------------------------------------

class TestGetExtension:
    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("file.txt", ".txt"),
            ("archive.tar.gz", ".gz"),
            ("UPPERCASE.MP4", ".mp4"),
            ("noextension", ""),
            (".hidden", ".hidden"),
            ("trailing.", "."),
        ],
    )
    def test_extension_extraction(self, filename: str, expected: str) -> None:
        assert FilterEngine._get_extension(filename) == expected  # type: ignore[attr-defined]
