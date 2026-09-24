import pytest
from pydantic import ValidationError
from health_signal.config import load_config


def test_load_valid_config(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: 'X'\n",
        encoding="utf-8",
    )
    cfg = load_config(f)
    assert cfg.schema_version == "0.1"
    assert cfg.site.title == "X"
    assert cfg.site.default_locale == "en"      # default applied


def test_missing_required_field_raises(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("site:\n  title: 'X'\n", encoding="utf-8")   # no schema_version
    with pytest.raises(ValidationError):
        load_config(f)
