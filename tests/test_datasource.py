import pytest
from pathlib import Path
from health_signal.datasource import FileDataSource, EmptyDataSource

FIX = Path(__file__).parent / "fixtures" / "erviss_sample.csv"


def _src(tmp_path, text=None):
    d = tmp_path / "data"
    d.mkdir()
    (d / "feed.csv").write_text(text if text is not None else FIX.read_text(), encoding="utf-8")
    return FileDataSource(d)


def test_reads_and_folds_dimensions(tmp_path):
    rows = _src(tmp_path).query()
    assert len(rows) == 4
    r = rows[0]
    assert r.location == "Attica" and r.indicator == "positivity" and r.value == 12.3
    assert r.dimensions["pathogen"] == "Influenza" and r.dimensions["age"] == "total"
    assert "indicator" not in r.dimensions  # spine columns are not dimensions


def test_query_filters_by_pathogen_and_indicator(tmp_path):
    src = _src(tmp_path)
    assert all(r.dimensions["pathogen"] == "Influenza" for r in src.query(pathogen="Influenza"))
    assert {r.indicator for r in src.query(indicator="deaths")} == {"deaths"}


def test_query_week_range_inclusive(tmp_path):
    rows = _src(tmp_path).query(week_from="2025-W02", week_to="2025-W02")
    assert {r.period for r in rows} == {"2025-W02"}


def test_query_no_match_returns_empty(tmp_path):
    assert _src(tmp_path).query(location="Nowhere") == []


def test_bad_value_rejected_with_message(tmp_path):
    bad = "location,period,pathogen,age,indicator,value,unit\nA,2025-W01,Influenza,total,deaths,lots,count\n"
    with pytest.raises(ValueError, match="value"):
        _src(tmp_path, bad)


def test_out_of_vocab_indicator_rejected(tmp_path):
    bad = "location,period,pathogen,age,indicator,value,unit\nA,2025-W01,Influenza,total,bogus,1,count\n"
    with pytest.raises(ValueError, match="indicator"):
        _src(tmp_path, bad)


def test_empty_source_returns_empty():
    assert EmptyDataSource().query(pathogen="Influenza") == []
