"""Tests for the InteractionMode and PlacementMode enums."""

import pytest

from graphulator.para_core.interaction_state import InteractionMode, PlacementMode


class TestInteractionMode:
    """Tests for InteractionMode enum."""

    def test_values_exist(self):
        """All expected interaction modes are defined."""
        assert InteractionMode.NORMAL is not None
        assert InteractionMode.BASIS_ORDERING is not None
        assert InteractionMode.KRON_REDUCTION is not None
        assert InteractionMode.SCATTERING is not None

    def test_modes_are_distinct(self):
        """Each mode has a unique value."""
        modes = list(InteractionMode)
        assert len(modes) == len(set(m.value for m in modes))


class TestPlacementMode:
    """Tests for PlacementMode enum."""

    def test_values_exist(self):
        """All expected placement modes are defined."""
        assert PlacementMode.NONE is not None
        assert PlacementMode.SINGLE is not None
        assert PlacementMode.CONTINUOUS is not None
        assert PlacementMode.EDGE is not None

    def test_from_string_none(self):
        """from_string(None) returns NONE."""
        assert PlacementMode.from_string(None) == PlacementMode.NONE

    def test_from_string_valid(self):
        """from_string works for valid strings."""
        assert PlacementMode.from_string('single') == PlacementMode.SINGLE
        assert PlacementMode.from_string('continuous') == PlacementMode.CONTINUOUS
        assert PlacementMode.from_string('edge') == PlacementMode.EDGE
        assert PlacementMode.from_string('conjugation') == PlacementMode.CONJUGATION

    def test_from_string_unknown(self):
        """from_string returns NONE for unknown strings."""
        assert PlacementMode.from_string('unknown') == PlacementMode.NONE

    def test_to_string_none(self):
        """NONE.to_string() returns None."""
        assert PlacementMode.NONE.to_string() is None

    def test_to_string_roundtrip(self):
        """to_string/from_string roundtrip works."""
        for mode in PlacementMode:
            if mode != PlacementMode.NONE:
                s = mode.to_string()
                assert PlacementMode.from_string(s) == mode
