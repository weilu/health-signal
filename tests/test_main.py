import pytest
from fastapi import FastAPI

from health_signal.__main__ import main


@pytest.fixture
def config_file(tmp_path):
    f = tmp_path / "dashboard.yaml"
    f.write_text("schema_version: '0.1'\nsite:\n  title: 'X'\n", encoding="utf-8")
    return f


def _run_main(monkeypatch, argv):
    """Invoke the entry point with uvicorn.run stubbed, returning what it was called with."""
    captured = {}
    monkeypatch.setattr(
        "health_signal.__main__.uvicorn.run",
        lambda app, host, port: captured.update(app=app, host=host, port=port),
    )
    main(argv)
    return captured


def test_main_serves_built_app_with_defaults(config_file, monkeypatch):
    captured = _run_main(monkeypatch, ["--config", str(config_file)])
    assert isinstance(captured["app"], FastAPI)   # config loaded + app built via the entry point
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8000


def test_main_applies_host_and_port_overrides(config_file, monkeypatch):
    captured = _run_main(
        monkeypatch, ["--config", str(config_file), "--host", "0.0.0.0", "--port", "1234"]
    )
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 1234
