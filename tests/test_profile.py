import pandas as pd
import pytest
from health_signal.profile import ERVISS, FeedRow

_VALID = {
    "location": "Attica", "period": "2025-W01", "survtype": "non-sentinel", "pathogen": "Influenza",
    "age": "total", "indicator": "positivity", "value": "12.3", "unit": "percent",
}


def _violation(**over):
    # Cells are strings, as FileDataSource reads them; a None override drops that column.
    row = {k: v for k, v in {**_VALID, **over}.items() if v is not None}
    found = ERVISS.first_violation(pd.DataFrame([row]))
    return found and found[1]


def _row(**over):
    base = dict(
        location="Attica", period="2025-W01",
        dimensions={"pathogen": "Influenza", "age": "total", "survtype": "non-sentinel"},
        indicator="positivity", value=12.3, unit="percent",
    )
    base.update(over)
    return FeedRow(**base)


def test_erviss_accepts_a_valid_clinical_row():
    assert _violation() is None


def test_erviss_rejects_unknown_indicator():
    assert "indicator" in _violation(indicator="not_an_indicator")


def test_erviss_rejects_unknown_unit():
    assert "unit" in _violation(unit="furlongs")


def test_erviss_rejects_out_of_vocab_dimension_value():
    assert "pathogen" in _violation(pathogen="Measles")


def test_erviss_rejects_non_iso_week_period():
    for bad in ("2025-W5", "2025-01-15"):
        assert "period" in _violation(period=bad)


def test_erviss_rejects_weeks_past_the_iso_year():
    for bad in ("2025-W53", "2025-W00"):
        assert "ISO year" in _violation(period=bad)
    assert _violation(period="2020-W53") is None  # a 53-week year


def test_erviss_rejects_non_finite_or_blank_value():
    for bad in ("nan", "inf", "", "lots"):
        assert "value" in _violation(value=bad)


def test_erviss_rejects_blank_location_and_period():
    assert "location" in _violation(location="")
    assert "period" in _violation(period="")



def test_erviss_pathogen_type_and_subtype_vocab():
    assert "pathogentype" in _violation(pathogentype="Influenza C")
    assert "pathogensubtype" in _violation(pathogensubtype="A(H5)")
    assert _violation(pathogentype="Influenza A", pathogensubtype="A (unknown)") is None
    assert _violation(pathogensubtype="NA") is None  # a real ERVISS value, not a missing cell


def test_erviss_requires_non_nullable_dimensions():
    assert "survtype" in _violation(survtype=None)
    assert "age" in _violation(age="")
    assert _violation(pathogen=None) is None  # pathogen is nullable


def test_first_violation_points_at_the_offending_row():
    df = pd.DataFrame([_VALID, {**_VALID, "unit": "furlongs"}, {**_VALID, "unit": "bogus"}])
    label, message = ERVISS.first_violation(df)
    assert label == 1 and "furlongs" in message


def test_feedrow_requires_numeric_value():
    with pytest.raises(Exception):
        FeedRow(location="A", period="2025-W01", dimensions={}, indicator="deaths", value="lots", unit="count")


def test_feedrow_rejects_nan_and_inf():
    for bad in ("nan", "inf"):
        with pytest.raises(Exception):
            _row(value=bad)


def test_feedrow_rejects_blank_location_and_period():
    with pytest.raises(Exception):
        _row(location="")
    with pytest.raises(Exception):
        _row(period="")

