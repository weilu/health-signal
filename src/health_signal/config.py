from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Branding(BaseModel):
    logo: str | None = None
    favicon: str | None = None
    theme: dict = Field(default_factory=dict)


class SiteConfig(BaseModel):
    title: dict[str, str]                 # locale code -> display title
    default_locale: str = "en"
    locales: list[str] = Field(default_factory=lambda: ["en"])


class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
