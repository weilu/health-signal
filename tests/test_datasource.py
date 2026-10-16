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
    assert r.location == "Greece" and r.indicator == "positivity" and r.value == 12.3
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


def test_missing_data_dir_fails_fast(tmp_path):
    with pytest.raises(ValueError, match="not a directory"):
        FileDataSource(tmp_path / "nope")


def test_bom_header_loads(tmp_path):
    rows = _src(tmp_path, "﻿" + FIX.read_text()).query()
    assert len(rows) == 4


def test_missing_column_names_the_column(tmp_path):
    bad = "location,period,pathogen,age,indicator,value\nA,2025-W01,Influenza,total,deaths,1\n"
    with pytest.raises(ValueError, match="missing column.*unit"):
        _src(tmp_path, bad)


def test_spine_cells_are_trimmed(tmp_path):
    text = "location,period,survtype,pathogen,age,indicator,value,unit,datasource\n Greece , 2025-W01 , non-sentinel ,Influenza,total, deaths , 3 , count , ERVISS \n"
    r = _src(tmp_path, text).query()[0]
    assert (r.location, r.period, r.indicator, r.value, r.unit, r.datasource) == ("Greece", "2025-W01", "deaths", 3.0, "count", "ERVISS")


def test_vocab_error_names_file_and_line(tmp_path):
    bad = "location,period,survtype,pathogen,age,indicator,value,unit\nA,2025-W01,non-sentinel,Influenza,total,bogus,1,count\n"
    with pytest.raises(ValueError, match=r"feed\.csv row 1: .*indicator"):
        _src(tmp_path, bad)


def test_non_utf8_file_names_the_file(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    header = b"location,period,survtype,pathogen,age,indicator,value,unit\n"
    (d / "feed.csv").write_bytes(header + "\u0391\u03c4\u03c4\u03b9\u03ba\u03ae".encode("cp1253") + b",2025-W01,non-sentinel,Influenza,total,deaths,1,count\n")
    with pytest.raises(ValueError, match=r"feed\.csv: not valid UTF-8"):
        FileDataSource(d)


_H = "location,period,survtype,pathogen,age,indicator,value,unit,datasource\n"
_OK = "A,2025-W01,non-sentinel,Influenza,total,deaths,1,count,X\n"


def test_unclosed_quote_fails_instead_of_swallowing_rows(tmp_path):
    with pytest.raises(ValueError, match=r"feed\.csv: malformed CSV"):
        _src(tmp_path, _H + _OK.replace(",X", ',"X') + _OK + _OK)




def test_files_with_different_optional_columns_combine(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    (d / "a.csv").write_text(_H + _OK, encoding="utf-8")
    (d / "b.csv").write_text("location,period,survtype,age,indicator,value,unit\nB,2025-W02,non-sentinel,total,deaths,2,count\n", encoding="utf-8")
    rows = FileDataSource(d).query()
    assert [(r.location, r.datasource, "pathogen" in r.dimensions) for r in rows] == [("A", "X", True), ("B", None, False)]


def test_empty_file_names_the_file(tmp_path):
    for text in ("", "\n\n"):
        with pytest.raises(ValueError, match=r"feed\.csv: empty file"):
            FileDataSource(_write(tmp_path, text))


def test_error_reports_data_row_not_physical_line(tmp_path):
    # The reader skips blank lines, so only a data-row number is accurate.
    bad = _H + _OK + "\n" + _OK.replace("count", "furlongs")
    with pytest.raises(ValueError, match=r"feed\.csv row 2: .*furlongs"):
        _src(tmp_path, bad)


def _write(tmp_path, text):
    d = tmp_path / f"data{len(list(tmp_path.iterdir()))}"
    d.mkdir()
    (d / "feed.csv").write_text(text, encoding="utf-8")
    return d


def test_literal_na_subtype_is_kept_as_text(tmp_path):
    text = "location,period,survtype,pathogen,pathogentype,pathogensubtype,age,indicator,value,unit\nGreece,2025-W01,non-sentinel,RSV,RSV-A,NA,0-4,detections,4,count\n"
    r = _src(tmp_path, text).query()[0]
    assert r.dimensions["pathogensubtype"] == "NA"


def test_query_filters_on_any_profile_dimension(tmp_path):
    text = ("location,period,survtype,pathogen,pathogentype,pathogensubtype,age,indicator,value,unit\n"
            "Greece,2025-W01,non-sentinel,Influenza,Influenza A,A(H3),total,detections,3,count\n"
            "Greece,2025-W01,non-sentinel,Influenza,Influenza B,B/Vic,total,detections,5,count\n")
    src = _src(tmp_path, text)
    assert [r.value for r in src.query(pathogentype="Influenza B")] == [5.0]
    assert [r.value for r in src.query(pathogensubtype="A(H3)", survtype="non-sentinel")] == [3.0]


def test_query_rejects_unknown_filter(tmp_path):
    with pytest.raises(ValueError, match="unknown filter"):
        _src(tmp_path).query(colour="red")
