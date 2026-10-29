import pytest
from fastapi.testclient import TestClient
from health_signal import create_app, load_config
from health_signal.auth import LocalAccountsProvider
from health_signal.config import Config


def _client(tmp_path):
    f = tmp_path / "dashboard.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: 'Test Dashboard'\n"
        "  default_locale: en\n"
        "  locales: [en]\n",
        encoding="utf-8",
    )
    config = load_config(f)
    # Stage-1 tests don't exercise login; an empty accounts map is enough to
    # build a DB-free provider without touching HEALTH_SIGNAL_SECRET_KEY.
    provider = LocalAccountsProvider(accounts={}, secret_key="test-secret")
    app = create_app(config, auth_provider=provider)
    # Secure cookies are only replayed by an http client over https.
    return TestClient(app, base_url="https://testserver")


def test_healthz_ok(tmp_path):
    r = _client(tmp_path).get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "0.1"


def test_root_redirects_to_login_when_unauthenticated(tmp_path):
    # Default access policy is all-locked (no public_paths), so an
    # unauthenticated request to any page now redirects to /login.
    r = _client(tmp_path).get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


_HEADER = "location,period,survtype,pathogen,pathogentype,pathogensubtype,age,indicator,value,unit\n"
_ROW = "{loc},2025-W01,primary care sentinel,,,,total,ILIconsultationrate,5,per_100k\n"


def _dashboard(tmp_path, locations, location_filter):
    feed = tmp_path / "clinical"
    feed.mkdir(parents=True)
    (feed / "feed.csv").write_text(_HEADER + "".join(_ROW.format(loc=x) for x in locations), encoding="utf-8")
    filters = {"location": {"default": locations[0], "options": [{"value": x} for x in locations]}} if location_filter else {}
    return Config.model_validate({"schema_version": "1", "site": {"title": "T"}, "filters": filters,
                                  "data": {"feeds": [{"id": "clinical", "profile": "erviss", "dir": str(feed)}]}})


def test_several_locations_without_a_location_filter_fail_at_startup(tmp_path):
    # Every query would mix the regions' rows: a chart, a tile and a summary row would each show a blend.
    with pytest.raises(ValueError, match="filters.location"):
        create_app(_dashboard(tmp_path, ["Greece", "Attica"], location_filter=False),
                   auth_provider=LocalAccountsProvider(accounts={}, secret_key="s"))


def test_one_location_needs_no_filter_and_several_need_one(tmp_path):
    create_app(_dashboard(tmp_path / "one", ["Greece"], location_filter=False),
               auth_provider=LocalAccountsProvider(accounts={}, secret_key="s"))
    create_app(_dashboard(tmp_path / "two", ["Greece", "Attica"], location_filter=True),
               auth_provider=LocalAccountsProvider(accounts={}, secret_key="s"))


def test_one_location_per_source_still_fails_when_the_sources_differ(tmp_path):
    # Greece's clinical feed beside Attica's wastewater: the overview would set one region's phase beside
    # the other's statuses.
    config = _dashboard(tmp_path / "c", ["Greece"], location_filter=False)
    ww = tmp_path / "w"
    ww.mkdir()
    (ww / "feed.csv").write_text("location,period,pathogen,aggregation,indicator,value,unit,quality\n"
                                 "Attica,2025-W01,Influenza,floMean,fluA,5,gcDay100k,\n", encoding="utf-8")
    data = {**config.data.model_dump(), "feeds": [*config.data.model_dump()["feeds"],
                                                  {"id": "wastewater", "profile": "phes_odm", "dir": str(ww)}]}
    with pytest.raises(ValueError, match="Attica.*Greece"):
        create_app(Config.model_validate({**config.model_dump(exclude={"data"}, exclude_computed_fields=True), "data": data}),
                   auth_provider=LocalAccountsProvider(accounts={}, secret_key="s"))
