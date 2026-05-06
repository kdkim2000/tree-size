"""SearchBar UI widget tests — covers F-30, F-31, F-32."""
from __future__ import annotations

import pytest
from pytestqt.qtbot import QtBot

from tree_size.core.filter import FilterSpec
from tree_size.ui.search_bar import SearchBar


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def search_bar(qtbot: QtBot) -> SearchBar:
    bar = SearchBar()
    qtbot.addWidget(bar)
    return bar


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestSearchBarInitialState:
    def test_initial_spec_is_empty(self, search_bar: SearchBar) -> None:
        spec = search_bar.filter_spec
        assert spec.is_empty(), "Fresh SearchBar must produce an empty FilterSpec"

    def test_initial_name_input_is_blank(self, search_bar: SearchBar) -> None:
        assert search_bar._name_input.text() == ""  # type: ignore[attr-defined]

    def test_initial_regex_unchecked(self, search_bar: SearchBar) -> None:
        assert not search_bar._regex_check.isChecked()  # type: ignore[attr-defined]

    def test_initial_ext_combo_index_is_all(self, search_bar: SearchBar) -> None:
        assert search_bar._ext_combo.currentIndex() == 0  # type: ignore[attr-defined]

    def test_initial_min_size_is_zero(self, search_bar: SearchBar) -> None:
        assert search_bar._min_size.value() == 0  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# filterChanged signal
# ---------------------------------------------------------------------------

class TestFilterChangedSignal:
    def test_name_input_emits_filter_changed(
        self, search_bar: SearchBar, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(search_bar.filterChanged, timeout=2000):
            search_bar._name_input.setText("test")  # type: ignore[attr-defined]

    def test_regex_check_emits_filter_changed(
        self, search_bar: SearchBar, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(search_bar.filterChanged, timeout=2000):
            search_bar._regex_check.setChecked(True)  # type: ignore[attr-defined]

    def test_ext_combo_change_emits_filter_changed(
        self, search_bar: SearchBar, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(search_bar.filterChanged, timeout=2000):
            search_bar._ext_combo.setCurrentIndex(1)  # type: ignore[attr-defined]

    def test_min_size_change_emits_filter_changed(
        self, search_bar: SearchBar, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(search_bar.filterChanged, timeout=2000):
            search_bar._min_size.setValue(5)  # type: ignore[attr-defined]

    def test_signal_carries_filter_spec(
        self, search_bar: SearchBar, qtbot: QtBot
    ) -> None:
        received: list[object] = []
        search_bar.filterChanged.connect(received.append)
        search_bar._name_input.setText("hello")  # type: ignore[attr-defined]
        assert len(received) == 1
        assert isinstance(received[0], FilterSpec), (
            f"filterChanged must emit FilterSpec, got {type(received[0])}"
        )


# ---------------------------------------------------------------------------
# filter_spec property
# ---------------------------------------------------------------------------

class TestFilterSpecProperty:
    def test_name_pattern_reflected_in_spec(self, search_bar: SearchBar) -> None:
        search_bar._name_input.setText("report")  # type: ignore[attr-defined]
        assert search_bar.filter_spec.name_pattern == "report"

    def test_use_regex_reflected_in_spec(self, search_bar: SearchBar) -> None:
        search_bar._regex_check.setChecked(True)  # type: ignore[attr-defined]
        assert search_bar.filter_spec.use_regex

    def test_use_regex_false_by_default(self, search_bar: SearchBar) -> None:
        assert not search_bar.filter_spec.use_regex

    def test_min_size_one_mb_in_bytes(self, search_bar: SearchBar) -> None:
        search_bar._min_size.setValue(1)  # type: ignore[attr-defined]
        spec = search_bar.filter_spec
        assert spec.min_size == 1024 * 1024, (
            f"1 MB spinner value should map to {1024 * 1024} bytes, got {spec.min_size}"
        )

    def test_min_size_ten_mb_in_bytes(self, search_bar: SearchBar) -> None:
        search_bar._min_size.setValue(10)  # type: ignore[attr-defined]
        spec = search_bar.filter_spec
        assert spec.min_size == 10 * 1024 * 1024

    def test_ext_all_gives_empty_extensions(self, search_bar: SearchBar) -> None:
        search_bar._ext_combo.setCurrentIndex(0)  # type: ignore[attr-defined]
        assert search_bar.filter_spec.extensions == []

    def test_ext_images_gives_image_extensions(self, search_bar: SearchBar) -> None:
        search_bar._ext_combo.setCurrentIndex(1)  # type: ignore[attr-defined]
        exts = search_bar.filter_spec.extensions
        assert ".jpg" in exts, "Images preset must include .jpg"
        assert ".png" in exts, "Images preset must include .png"

    def test_ext_videos_gives_video_extensions(self, search_bar: SearchBar) -> None:
        search_bar._ext_combo.setCurrentIndex(2)  # type: ignore[attr-defined]
        exts = search_bar.filter_spec.extensions
        assert ".mp4" in exts, "Videos preset must include .mp4"
        assert ".mkv" in exts, "Videos preset must include .mkv"

    def test_ext_archives_gives_archive_extensions(self, search_bar: SearchBar) -> None:
        search_bar._ext_combo.setCurrentIndex(3)  # type: ignore[attr-defined]
        exts = search_bar.filter_spec.extensions
        assert ".zip" in exts, "Archives preset must include .zip"
        assert ".7z" in exts, "Archives preset must include .7z"

    def test_non_empty_spec_after_name_input(self, search_bar: SearchBar) -> None:
        search_bar._name_input.setText("anything")  # type: ignore[attr-defined]
        assert not search_bar.filter_spec.is_empty()

    def test_non_empty_spec_after_ext_selection(self, search_bar: SearchBar) -> None:
        search_bar._ext_combo.setCurrentIndex(1)  # type: ignore[attr-defined]
        assert not search_bar.filter_spec.is_empty()


# ---------------------------------------------------------------------------
# set_focus_on_name_input
# ---------------------------------------------------------------------------

class TestSetFocusOnNameInput:
    def test_set_focus_focuses_name_input(self, search_bar: SearchBar, qtbot: QtBot) -> None:
        # Show the widget so focus can be applied
        search_bar.show()
        qtbot.waitExposed(search_bar)
        search_bar.set_focus_on_name_input()
        assert search_bar._name_input.hasFocus(), (  # type: ignore[attr-defined]
            "set_focus_on_name_input() must focus the name QLineEdit"
        )

    def test_set_focus_selects_all_text(self, search_bar: SearchBar, qtbot: QtBot) -> None:
        search_bar._name_input.setText("existing text")  # type: ignore[attr-defined]
        search_bar.show()
        qtbot.waitExposed(search_bar)
        search_bar.set_focus_on_name_input()
        selected = search_bar._name_input.selectedText()  # type: ignore[attr-defined]
        assert selected == "existing text", (
            "set_focus_on_name_input() must select all text in the name field"
        )


# ---------------------------------------------------------------------------
# Combo-box preset count
# ---------------------------------------------------------------------------

class TestExtComboItems:
    def test_combo_has_four_items(self, search_bar: SearchBar) -> None:
        count = search_bar._ext_combo.count()  # type: ignore[attr-defined]
        assert count == 4, f"Extension combo must have 4 presets (All + 3 types), got {count}"

    def test_first_item_is_all(self, search_bar: SearchBar) -> None:
        text = search_bar._ext_combo.itemText(0)  # type: ignore[attr-defined]
        assert "All" in text, f"Index 0 must be 'All', got {text!r}"
