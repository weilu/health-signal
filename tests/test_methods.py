import pytest
from pydantic import ValidationError
from health_signal.methods import Method


def test_a_method_cannot_repeat_a_level():
    with pytest.raises(ValidationError):
        Method(name="x", levels=["low", "low"], phases=[], trend=False)


def test_aedseo_declares_its_stream_roles_and_active_phases():
    m = METHODS["aedseo"]
    assert (m.stream_roles, m.active_phases) == (["cases", "admissions"], ["in_season", "in_wave"])


def test_active_phases_must_be_phases():
    with pytest.raises(ValidationError):
        Method(name="x", levels=["a"], phases=["on"], active_phases=["off"], trend=False)
