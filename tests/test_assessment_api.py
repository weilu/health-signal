from pathlib import Path
from fastapi.testclient import TestClient
from health_signal.app import create_app
from health_signal.auth import User
from health_signal.config import Config, DataConfig, SiteConfig

FIX = Path(__file__).parent / "fixtures"


class _AllowAll:
    def install(self, app):
        pass

    async def current_user(self, request):
        return User(email="t@test")


def _client(tmp_path, with_assessments=True):
    (tmp_path / "ww").mkdir()
    (tmp_path / "ww" / "feed.csv").write_text((FIX / "odm_sample.csv").read_text(), encoding="utf-8")
    feed = {"id": "wastewater", "profile": "phes_odm", "dir": str(tmp_path / "ww")}
    if with_assessments:
        feed["assessments"] = str(FIX / "assessed")
    cfg = Config(schema_version="1", site=SiteConfig(title="T"),
                 data=DataConfig(feeds=[feed], phases=str(FIX / "phases") if with_assessments else None))
    return TestClient(create_app(cfg, auth_provider=_AllowAll()))


def test_assessments_filter_like_api_data(tmp_path):
    r = _client(tmp_path).get("/api/assessments", params={
        "feed": "wastewater", "indicator": "fluA", "aggregation": "floMean", "week_from": "2025-W03"})
    assert [(x["period"], x["level"], x["trend"]) for x in r.json()] == [("2025-W03", "medium", "stable")]


def test_thresholds_overlap_the_range(tmp_path):
    r = _client(tmp_path).get("/api/thresholds", params={"feed": "wastewater", "week_from": "2025-W10", "week_to": "2025-W40"})
    assert [(x["from"], x["to"], x["level"]) for x in r.json()] == [("2024-W21", "2025-W20", "low"), ("2024-W21", "2025-W20", "medium")]


def test_phases_by_pathogen(tmp_path):
    r = _client(tmp_path).get("/api/phases", params={"pathogen": "Influenza", "week_to": "2025-W02"})
    assert [(x["period"], x["phase"]) for x in r.json()] == [("2025-W02", "in_season")]


def test_a_feed_without_assessments_returns_empty(tmp_path):
    client = _client(tmp_path, with_assessments=False)
    assert client.get("/api/assessments", params={"feed": "wastewater"}).json() == []
    assert client.get("/api/thresholds", params={"feed": "wastewater"}).json() == []
    assert client.get("/api/phases").json() == []


def test_unknown_feed_or_dimension_is_422(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/assessments", params={"feed": "sewage"}).status_code == 422
    assert client.get("/api/thresholds", params={"feed": "wastewater", "survtype": "x"}).status_code == 422
