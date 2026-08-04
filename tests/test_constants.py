"""Constant integrity tests."""

from waypoint.constants import EXIT_ERROR, EXIT_OK, EXIT_USAGE, TEMP_SLOT
from waypoint.resolver import RESERVED


def test_temp_slot_not_reserved():
    """TEMP_SLOT must not be a reserved keyword (parser would eat it)."""
    assert TEMP_SLOT not in RESERVED


def test_exit_codes_are_distinct():
    assert len({EXIT_OK, EXIT_ERROR, EXIT_USAGE}) == 3


def test_exit_codes_are_ints():
    assert isinstance(EXIT_OK, int)
    assert isinstance(EXIT_ERROR, int)
    assert isinstance(EXIT_USAGE, int)
