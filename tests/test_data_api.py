from pathlib import Path
from fastapi.testclient import TestClient
from health_signal.app import create_app
from health_signal.config import Config, DataConfig, SiteConfig
from auth_stubs import AllowAll, DenyAll

FIX = Path(__file__).parent / "fixtures" / "erviss_sample.csv"
ODM = Path(__file__).parent / "fixtures" / "odm_sample.csv"


def _app(tmp_path, provider, feed=None, ww=None):
    feeds = []
    for fid, profile, text in (("clinical", "erviss", feed if feed is not None else FIX.read_text()),
                               ("wastewater", "phes_odm", ww if ww is not None else ODM.read_text())):
        d = tmp_path / fid
        d.mkdir()
        (d / "feed.csv").write_text(text, encoding="utf-8")
        feeds.append({"id": fid, "profile": profile, "dir": str(d)})
    cfg = Config(schema_version="1.0.0", site=SiteConfig(title="T"), data=DataConfig(feeds=feeds))
    return create_app(cfg, auth_provider=provider)


def test_api_data_requires_auth(tmp_path):
    client = TestClient(_app(tmp_path, DenyAll()))
    assert client.get("/api/data").status_code == 401


def test_api_data_returns_filtered_rows(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))
    r = client.get("/api/data", params={"feed": "clinical", "pathogen": "Influenza"})
    assert r.status_code == 200
    body = r.json()
    assert [(r["dimensions"]["pathogen"], r["period"]) for r in body] == [("Influenza", "2025-W01"), ("Influenza", "2025-W02")]


def test_api_data_no_match_is_empty_list(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))
    r = client.get("/api/data", params={"feed": "clinical", "location": "Nowhere"})
    assert r.status_code == 200 and r.json() == []


def test_api_data_bad_week_is_422(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))
    assert client.get("/api/data", params={"feed": "clinical", "week_from": "not-a-week"}).status_code == 422


def test_data_config_is_server_only(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    cfg = Config(schema_version="1.0.0", site=SiteConfig(title="T"),
                 data=DataConfig(feeds=[{"id": "c", "profile": "erviss", "dir": str(d)}]))
    assert "data" not in cfg.client_config() and "data" not in cfg.bootstrap_config()


def test_no_data_config_has_no_feeds(tmp_path):
    cfg = Config(schema_version="1.0.0", site=SiteConfig(title="T"))
    client = TestClient(create_app(cfg, auth_provider=AllowAll()))
    assert client.get("/api/data", params={"feed": "clinical"}).status_code == 422
    assert client.get("/api/periods").json() is None


def test_api_data_reads_the_named_feed(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))
    r = client.get("/api/data", params={"feed": "wastewater", "indicator": "fluA", "aggregation": "floMean"})
    assert r.status_code == 200
    assert [(x["period"], x["value"], x["quality"]) for x in r.json()] == [
        ("2025-W02", 1200.5, None), ("2025-W03", 0.0, "beLOD"), ("2025-W04", 950.0, None)]


def test_api_data_requires_a_known_feed(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))
    assert client.get("/api/data").status_code == 422
    assert client.get("/api/data", params={"feed": "sewage"}).status_code == 422


def test_api_data_rejects_another_profiles_dimension(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))
    r = client.get("/api/data", params={"feed": "clinical", "aggregation": "floMean"})
    assert r.status_code == 422 and "aggregation" in r.json()["detail"]


def test_api_periods_requires_auth(tmp_path):
    assert TestClient(_app(tmp_path, DenyAll())).get("/api/periods").status_code == 401


def test_api_periods_spans_all_feeds(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll()))  # clinical 2025-W01..W03, wastewater W02..W04
    assert client.get("/api/periods").json() == {"first": "2025-W01", "last": "2025-W04"}


def test_api_periods_skips_an_empty_feed(tmp_path):
    client = TestClient(_app(tmp_path, AllowAll(), feed=FIX.read_text().splitlines()[0] + "\n"))
    assert client.get("/api/periods").json() == {"first": "2025-W02", "last": "2025-W04"}


def test_api_data_openapi_response_is_typed(tmp_path):
    schema = _app(tmp_path, AllowAll()).openapi()
    resp = schema["paths"]["/api/data"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert resp["type"] == "array" and resp["items"]["$ref"].endswith("/FeedRow")


def test_api_data_filters_on_survtype(tmp_path):
    feed = FIX.read_text() + "Greece,2025-W01,SARI virological,RSV,total,positivity,9.5,percent,ERVISS\n"
    client = TestClient(_app(tmp_path, AllowAll(), feed))
    sari = client.get("/api/data", params={"feed": "clinical", "survtype": "SARI virological"}).json()
    assert [(r["dimensions"]["survtype"], r["value"]) for r in sari] == [("SARI virological", 9.5)]
    rest = client.get("/api/data", params={"feed": "clinical", "survtype": "non-sentinel"}).json()
    assert len(rest) == 4 and {r["dimensions"]["survtype"] for r in rest} == {"non-sentinel"}
