import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from health_signal.analytics.series import assessed_series
from health_signal.app import create_app
from health_signal.config import Config
from health_signal.datasource import FileDataSource
from health_signal.profile import ERVISS
from analytics_support import ERVISS_HEADER, write_feed
from auth_stubs import AllowAll

_GR = {"extends": "erviss", "units": ["per_1000_admissions"], "dimension_vocab": {"survtype": ["private hospital"]},
       "denominators": [{"indicator": "SARIrate", "unit": "per_1000_admissions", "denominator": "hospitaladmissions",
                         "per": 1000}]}
_ROWS = ("Greece,2021-W01,private hospital,Influenza,,,total,positivity,12.5,percent\n"
         "Greece,2021-W01,SARI syndromic,,,,total,SARIrate,40,per_1000_admissions\n")


def _config(tmp_path, profiles=None, profile="erviss_gr", panels=()):
    feed = write_feed(tmp_path / "c", _ROWS)
    (tmp_path / "a").mkdir(exist_ok=True)
    return Config.model_validate({
        "schema_version": "1", "site": {"title": "T"}, "profiles": {"erviss_gr": _GR} if profiles is None else profiles,
        "data": {"feeds": [{"id": "clinical", "profile": profile, "dir": str(feed), "assessments": str(tmp_path / "a")}]},
        "targets": [{"id": "Influenza", "pages": [{"id": "clinical", "panels": list(panels)}]}]})


def test_a_feed_validates_against_its_extended_profile(tmp_path):
    cfg = _config(tmp_path)
    profile = cfg.profile("erviss_gr")
    assert profile.version == f"{ERVISS.version}+erviss_gr"
    assert len(FileDataSource(tmp_path / "c", profile).query()) == 2
    with pytest.raises(ValueError, match="per_1000_admissions"):   # the built-in is untouched
        FileDataSource(tmp_path / "c", cfg.profile("erviss"))


def test_panels_and_the_api_use_the_extended_vocabulary(tmp_path):
    panel = {"id": "priv", "query": {"feed": "clinical", "indicator": "positivity",
                                     "dimensions": {"survtype": "private hospital", "pathogen": "Influenza"}}}
    cfg = _config(tmp_path, panels=[panel])
    rows = TestClient(create_app(cfg, auth_provider=AllowAll())).get(
        "/api/data", params={"feed": "clinical", "survtype": "private hospital"}).json()
    assert [r["value"] for r in rows] == [12.5]
    with pytest.raises(ValidationError, match="private hospital"):
        _config(tmp_path / "base", profiles={}, profile="erviss", panels=[panel])


@pytest.mark.parametrize("extension, message", [
    ({**_GR, "extends": "nwss"}, "extends"),                                       # not a built-in
    ({**_GR, "dimension_vocab": {"setting": ["ward"]}}, "dimension"),              # a new key changes series identity
    ({**_GR, "dimension_vocab": {"pathogen": ["Measles"]}}, "pathogen"),           # the shared registry
    ({**_GR, "denominators": [{**_GR["denominators"][0], "unit": "per_mille"}]}, "unit"),
    ({**_GR, "denominators": [{**_GR["denominators"][0], "denominator": "visits"}]}, "denominator"),
    ({**_GR, "colour": "red"}, "colour"),                                          # a misspelt key
])
def test_bad_extensions_fail_at_load(tmp_path, extension, message):
    with pytest.raises(ValidationError, match=message):
        _config(tmp_path, profiles={"erviss_gr": extension})


def test_an_extension_cannot_take_a_built_in_name_and_feeds_need_a_known_profile(tmp_path):
    with pytest.raises(ValidationError, match="built-in"):
        _config(tmp_path, profiles={"erviss": _GR}, profile="erviss")
    with pytest.raises(ValidationError, match="unknown profile"):
        _config(tmp_path / "x", profile="erviss_fr")


def test_a_unit_scoped_denominator_applies_only_to_its_unit(tmp_path):
    rows = ("Greece,2021-W01,SARI syndromic,,,,total,SARIrate,40,per_1000_admissions\n"
            "Greece,2021-W01,SARI syndromic,,,,total,hospitaladmissions,500,count\n"
            "Cyprus,2021-W01,SARI syndromic,,,,total,SARIrate,7,per_100k\n")
    cfg = _config(tmp_path, panels=[{"id": "sari", "query": {"feed": "clinical", "indicator": "SARIrate",
                                                             "dimensions": {"survtype": "SARI syndromic", "age": "total"}}}])
    (tmp_path / "c" / "feed.csv").write_text(ERVISS_HEADER + rows, encoding="utf-8")
    sources = {"clinical": FileDataSource(tmp_path / "c", cfg.profile("erviss_gr"))}
    by_location = {s.location: s for s in assessed_series(cfg, sources)[0]}
    assert (by_location["Greece"].exposure, by_location["Greece"].per) == ([500.0], 1000.0)   # admissions
    assert (by_location["Cyprus"].exposure, by_location["Cyprus"].per) == ([1.0], 1.0)        # per population
