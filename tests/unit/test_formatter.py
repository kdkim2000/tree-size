"""Unit tests for size/count formatting (core/formatter.py)."""
from __future__ import annotations

import pytest

from tree_size.core.formatter import fmt_count, fmt_size, fmt_size_tooltip


class TestFmtSize:
    def test_zero_bytes(self) -> None:
        assert fmt_size(0) == "0 B"

    def test_under_threshold_bytes(self) -> None:
        assert fmt_size(512) == "512 B"

    def test_just_under_one_kb(self) -> None:
        assert fmt_size(1023) == "1023 B"

    def test_exactly_one_kb(self) -> None:
        assert fmt_size(1024) == "1.0 KB"

    def test_one_and_half_kb(self) -> None:
        assert fmt_size(1536) == "1.5 KB"

    def test_exactly_one_mb(self) -> None:
        assert fmt_size(1024 * 1024) == "1.0 MB"

    def test_one_and_half_mb(self) -> None:
        assert fmt_size(int(1.5 * 1024 * 1024)) == "1.5 MB"

    def test_exactly_one_gb(self) -> None:
        assert fmt_size(1024**3) == "1.0 GB"

    def test_exactly_one_tb(self) -> None:
        assert fmt_size(1024**4) == "1.0 TB"

    def test_decimal_places_two(self) -> None:
        assert fmt_size(1536, decimal_places=2) == "1.50 KB"

    def test_decimal_places_zero(self) -> None:
        # 1024 bytes → "1 KB" with 0 decimal places
        result = fmt_size(1024, decimal_places=0)
        assert result == "1 KB"

    def test_large_value_has_gb_unit(self) -> None:
        result = fmt_size(10 * 1024**3)
        assert "GB" in result

    def test_unit_suffix_present(self) -> None:
        for val, expected_unit in [
            (500, "B"),
            (2048, "KB"),
            (2 * 1024 * 1024, "MB"),
            (2 * 1024**3, "GB"),
        ]:
            result = fmt_size(val)
            assert expected_unit in result, f"fmt_size({val}) = {result!r}, expected unit {expected_unit!r}"

    def test_output_is_string(self) -> None:
        assert isinstance(fmt_size(1024), str)


class TestFmtSizeTooltip:
    def test_zero(self) -> None:
        assert fmt_size_tooltip(0) == "0 bytes"

    def test_one_kb(self) -> None:
        assert fmt_size_tooltip(1024) == "1,024 bytes"

    def test_one_million(self) -> None:
        assert fmt_size_tooltip(1_000_000) == "1,000,000 bytes"

    def test_large_value_has_commas(self) -> None:
        result = fmt_size_tooltip(1_234_567_890)
        assert "," in result
        assert result.endswith(" bytes")

    def test_output_is_string(self) -> None:
        assert isinstance(fmt_size_tooltip(42), str)


class TestFmtCount:
    def test_zero(self) -> None:
        assert fmt_count(0) == "0"

    def test_one(self) -> None:
        assert fmt_count(1) == "1"

    def test_hundreds(self) -> None:
        assert fmt_count(999) == "999"

    def test_thousands_separator(self) -> None:
        assert fmt_count(1234) == "1,234"

    def test_one_million(self) -> None:
        assert fmt_count(1_000_000) == "1,000,000"

    def test_large_value_has_commas(self) -> None:
        result = fmt_count(1_234_567)
        assert "," in result

    def test_output_is_string(self) -> None:
        assert isinstance(fmt_count(100), str)
