import pytest
from pydantic import ValidationError
from health_signal.analytics.aedseo_r import burden_args, onset_args
from health_signal.methods import AEDSEO, Method


def test_a_method_cannot_repeat_a_level():
    with pytest.raises(ValidationError):
        Method(name="x", levels=["low", "low"], phases=[], trend=False)


def test_active_phases_must_be_phases():
    with pytest.raises(ValidationError):
        Method(name="x", levels=["a"], phases=["on"], active_phases=["off"], trend=False)


def test_aedseo_fits_with_its_methods_parameters():
    # One source for the settings: the methodology page shows them, so the fit must read the same ones.
    m = AEDSEO.model_copy(update={"parameters": {**AEDSEO.parameters, "window_weeks": 6, "n_peak": 4}})
    assert onset_args(m)["k"] == 6 and burden_args(m)["n_peak"] == 4
    assert onset_args(AEDSEO) == {"family": "quasipoisson", "k": 5, "level": 0.95}
