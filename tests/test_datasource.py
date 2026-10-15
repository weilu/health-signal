import pytest
from pathlib import Path
from health_signal.datasource import FileDataSource, EmptyDataSource

FIX = Path(__file__).parent / "fixtures" / "erviss_sample.csv"

# ERVISS's own headers; ILIARIRates-style files carry no pathogen columns at all.
_H = "survtype,countryname,yearweek,pathogen,pathogentype,pathogensubtype,indicator,age,value\n"
_OK = "non-sentinel,Greece,2025-W01,Influenza,Influenza A,A(H3),deaths,total,1\n"
_RATES_H = "survtype,countryname,yearweek,indicator,age,value\n"


def _write(tmp_path, text, name="feed.csv"):
    d = tmp_path / f"data{len(list(tmp_path.iterdir()))}"
    d.mkdir()
    (d / name).write_text(text, encoding="utf-8")
    return d


def _src(tmp_path, text=None):
    return FileDataSource(_write(tmp_path, text if text is not None else FIX.read_text()))


def test_reads_erviss_columns(tmp_path):
    rows = _src(tmp_path).query()
    assert len(rows) == 4
    r = rows[0]
    assert (r.survtype, r.countryname, r.yearweek, r.pathogen, r.pathogensubtype, r.indicator, r.age, r.value) == (
        "non-sentinel", "Greece", "2025-W01", "Influenza", "A(H3)", "positivity", "total", 12.3)
    assert r.unit == "percent" and r.region is None and r.datasource is None


def test_literal_na_subtype_is_kept(tmp_path):
    rsv = _src(tmp_path).query(pathogen="RSV")
    assert [r.pathogensubtype for r in rsv] == ["NA"]


def test_query_filters(tmp_path):
    src = _src(tmp_path)
    assert {r.pathogen for r in src.query(pathogen="Influenza")} == {"Influenza"}
    assert {r.indicator for r in src.query(indicator="deaths")} == {"deaths"}
    assert {r.yearweek for r in src.query(week_from="2025-W02", week_to="2025-W02")} == {"2025-W02"}
    assert src.query(countryname="Nowhere") == []


def test_region_extension_loads_and_filters(tmp_path):
    text = _H.replace("countryname,", "countryname,region,") + _OK.replace("Greece,", "Greece,Attica,") + _OK.replace("Greece,", "Greece,,")
    src = _src(tmp_path, text)
    assert [r.region for r in src.query()] == ["Attica", None]
    assert len(src.query(region="Attica")) == 1


def test_rates_file_without_pathogen_columns_combines(tmp_path):
    d = _write(tmp_path, _H + _OK, "a.csv")
    (d / "b.csv").write_text(_RATES_H + "primary care syndromic,Greece,2025-W02,ILIconsultationrate,total,40.5\n", encoding="utf-8")
    ili = FileDataSource(d).query(indicator="ILIconsultationrate")
    assert [(r.pathogen, r.unit, r.value) for r in ili] == [(None, "per_100k_population", 40.5)]


def test_columns_outside_the_profile_are_ignored(tmp_path):
    rows = _src(tmp_path, _H.rstrip() + ",notes\n" + _OK.rstrip() + ",free text\n").query()
    assert len(rows) == 1 and not hasattr(rows[0], "notes")


def test_cells_are_trimmed(tmp_path):
    r = _src(tmp_path, _H + " non-sentinel , Greece , 2025-W01 ,Influenza,Influenza A,A(H3), deaths , total , 3 \n").query()[0]
    assert (r.survtype, r.countryname, r.yearweek, r.indicator, r.age, r.value) == (
        "non-sentinel", "Greece", "2025-W01", "deaths", "total", 3.0)


def test_bad_value_rejected_with_message(tmp_path):
    with pytest.raises(ValueError, match="value"):
        _src(tmp_path, _H + _OK.replace(",1\n", ",lots\n"))


def test_vocab_error_names_file_and_row(tmp_path):
    with pytest.raises(ValueError, match=r"feed\.csv row 1: .*indicator"):
        _src(tmp_path, _H + _OK.replace("deaths", "bogus"))


def test_error_reports_data_row_not_physical_line(tmp_path):
    # A blank line is skipped by the reader, so a physical line number would be off; the row number isn't.
    with pytest.raises(ValueError, match=r"feed\.csv row 2: .*99\+"):
        _src(tmp_path, _H + _OK + "\n" + _OK.replace("total", "99+"))


def test_missing_column_names_the_column(tmp_path):
    with pytest.raises(ValueError, match="missing column.*age"):
        _src(tmp_path, _H.replace(",age", "") + _OK.replace(",total", ""))


def test_missing_data_dir_fails_fast(tmp_path):
    with pytest.raises(ValueError, match="not a directory"):
        FileDataSource(tmp_path / "nope")


def test_bom_header_loads(tmp_path):
    assert len(_src(tmp_path, "﻿" + FIX.read_text()).query()) == 4


def test_non_utf8_file_names_the_file(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    greek = "Αττική".encode("cp1253")
    (d / "feed.csv").write_bytes(_H.encode() + b"non-sentinel," + greek + b",2025-W01,Influenza,Influenza A,A(H3),deaths,total,1\n")
    with pytest.raises(ValueError, match=r"feed\.csv: not valid UTF-8"):
        FileDataSource(d)


def test_unclosed_quote_fails_instead_of_swallowing_rows(tmp_path):
    with pytest.raises(ValueError, match=r"feed\.csv: malformed CSV"):
        _src(tmp_path, _H + _OK.replace("non-sentinel", '"non-sentinel') + _OK + _OK)


def test_empty_file_names_the_file(tmp_path):
    for text in ("", "\n\n"):
        with pytest.raises(ValueError, match=r"feed\.csv: empty file"):
            _src(tmp_path, text)


def test_empty_source_returns_empty():
    assert EmptyDataSource().query(pathogen="Influenza") == []
