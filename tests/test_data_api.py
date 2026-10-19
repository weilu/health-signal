from pathlib import Path
from fastapi.testclient import TestClient
from health_signal.app import create_app
from health_signal.auth import User
from health_signal.config import Config, DataConfig, SiteConfig

FIX = Path(__file__).parent / "fixtures" / "erviss_sample.csv"


class _AllowAll:
    def install(self, app):  # no login routes needed for the test
        pass

    async def current_user(self, request):
        return User(email="t@test")


class _DenyAll:
    def install(self, app):
        pass

    async def current_user(self, request):
        return None


def _app(tmp_path, provider, feed=None):
    d = tmp_path / "data"
    d.mkdir()
    (d / "feed.csv").write_text(feed if feed is not None else FIX.read_text(), encoding="utf-8")
    cfg = Config(schema_version="1.0.0", site=SiteConfig(title="T"), data=DataConfig(dir=str(d)))
    return create_app(cfg, auth_provider=provider)


def test_api_data_requires_auth(tmp_path):
    client = TestClient(_app(tmp_path, _DenyAll()))
    assert client.get("/api/data").status_code == 401


def test_api_data_returns_filtered_rows(tmp_path):
    client = TestClient(_app(tmp_path, _AllowAll()))
    r = client.get("/api/data", params={"pathogen": "Influenza"})
    assert r.status_code == 200
    body = r.json()
    assert [(r["dimensions"]["pathogen"], r["period"]) for r in body] == [("Influenza", "2025-W01"), ("Influenza", "2025-W02")]


def test_api_data_no_match_is_empty_list(tmp_path):
    client = TestClient(_app(tmp_path, _AllowAll()))
    r = client.get("/api/data", params={"location": "Nowhere"})
    assert r.status_code == 200 and r.json() == []


def test_api_data_bad_week_is_422(tmp_path):
    client = TestClient(_app(tmp_path, _AllowAll()))
    assert client.get("/api/data", params={"week_from": "not-a-week"}).status_code == 422


def test_data_config_is_server_only(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    cfg = Config(schema_version="1.0.0", site=SiteConfig(title="T"), data=DataConfig(dir=str(d)))
    assert "data" not in cfg.client_config() and "data" not in cfg.bootstrap_config()


def test_no_data_config_serves_empty(tmp_path):
    cfg = Config(schema_version="1.0.0", site=SiteConfig(title="T"))
    client = TestClient(create_app(cfg, auth_provider=_AllowAll()))
    r = client.get("/api/data")
    assert r.status_code == 200 and r.json() == []


def test_api_data_openapi_response_is_typed(tmp_path):
    schema = _app(tmp_path, _AllowAll()).openapi()
    resp = schema["paths"]["/api/data"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert resp["type"] == "array" and resp["items"]["$ref"].endswith("/FeedRow")


def test_api_data_filters_on_survtype(tmp_path):
    feed = FIX.read_text() + "Greece,2025-W01,SARI virological,RSV,total,positivity,9.5,percent,ERVISS\n"
    client = TestClient(_app(tmp_path, _AllowAll(), feed))
    sari = client.get("/api/data", params={"survtype": "SARI virological"}).json()
    assert [(r["dimensions"]["survtype"], r["value"]) for r in sari] == [("SARI virological", 9.5)]
    rest = client.get("/api/data", params={"survtype": "non-sentinel"}).json()
    assert len(rest) == 4 and {r["dimensions"]["survtype"] for r in rest} == {"non-sentinel"}
