"""Shared utility functions for the PBS Explorer application."""

from __future__ import annotations


def escape_like(value: str) -> str:
    """Escape special SQL LIKE/ILIKE wildcard characters in user input.

    Prevents ``%`` and ``_`` characters from being interpreted as
    wildcards in ``LIKE`` / ``ILIKE`` clauses, while preserving the
    ability to wrap the value with ``%…%`` for substring matching.

    Args:
        value: Raw user-supplied search string.

    Returns:
        The escaped string safe for use inside a ``LIKE`` pattern.
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
