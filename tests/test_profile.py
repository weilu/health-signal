import pytest
from health_signal.profile import ERVISS, FeedRow, Profile


def _row(**over):
    base = dict(
        location="Attica", period="2025-W01",
        dimensions={"pathogen": "Influenza", "age": "total", "survtype": "non-sentinel"},
        indicator="positivity", value=12.3, unit="percent",
    )
    base.update(over)
    return FeedRow(**base)


def test_erviss_accepts_a_valid_clinical_row():
    ERVISS.validate_row(_row())  # no raise


def test_erviss_rejects_unknown_indicator():
    with pytest.raises(ValueError, match="indicator"):
        ERVISS.validate_row(_row(indicator="not_an_indicator"))


def test_erviss_rejects_unknown_unit():
    with pytest.raises(ValueError, match="unit"):
        ERVISS.validate_row(_row(unit="furlongs"))


def test_erviss_rejects_out_of_vocab_dimension_value():
    with pytest.raises(ValueError, match="pathogen"):
        ERVISS.validate_row(_row(dimensions={"pathogen": "Measles", "age": "total"}))


def test_erviss_ingests_status_level_but_not_categorical_trend():
    assert "status_level" in ERVISS.indicators
    assert "trend" not in ERVISS.indicators  # categorical derived rows deferred to 4c


def test_status_level_must_be_a_level_0_to_4():
    for bad in (7, -1, 2.5):
        with pytest.raises(ValueError, match="status_level"):
            ERVISS.validate_row(_row(indicator="status_level", value=bad, unit="level"))
    ERVISS.validate_row(_row(indicator="status_level", value=3, unit="level"))


def test_erviss_requires_non_nullable_dimensions():
    with pytest.raises(ValueError, match="survtype"):
        ERVISS.validate_row(_row(dimensions={"pathogen": "Influenza", "age": "total"}))
    with pytest.raises(ValueError, match="age"):
        ERVISS.validate_row(_row(dimensions={"survtype": "non-sentinel"}))
    ERVISS.validate_row(_row(dimensions={"survtype": "non-sentinel", "age": "total"}))  # pathogen is nullable


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


def test_erviss_rejects_non_iso_week_period():
    for bad in ("2025-W5", "2025-01-15"):
        with pytest.raises(ValueError, match="period"):
            ERVISS.validate_row(_row(period=bad))


def test_profile_does_not_shadow_pydantic_validate():
    assert "validate" not in Profile.__dict__
