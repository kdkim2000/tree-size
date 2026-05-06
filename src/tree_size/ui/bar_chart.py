"""Bar chart: PyQtGraph-based Top 10 children visualisation for selected node."""
from __future__ import annotations

import logging

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from tree_size.core.formatter import fmt_size
from tree_size.core.node import Node

logger = logging.getLogger(__name__)

# Palette tokens — updated by apply_theme().
_THEME_LIGHT = {
    "background": "#ffffff",
    "bar_brush": "#4a90d9",
    "axis_pen": "#444444",
    "text_color": "#333333",
}
_THEME_DARK = {
    "background": "#2b2b2b",
    "bar_brush": "#3a7abf",
    "axis_pen": "#aaaaaa",
    "text_color": "#cccccc",
}


class BarChartPanel(QWidget):
    """Show the Top 10 children of the selected node, sorted by size."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_node: Node | None = None
        self._palette: dict[str, str] = _THEME_LIGHT
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self._title = QLabel("Select a folder to view", parent=self)
        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # Styling via QSS; no inline setStyleSheet per R-U2.
        self._title.setObjectName("BarChartTitle")
        layout.addWidget(self._title)

        self._plot = pg.PlotWidget(parent=self)
        self._plot.setLabel("left", "Size (GB)")
        self._plot.setLabel("bottom", "Child Item")
        self._plot.hideAxis("bottom")
        self._plot.setMenuEnabled(False)
        # Background is set explicitly so PyQtGraph does not paint its own
        # default grey behind the QWidget-inherited background.
        self._plot.setBackground(None)
        layout.addWidget(self._plot)

        self._apply_palette()

    # ── public API ──────────────────────────────────────────────────────────

    def apply_theme(self, theme: str) -> None:
        """Switch colour palette when the application theme changes."""
        self._palette = _THEME_DARK if theme == "dark" else _THEME_LIGHT
        self._apply_palette()
        # Re-render so bar colours update immediately.
        self.set_node(self._current_node)

    def set_node(self, node: Node | None) -> None:
        """Refresh the chart to display *node*'s top 10 children by size."""
        self._current_node = node

        if node is None:
            self._plot.clear()
            self._title.setText("No selection")
            return

        if not node.children:
            self._plot.clear()
            self._title.setText(f"{node.name} (no children)")
            return

        top10 = sorted(node.children, key=lambda n: n.size_logical, reverse=True)[:10]
        sizes_gb = [n.size_logical / (1024 ** 3) for n in top10]

        self._title.setText(
            f"Top {len(top10)} children of {node.name}"
            f"  (total: {fmt_size(node.size_logical)})"
        )

        self._plot.clear()
        bars = pg.BarGraphItem(
            x=list(range(len(top10))),
            height=sizes_gb,
            width=0.6,
            brush=self._palette["bar_brush"],
        )
        self._plot.addItem(bars)

        # X ticks: short names
        tick_labels = [(i, top10[i].name[:18]) for i in range(len(top10))]
        ax = self._plot.getAxis("bottom")
        ax.setTicks([tick_labels])
        self._plot.showAxis("bottom")

        max_gb = max(sizes_gb) if sizes_gb else 1.0
        self._plot.setXRange(-0.5, len(top10) - 0.5)
        self._plot.setYRange(0, max_gb * 1.15)

        logger.debug("BarChartPanel: rendered %d children for %s", len(top10), node.name)

    # ── private ──────────────────────────────────────────────────────────────

    def _apply_palette(self) -> None:
        """Push axis/label colours into the PyQtGraph plot widget."""
        pen_color = QColor(self._palette["axis_pen"])
        text_color = QColor(self._palette["text_color"])
        for axis_name in ("left", "bottom"):
            axis = self._plot.getAxis(axis_name)
            axis.setPen(pen_color)
            axis.setTextPen(text_color)
