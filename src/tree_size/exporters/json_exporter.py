"""JSON tree-structure export — preserves parent/child hierarchy."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tree_size.core.node import Node

logger = logging.getLogger(__name__)


class JsonExporter:
    """Serialise a Node tree to a JSON file.

    The JSON structure mirrors the Node hierarchy: each object contains a
    ``children`` array so the tree can be reconstructed.
    """

    def export(self, root: Node, dest: Path) -> None:
        """Write *root* and its entire subtree to *dest* as UTF-8 JSON.

        Args:
            root: The top-level node to serialise.
            dest: Output file path.  Created or overwritten.

        Raises:
            OSError: If the file cannot be opened for writing.
        """
        data = self._node_to_dict(root)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info("JSON export completed: %s", dest)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _node_to_dict(self, node: Node) -> dict[str, Any]:
        """Convert *node* to a JSON-serialisable dictionary (recursive)."""
        return {
            "name": node.name,
            "path": str(node.path),
            "is_dir": node.is_dir,
            "size_logical": node.size_logical,
            "size_allocated": node.size_allocated,
            "file_count": node.file_count,
            "folder_count": node.folder_count,
            "mtime": node.mtime,
            "flags": node.flags,
            "children": [self._node_to_dict(child) for child in node.children],
        }
