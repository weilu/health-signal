from fastapi import FastAPI

from health_signal.__main__ import _parse, main


def test_parse_defaults():
    args = _parse([])
    assert args.config == "dashboard.yaml"
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_parse_overrides():
    args = _parse(["--config", "x.yaml", "--host", "0.0.0.0", "--port", "9000"])
    assert args.config == "x.yaml"
    assert args.host == "0.0.0.0"
    assert args.port == 9000


def test_main_builds_app_and_calls_uvicorn(tmp_path, monkeypatch):
    cfg = tmp_path / "dashboard.yaml"
    cfg.write_text(
        "schema_version: '0.1'\nsite:\n  title: 'X'\n", encoding="utf-8"
    )
    captured = {}
    monkeypatch.setattr(
        "health_signal.__main__.uvicorn.run",
        lambda app, host, port: captured.update(app=app, host=host, port=port),
    )
    main(["--config", str(cfg), "--host", "0.0.0.0", "--port", "1234"])
    assert isinstance(captured["app"], FastAPI)   # config loaded + app built through the CLI path
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 1234
