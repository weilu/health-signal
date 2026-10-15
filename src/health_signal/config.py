from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .profile import ERVISS


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

    @model_validator(mode="after")
    def _default_locale_is_offered(self) -> "SiteConfig":
        # fallbackLng is default_locale; if it isn't a configured locale, fallback resolves to
        # nothing and the UI renders raw keys.
        if self.default_locale not in self.locales:
            raise ValueError(
                f"default_locale {self.default_locale!r} must be one of the configured locales {self.locales}"
            )
        return self


_WEEK = r"^\d{4}-W\d{2}$"


class PanelQuery(BaseModel):
    # Mirrors /api/data's filters. Validated against the ERVISS profile so a config typo fails at load.
    model_config = ConfigDict(extra="forbid")  # a misspelt filter would otherwise be silently dropped
    indicator: str
    location: str | None = None
    survtype: str | None = None
    pathogen: str | None = None
    pathogentype: str | None = None
    pathogensubtype: str | None = None
    age: str | None = None
    week_from: str | None = Field(default=None, pattern=_WEEK)
    week_to: str | None = Field(default=None, pattern=_WEEK)

    @model_validator(mode="after")
    def _in_profile_vocab(self) -> "PanelQuery":
        if self.indicator not in ERVISS.indicators:
            raise ValueError(f"unknown indicator {self.indicator!r} for profile {ERVISS.name}")
        for dim, allowed in ERVISS.dimension_vocab.items():
            value = getattr(self, dim, None)
            if value is not None and value not in allowed:
                raise ValueError(f"{dim} {value!r} not allowed in profile {ERVISS.name}")
        return self


class Panel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["timeseries"]
    label_key: str | None = None
    query: PanelQuery
    series_by: str | None = None  # one line per value of this dimension

    @field_validator("series_by")
    @classmethod
    def _is_dimension(cls, v: str | None) -> str | None:
        if v is not None and v not in ERVISS.dimension_keys:
            raise ValueError(f"series_by {v!r} is not an {ERVISS.name} dimension")
        return v


# Server routes and SPA routes a page path must not shadow (a reload would hit the server route).
_RESERVED_PATHS = ("/login", "/logout", "/config", "/api", "/docs", "/redoc", "/openapi.json", "/healthz", "/assets")


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    path: str
    label_key: str | None = None  # i18n key; text lives in locale files, not config
    panels: list[Panel] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _routable(cls, path: str) -> str:
        # Literal paths only: ":" and "*" are react-router patterns; "/" is the redirect to the first page.
        if not path.startswith("/") or path == "/" or any(c in path for c in ":*"):
            raise ValueError(f"page path {path!r} must be a literal path starting with '/' (not '/' itself)")
        if any(path == r or path.startswith(r + "/") for r in _RESERVED_PATHS):
            raise ValueError(f"page path {path!r} collides with an app route")
        return path

    @model_validator(mode="after")
    def _unique_panel_ids(self) -> "Page":
        ids = [panel.id for panel in self.panels]
        if len(ids) != len(set(ids)):
            raise ValueError(f"page {self.id!r} has duplicate panel ids")
        return self


class Target(BaseModel):
    # A surveillance target (e.g. a pathogen). label_key -> locale files; id can derive one by convention.
    model_config = ConfigDict(extra="forbid")
    id: str
    label_key: str | None = None
    pages: list[Page] = Field(default_factory=list)


class DataConfig(BaseModel):
    dir: str


class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)
    targets: list[Target] = Field(default_factory=list)
    # Server-only: neither projection below references it, so it never reaches the client.
    data: DataConfig | None = None

    @model_validator(mode="after")
    def _unique_pages(self) -> "Config":
        # Two pages on one path would shadow each other as routes; ids key nav and React lists.
        pages = [page for target in self.targets for page in target.pages]
        for attr, label in (("path", "path"), ("id", "page id")):
            values = [getattr(page, attr) for page in pages]
            dupes = sorted({v for v in values if values.count(v) > 1})
            if dupes:
                raise ValueError(f"duplicate {label}(s) {', '.join(dupes)} across targets")
        return self

    def bootstrap_config(self) -> dict:
        # Whitelisted slice injected pre-login: only what the shell + login page need.
        return {
            "title": self.site.title,
            "branding": self.branding.model_dump(mode="json"),
            "defaultLocale": self.site.default_locale,
            "locales": self.site.locales,
        }

    def client_config(self) -> dict:
        # Full client view-model (authenticated). Superset of bootstrap; still excludes server-only
        # fields (public_paths, schema_version, future data-source config).
        return {
            **self.bootstrap_config(),
            "targets": [t.model_dump(mode="json") for t in self.targets],
        }


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
