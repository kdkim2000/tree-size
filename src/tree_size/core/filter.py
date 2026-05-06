"""Filter engine: match nodes by name, extension, size, and modification date."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from tree_size.core.node import Node


@dataclass(slots=True)
class FilterSpec:
    """Immutable (by convention) filter criteria.

    All conditions are ANDed together.  A field at its default value means
    "no constraint" for that dimension.
    """

    name_pattern: str = ""
    """Substring match (case-insensitive) or regex when *use_regex* is True."""

    use_regex: bool = False
    """Treat *name_pattern* as a compiled regular-expression."""

    extensions: list[str] = field(default_factory=list)
    """Allowed extensions including the dot, e.g. ``[".mp4", ".txt"]``.

    Only applied to files; directories are excluded from the result when
    *extensions* is non-empty.
    """

    min_size: int = 0
    """Minimum logical size in bytes (0 = no lower bound)."""

    max_size: int = 0
    """Maximum logical size in bytes (0 = no upper bound)."""

    modified_after: float = 0.0
    """Unix timestamp lower bound (0.0 = no constraint)."""

    modified_before: float = 0.0
    """Unix timestamp upper bound (0.0 = no constraint)."""

    def is_empty(self) -> bool:
        """Return True when every criterion is at its default (no-op filter)."""
        return (
            not self.name_pattern
            and not self.extensions
            and self.min_size == 0
            and self.max_size == 0
            and self.modified_after == 0.0
            and self.modified_before == 0.0
        )


class FilterEngine:
    """Apply a :class:`FilterSpec` against an iterable of :class:`Node` objects.

    Thread-safety note: the internal regex cache is **not** guarded by a lock,
    so each thread that needs filtering should instantiate its own
    ``FilterEngine``.  Construction is cheap — no I/O involved.
    """

    def __init__(self) -> None:
        # Cache compiled patterns to avoid recompilation on repeated calls.
        self._regex_cache: dict[str, re.Pattern[str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply(
        self,
        nodes: Iterable[Node],
        spec: FilterSpec,
    ) -> list[Node]:
        """Return a new list containing only nodes that satisfy *spec*.

        If *spec* :py:meth:`~FilterSpec.is_empty` the original iterable is
        materialised and returned unchanged.
        """
        if spec.is_empty():
            return list(nodes)
        return [n for n in nodes if self.matches(n, spec)]

    def matches(self, node: Node, spec: FilterSpec) -> bool:
        """Return True iff *node* satisfies every criterion in *spec*.

        Criteria are evaluated cheapest-first so that short-circuit evaluation
        avoids unnecessary work.
        """
        # --- name -------------------------------------------------------
        if spec.name_pattern and not self._match_name(
            node.name, spec.name_pattern, spec.use_regex
        ):
            return False

        # --- extension --------------------------------------------------
        # Directories never match an extension filter: they have no meaningful
        # extension and cannot be opened as a specific file type.
        if spec.extensions:
            if node.is_dir:
                return False
            if self._get_extension(node.name) not in spec.extensions:
                return False

        # --- size -------------------------------------------------------
        if spec.min_size > 0 and node.size_logical < spec.min_size:
            return False
        if spec.max_size > 0 and node.size_logical > spec.max_size:
            return False

        # --- modification date ------------------------------------------
        if spec.modified_after > 0.0 and node.mtime < spec.modified_after:
            return False
        return not (spec.modified_before > 0.0 and node.mtime > spec.modified_before)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _match_name(self, name: str, pattern: str, use_regex: bool) -> bool:
        """Return True if *name* matches *pattern*.

        In substring mode (``use_regex=False``) matching is case-insensitive.
        In regex mode an invalid pattern silently returns False so that a
        half-typed expression in the search bar does not raise an exception.
        """
        if use_regex:
            compiled = self._get_compiled_regex(pattern)
            if compiled is None:
                # Invalid pattern — treat as no match rather than crash.
                return False
            return bool(compiled.search(name))
        # Plain substring match — use lower() on both sides (O(n) but simple).
        return pattern.lower() in name.lower()

    def _get_compiled_regex(self, pattern: str) -> re.Pattern[str] | None:
        """Return a cached compiled regex, or None if *pattern* is invalid."""
        if pattern not in self._regex_cache:
            try:
                self._regex_cache[pattern] = re.compile(pattern, re.IGNORECASE)
            except re.error:
                return None
        return self._regex_cache[pattern]

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Return the lowercase extension including the leading dot.

        Returns an empty string for filenames without a dot.
        """
        dot_idx = filename.rfind(".")
        if dot_idx < 0:
            return ""
        return filename[dot_idx:].lower()
