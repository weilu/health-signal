import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from health_signal import create_app
from health_signal.config import Config, Page, Panel, SiteConfig, Target
from auth_stubs import AllowAll, DenyAll


def _config(tmp_path, embeds_dir=True, page=None):
    directory = tmp_path / "embeds"
    (directory / "forecast").mkdir(parents=True, exist_ok=True)
    (directory / "forecast" / "index.html").write_text("<p>forecast</p>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    site = SiteConfig(title="T", embeds_dir=directory if embeds_dir else None)
    return Config(schema_version="1", site=site,
                  targets=[Target(id="AMR", pages=[page or Page(id="forecast", embed="forecast/index.html")])])


def _client(config, auth=None):
    return TestClient(create_app(config, auth_provider=auth or AllowAll()))


def test_an_embedded_page_is_served_from_the_embeds_dir(tmp_path):
    r = _client(_config(tmp_path)).get("/embeds/forecast/index.html")
    assert r.status_code == 200 and r.text == "<p>forecast</p>"


def test_embeds_are_behind_login(tmp_path):
    assert _client(_config(tmp_path), DenyAll()).get("/embeds/forecast/index.html").status_code == 401


@pytest.mark.parametrize("path", ["/embeds/forecast/..%2f..%2fsecret.txt", "/embeds/%2e%2e/secret.txt", "/embeds/forecast/missing.html",
                                  "/embeds/forecast"])
def test_only_files_inside_the_embeds_dir_are_served(tmp_path, path):
    assert _client(_config(tmp_path)).get(path).status_code == 404


def test_the_page_tells_the_browser_what_it_embeds(tmp_path):
    page = _config(tmp_path).client_config()["targets"][0]["pages"][0]
    assert page["embed"] == "forecast/index.html"


def test_an_embed_needs_an_embeds_dir_holding_it(tmp_path):
    with pytest.raises(ValidationError, match="embeds_dir"):
        _config(tmp_path, embeds_dir=False)
    with pytest.raises(ValidationError, match="missing.html"):
        _config(tmp_path, page=Page(id="forecast", embed="missing.html"))


def test_a_page_embeds_or_has_panels_not_both():
    with pytest.raises(ValidationError, match="embed"):
        Page(id="forecast", embed="forecast/index.html", panels=[Panel(id="p", query={"feed": "c", "indicator": "deaths"})])


def test_a_link_the_deployment_put_in_the_embeds_dir_is_followed(tmp_path):
    # Data kept outside the repository (a shared folder) is linked in beside the page that reads it.
    config = _config(tmp_path)
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "forecast.json").write_text("{}", encoding="utf-8")
    (tmp_path / "embeds" / "forecast" / "data").symlink_to(shared)
    assert _client(config).get("/embeds/forecast/data/forecast.json").text == "{}"
