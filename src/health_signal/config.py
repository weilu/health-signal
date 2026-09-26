from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


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

    @field_validator("public_paths")
    @classmethod
    def _normalize_public_paths(cls, paths: list[str]) -> list[str]:
        # Normalize to a leading-slash, no-trailing-slash prefix so create_app consumes a clean list.
        # Only a literal "/" may be match-all: reject "", "//", whitespace, etc. that also normalize
        # to "/" and would silently make the whole site public ([] = all locked, ["/"] = all public).
        normalized = []
        for p in paths:
            if p != "/" and not p.strip("/").strip():
                raise ValueError(f'{p!r} is not a valid path prefix; use "/" (exactly) for the whole site')
            normalized.append("/" + p.strip("/"))
        return normalized


class Page(BaseModel):
    id: str
    path: str
    label_key: str | None = None  # i18n key; text lives in locale files, not config


class Target(BaseModel):
    # A surveillance target (e.g. a pathogen). label_key -> locale files; id can derive one by convention.
    id: str
    label_key: str | None = None
    pages: list[Page] = Field(default_factory=list)


class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)
    targets: list[Target] = Field(default_factory=list)

    def bootstrap_config(self) -> dict:
        # Whitelisted slice injected pre-login: only what the shell + login page need.
        return {
            "title": self.site.title,
            "branding": self.branding.model_dump(),
            "defaultLocale": self.site.default_locale,
            "locales": self.site.locales,
        }

    def client_config(self) -> dict:
        # Full client view-model (authenticated). Superset of bootstrap; still excludes server-only
        # fields (public_paths, schema_version, future data-source config).
        return {
            **self.bootstrap_config(),
            "targets": [t.model_dump() for t in self.targets],
        }


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
