"""Bottom-up size aggregation helpers."""
from __future__ import annotations

from tree_size.core.node import Node


def aggregate(root: Node) -> None:
    """Recompute size/count for all ancestor nodes bottom-up (post-order DFS).

    This is idempotent — safe to call multiple times.
    """
    _aggregate_recursive(root)


def _aggregate_recursive(node: Node) -> None:
    if not node.is_dir:
        return

    node.size_logical = 0
    node.size_allocated = 0
    node.file_count = 0
    node.folder_count = 0

    for child in node.children:
        _aggregate_recursive(child)
        node.size_logical += child.size_logical
        node.size_allocated += child.size_allocated
        node.file_count += child.file_count
        node.folder_count += child.folder_count + (1 if child.is_dir else 0)
