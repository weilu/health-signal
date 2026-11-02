import json

import pytest
from fastapi.testclient import TestClient

from health_signal import create_app
from health_signal.config import Config
from health_signal.methodology import load_methodology
from analytics_support import write_feed
from auth_stubs import AllowAll, DenyAll

_GR = {"extends": "erviss", "units": ["per_1000_admissions"],
       "denominators": [{"rate": "SARIrate", "unit": "per_1000_admissions", "denominator": "hospitaladmissions",
                         "per": 1000}]}


def _config(tmp_path, pages=None, locales=("en",), feeds=1, analytics=None):
    site = {"title": "T", "default_locale": "en", "locales": list(locales)}
    if pages is not None:
        directory = tmp_path / "methodology"
        directory.mkdir(exist_ok=True)
        for lang, text in pages.items():
            (directory / f"{lang}.md").write_text(text, encoding="utf-8")
        site["methodology_dir"] = str(directory)
    feed = write_feed(tmp_path / "c", "")
    feed_list = [{"id": f"clinical{i or ''}", "profile": "erviss_gr", "dir": str(feed),
                  "assessments": str(tmp_path / f"a{i}")} for i in range(feeds)]
    for f in feed_list:
        (tmp_path / f["assessments"].rsplit("/", 1)[1]).mkdir(exist_ok=True)
    (tmp_path / "phase.csv").write_text("location,pathogen,period,method,phase\n", encoding="utf-8")
    (tmp_path / "s.csv").write_text("location,pathogen,method,role,feed,series\n", encoding="utf-8")
    return Config.model_validate({
        "schema_version": "1", "site": site, "profiles": {"erviss_gr": _GR},
        "surveillance": {"year_start_week": 21},
        "filters": {"location": {"default": "Greece", "options": [{"value": "Greece"}, {"value": "Attica"}]}},
        "data": {"feeds": feed_list, "phases": str(tmp_path / "phase.csv"), "phase_streams": str(tmp_path / "s.csv")},
        "targets": [{"id": "Influenza", "pages": [{"id": "clinical", "panels": [
            {"id": "ili", "query": {"feed": "clinical", "indicator": "ILIconsultationrate",
                                    "dimensions": {"survtype": "primary care syndromic", "age": "total"}}},
            {"id": "sari", "query": {"feed": "clinical", "indicator": "SARIrate",
                                     "dimensions": {"survtype": "SARI syndromic", "age": "total"}}}]}]}],
        "analytics": {"phase_streams": [{"pathogen": "Influenza", "location": "Greece",
                                         "streams": {"cases": "clinical/ili", "admissions": "clinical/sari"}}],
                      **(analytics or {})}})


def _page(tmp_path, text, **options):
    return load_methodology(_config(tmp_path, {"en": text}, **options))["en"]


def test_values_substitute_as_marked_values(tmp_path):
    md = _page(tmp_path, "Week {{surveillance.year_start_week}}, ending at {{analytics.aedseo.wave_end.burden_level_decrease}}",
               analytics={"aedseo": {"wave_end": {"burden_level_decrease": "medium"}}})["markdown"]
    assert "Week `hs:21`" in md and "`hs:t:level.medium`" in md


def test_values_substitute_inside_table_cells(tmp_path):
    md = _page(tmp_path, "| setting | value |\n|---|---|\n| start | {{surveillance.year_start_week}} |\n")["markdown"]
    assert "| start | `hs:21` |" in md


def test_blocks_become_fenced_markers_with_their_data(tmp_path):
    page = _page(tmp_path, "Streams:\n\n{{> streams}}\n")
    assert "```hs-block\nstreams\n```" in page["markdown"]
    rows = {(r["target"], r["location"]): r["streams"] for r in page["blocks"]["streams"]}
    assert rows[("Influenza", "Greece")] == {"cases": {"page": "clinical", "panel": "ili"},
                                             "admissions": {"page": "clinical", "panel": "sari"}}
    assert rows[("Influenza", "Attica")] is None


def test_a_block_must_stand_on_its_own_line(tmp_path):
    with pytest.raises(ValueError, match=r"en\.md line 1.*streams"):
        _page(tmp_path, "See {{> streams}} here")


def test_the_method_block_inlines_the_library_text(tmp_path):
    md = _page(tmp_path, "# Ours\n\n{{> method}}\n")["markdown"]
    assert "# Ours" in md and "## " in md and "{{" not in md


def test_without_a_methodology_dir_the_page_is_the_library_text(tmp_path):
    md = load_methodology(_config(tmp_path))["en"]["markdown"]
    assert md.startswith("#") and "{{" not in md


def test_a_language_without_library_text_falls_back_to_english(tmp_path):
    pages = load_methodology(_config(tmp_path, {"en": "{{> method}}", "fr": "{{> method}}"}, locales=("en", "fr")))
    assert pages["fr"]["markdown"] == pages["en"]["markdown"]


def test_an_unknown_placeholder_stops_startup_naming_it(tmp_path):
    with pytest.raises(ValueError, match=r"el\.md.*surveilance\.year_start_week"):
        load_methodology(_config(tmp_path, {"en": "ok", "el": "{{surveilance.year_start_week}}"}, locales=("en", "el")))


def test_a_missing_file_for_an_offered_language_stops_startup(tmp_path):
    with pytest.raises(ValueError, match="el.md"):
        load_methodology(_config(tmp_path, {"en": "ok"}, locales=("en", "el")))


def test_indicator_models_are_rules_from_the_profiles(tmp_path):
    rules = _page(tmp_path, "x", feeds=2)["blocks"]["indicator_models"]
    assert {"kind": "rate", "indicator": "SARIrate", "unit": "per_1000_admissions", "denominator": "hospitaladmissions",
            "per": 1000} in rules
    assert {"kind": "count", "units": ["count"]} in rules
    assert rules[-1] == {"kind": "constant"} and len(rules) == len({str(r) for r in rules})   # merged once


def test_the_build_is_read_from_each_feeds_settings(tmp_path):
    cfg = _config(tmp_path, {"en": "Built with {{method.build}}"}, feeds=2)
    for i, version in enumerate(["1.2.0.9000+de5c15e", "1.1.0"]):
        (tmp_path / f"a{i}" / "assessed_with.csv").write_text(
            f"method,setting,value\naedseo,package_version,{version}\n", encoding="utf-8")
    md = load_methodology(cfg)["en"]["markdown"]
    assert "1.2.0.9000+de5c15e" in md and "1.1.0" in md


def test_the_build_is_a_dash_before_any_assessment(tmp_path):
    assert "`hs:—`" in _page(tmp_path, "{{method.build}}")["markdown"]


def _client(cfg, auth=None):
    return TestClient(create_app(cfg, auth_provider=auth or AllowAll()))


def test_it_serves_the_page_and_its_blocks(tmp_path):
    body = _client(_config(tmp_path, {"en": "Week {{surveillance.year_start_week}}"})).get("/api/methodology/en").json()
    assert "`hs:21`" in body["markdown"] and "streams" in body["blocks"]


def test_the_methodology_is_behind_login(tmp_path):
    assert _client(_config(tmp_path), DenyAll()).get("/api/methodology/en").status_code == 401


def test_a_language_not_offered_is_not_found(tmp_path):
    assert _client(_config(tmp_path)).get("/api/methodology/fr").status_code == 404


def test_methodology_dir_is_not_sent_to_the_browser(tmp_path):
    assert "methodology_dir" not in json.dumps(_config(tmp_path, {"en": "x"}).client_config())
