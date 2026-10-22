import pytest
from pydantic import ValidationError
from health_signal.methods import METHODS, Method


def test_aedseo_grades_five_ordered_levels():
    assert METHODS["aedseo"].levels == ["very_low", "low", "medium", "high", "very_high"]


def test_a_method_cannot_repeat_a_level():
    with pytest.raises(ValidationError):
        Method(name="x", levels=["low", "low"], phases=[], trend=False)
