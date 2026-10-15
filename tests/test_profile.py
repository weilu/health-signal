import pandas as pd
import pytest
from health_signal.profile import ERVISS, FeedRow, Profile

# One row as FileDataSource hands it to the profile: every profile column, cells as text.
_VALID = {
    "survtype": "non-sentinel", "countryname": "Greece", "region": "", "yearweek": "2025-W01",
    "pathogen": "Influenza", "pathogentype": "Influenza A", "pathogensubtype": "A(H3)",
    "indicator": "positivity", "age": "total", "value": "12.3", "datasource": "",
}


def _violation(**over):
    found = ERVISS.first_violation(pd.DataFrame([{**_VALID, **over}]))
    return found and found[1]


def test_erviss_accepts_a_valid_row():
    assert _violation() is None


def test_erviss_rejects_unknown_indicator():
    assert "indicator" in _violation(indicator="not_an_indicator")


def test_erviss_rejects_out_of_vocab_values():
    assert "pathogen" in _violation(pathogen="Measles")
    assert "pathogentype" in _violation(pathogentype="Influenza C")
    assert "pathogensubtype" in _violation(pathogensubtype="A(H5)")


def test_erviss_accepts_literal_na_subtype():
    assert _violation(pathogensubtype="NA") is None  # a real ERVISS value, not a missing cell


def test_erviss_rejects_non_iso_yearweek():
    for bad in ("2025-W5", "2025-01-15"):
        assert "yearweek" in _violation(yearweek=bad)


def test_erviss_rejects_non_finite_or_blank_value():
    for bad in ("nan", "inf", "", "lots"):
        assert "value" in _violation(value=bad)


def test_erviss_requires_non_blank_required_columns():
    for col in ("survtype", "countryname", "yearweek", "age"):
        assert f"{col} is empty" in _violation(**{col: ""})


def test_erviss_optional_columns_may_be_blank():
    assert _violation(pathogen="", pathogentype="", pathogensubtype="", region="") is None


def test_status_assessments_are_not_erviss_indicators():
    # Status/Trend are a separate assessment contract (spec §6.3), not rows of this profile.
    assert not ({"status_level", "trend"} & ERVISS.indicators)


def test_first_violation_points_at_the_offending_row():
    df = pd.DataFrame([_VALID, {**_VALID, "age": "99+"}, {**_VALID, "age": "bogus"}])
    label, message = ERVISS.first_violation(df)
    assert label == 1 and "99+" in message


def test_units_follow_indicator_with_erviss_country_exceptions():
    df = pd.DataFrame({
        "indicator": ["positivity", "deaths", "ILIconsultationrate", "ILIconsultationrate",
                      "ARIconsultationrate", "SARIrate"],
        "countryname": ["Greece", "Greece", "Greece", "Malta", "Finland", "Greece"],
    })
    units = ERVISS.units(df)
    assert units.iloc[:5].tolist() == [
        "percent", "count", "per_100k_population", "per_100_consultations", "per_100k_consultations"]
    assert pd.isna(units.iloc[5])  # SARIrate's unit is undocumented by ERVISS, so not guessed


def _row(**over):
    base = dict(survtype="non-sentinel", countryname="Greece", yearweek="2025-W01",
                indicator="positivity", age="total", value=12.3)
    return FeedRow(**{**base, **over})


def test_feedrow_rejects_non_numeric_nan_and_inf():
    for bad in ("lots", "nan", "inf"):
        with pytest.raises(Exception):
            _row(value=bad)


def test_feedrow_rejects_blank_countryname_and_yearweek():
    with pytest.raises(Exception):
        _row(countryname="")
    with pytest.raises(Exception):
        _row(yearweek="")


def test_profile_does_not_shadow_pydantic_validate():
    assert "validate" not in Profile.__dict__
