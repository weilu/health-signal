from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Branding(BaseModel):
    logo: str | None = None
    favicon: str | None = None
    theme: dict = Field(default_factory=dict)


class SiteConfig(BaseModel):
    # App/OpenAPI name only. User-facing display text (including a localized title) lives in the
    # locale files and is resolved by i18n key -- config carries structure + keys, not translations.
    title: str
    default_locale: str = "en"
    locales: list[str] = Field(default_factory=lambda: ["en"])
    # Path prefixes that bypass auth. Default empty = everything is locked (opt-in public).
    public_paths: list[str] = Field(default_factory=list)


class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
