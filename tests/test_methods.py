import pytest
from pydantic import ValidationError
from health_signal.methods import Method


def test_a_method_cannot_repeat_a_level():
    with pytest.raises(ValidationError):
        Method(name="x", levels=["low", "low"], phases=[], trend=False)
