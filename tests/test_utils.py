"""Tests for utils module."""
from __future__ import annotations

from utils import escape_like


def test_escape_like_plain():
    assert escape_like("hello") == "hello"


def test_escape_like_percent():
    assert escape_like("50%") == r"50\%"


def test_escape_like_underscore():
    assert escape_like("a_b") == r"a\_b"


def test_escape_like_backslash():
    assert escape_like(r"a\b") == r"a\\b"


def test_escape_like_combined():
    assert escape_like(r"50%_\x") == r"50\%\_\\x"


def test_escape_like_empty():
    assert escape_like("") == ""
