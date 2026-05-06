"""CSV flat export — one row per node, depth-first order."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from tree_size.core.formatter import fmt_size
from tree_size.core.node import Node

logger = logging.getLogger(__name__)


class CsvExporter:
    """Write a flat CSV table from a Node tree.

    All nodes are serialised in depth-first order; parent-child
    relationship is not expressed in the output (use JsonExporter for
    that).
    """

    _HEADER: tuple[str, ...] = (
        "Name",
        "Path",
        "Type",
        "Size (bytes)",
        "Size (formatted)",
        "Allocated",
        "Files",
        "Folders",
        "Modified",
    )

    def export(self, nodes: list[Node], dest: Path) -> None:
        """Write *nodes* (and all descendants) to *dest* as UTF-8 CSV.

        Args:
            nodes: Root nodes to export.  Their full subtrees are included.
            dest:  Output file path.  Created or overwritten.

        Raises:
            OSError: If the file cannot be opened for writing.
        """
        with open(dest, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(self._HEADER)
            for node in self._iter_depth_first(nodes):
                writer.writerow([
                    node.name,
                    str(node.path),
                    "Folder" if node.is_dir else "File",
                    node.size_logical,
                    fmt_size(node.size_logical),
                    node.size_allocated,
                    node.file_count,
                    node.folder_count,
                    node.mtime,
                ])

        logger.info("CSV export completed: %s (%d root nodes)", dest, len(nodes))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_depth_first(self, roots: list[Node]) -> list[Node]:
        """Return all nodes in depth-first order without recursion."""
        result: list[Node] = []
        stack: list[Node] = list(roots)
        while stack:
            node = stack.pop()
            result.append(node)
            # Push children in reverse so left-to-right DFS order is preserved.
            stack.extend(reversed(node.children))
        return result
