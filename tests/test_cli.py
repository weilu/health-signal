import pytest

from health_signal import __main__ as cli
from health_signal.analytics.store import SettingsChanged


def test_bare_invocation_still_serves(monkeypatch):
    served = {}
    monkeypatch.setattr(cli, "load_config", lambda path: f"cfg:{path}")
    monkeypatch.setattr(cli, "create_app", lambda cfg: f"app:{cfg}")
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, host, port: served.update(app=app, port=port))
    cli.main(["--config", "x.yaml", "--port", "9"])
    assert served == {"app": "app:cfg:x.yaml", "port": 9}
    cli.main(["serve", "--config", "y.yaml"])
    assert served == {"app": "app:cfg:y.yaml", "port": 8000}


def test_assess_passes_its_flags(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "load_config", lambda path: path)
    monkeypatch.setattr(cli, "assess", lambda cfg, full, method, jobs: calls.append((cfg, full, method, jobs)))
    cli.main(["assess", "--config", "d.yaml", "--full", "--method", "mem", "--jobs", "4"])
    cli.main(["assess", "--config", "d.yaml"])
    assert calls == [("d.yaml", True, "mem", 4), ("d.yaml", False, None, 1)]


@pytest.mark.parametrize("error", [RuntimeError("no R"), SettingsChanged("assessed with other settings"),
                                   ValueError("bad phase stream")])
def test_assess_failures_exit_non_zero_with_the_reason(monkeypatch, capsys, error):
    def fail(cfg, full, method, jobs):
        raise error
    monkeypatch.setattr(cli, "load_config", lambda path: path)
    monkeypatch.setattr(cli, "assess", fail)
    with pytest.raises(SystemExit) as exit_:
        cli.main(["assess", "--config", "d.yaml"])
    assert exit_.value.code == 1 and str(error) in capsys.readouterr().err
