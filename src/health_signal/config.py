import re
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
    # App/OpenAPI name only; user-facing text comes from the locale files via i18n keys.
    title: str
    default_locale: str = "en"
    locales: list[str] = Field(default_factory=lambda: ["en"])
    # Path prefixes that bypass auth. Default empty = everything is locked (opt-in public).
    public_paths: list[str] = Field(default_factory=list)

    @field_validator("public_paths")
    @classmethod
    def _normalize_public_paths(cls, paths: list[str]) -> list[str]:
        # Only a literal "/" may match all: "", "//" or whitespace would also normalize to "/" and
        # silently make the whole site public.
        normalized = []
        for p in paths:
            if p != "/" and not p.strip("/").strip():
                raise ValueError(f'{p!r} is not a valid path prefix; use "/" (exactly) for the whole site')
            normalized.append("/" + p.strip("/"))
        return normalized

    @model_validator(mode="after")
    def _default_locale_is_offered(self) -> "SiteConfig":
        # fallbackLng is default_locale; one outside the configured locales renders raw keys.
        if self.default_locale not in self.locales:
            raise ValueError(
                f"default_locale {self.default_locale!r} must be one of the configured locales {self.locales}"
            )
        return self


class PanelQuery(BaseModel):
    # `dimensions` is a map so other profiles (e.g. wastewater) need no new fields. Location and dates
    # are dashboard filters, not panel settings.
    model_config = ConfigDict(extra="forbid")  # a misspelt key would otherwise be silently dropped
    indicator: str
    dimensions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _in_profile_vocab(self) -> "PanelQuery":
        if self.indicator not in ERVISS.indicators:
            raise ValueError(f"unknown indicator {self.indicator!r} for profile {ERVISS.name}")
        for dim, value in self.dimensions.items():
            if dim not in ERVISS.dimension_keys:
                raise ValueError(f"{dim!r} is not an {ERVISS.name} dimension")
            allowed = ERVISS.dimension_vocab.get(dim)
            if allowed is not None and value not in allowed:
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


# ASCII slug segments only: dots, "%", "\\", "//", "?", "#" and router patterns could resolve elsewhere, and
# ASCII never needs decoding, so the nav matcher sees the same pathname as <Routes>.
_PAGE_PATH = re.compile(r"(/[A-Za-z0-9_-]+)+")
# Paths a page must not shadow (a reload would hit the server route).
_RESERVED_PATHS = ("/login", "/logout", "/config", "/api", "/docs", "/redoc", "/openapi.json", "/healthz", "/assets")


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    path: str
    label_key: str | None = None  # i18n key, not text
    panels: list[Panel] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _routable(cls, path: str) -> str:
        # "/" redirects to the first page. Routes ignore a trailing slash, so it may not tell two paths apart.
        if not _PAGE_PATH.fullmatch(path):
            raise ValueError(f"page path {path!r} must be '/'-separated segments of letters, digits, '-' or '_'")
        if any(path.lower() == r or path.lower().startswith(r + "/") for r in _RESERVED_PATHS):
            raise ValueError(f"page path {path!r} collides with an app route")
        return path

    @model_validator(mode="after")
    def _unique_panel_ids(self) -> "Page":
        ids = [panel.id for panel in self.panels]
        if len(ids) != len(set(ids)):
            raise ValueError(f"page {self.id!r} has duplicate panel ids")
        return self


class Target(BaseModel):
    # A surveillance target, e.g. a pathogen.
    model_config = ConfigDict(extra="forbid")
    id: str
    label_key: str | None = None
    pages: list[Page] = Field(default_factory=list)


class LocationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str  # a feed `location`, e.g. "Greece" or "Attica"
    label_key: str | None = None


class LocationFilter(BaseModel):
    # The header's Region selector.
    model_config = ConfigDict(extra="forbid")
    default: str
    options: list[LocationOption] = Field(min_length=1)

    @model_validator(mode="after")
    def _default_offered_and_unique(self) -> "LocationFilter":
        values = [o.value for o in self.options]
        if len(values) != len(set(values)):
            raise ValueError("location options must be unique")
        if self.default not in values:
            raise ValueError(f"location default {self.default!r} is not one of the options {values}")
        return self


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: LocationFilter | None = None


class DataConfig(BaseModel):
    dir: str


class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)
    targets: list[Target] = Field(default_factory=list)
    filters: Filters = Field(default_factory=Filters)
    # Server-only: neither projection below references it, so it never reaches the client.
    data: DataConfig | None = None

    @model_validator(mode="after")
    def _unique_pages(self) -> "Config":
        # Duplicate paths shadow each other as routes (matched case-insensitively); ids key tabs and React lists.
        target_ids = [t.id for t in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("duplicate target ids")
        pages = [page for target in self.targets for page in target.pages]
        for key, label in ((lambda p: p.path.lower(), "path"), (lambda p: p.id, "page id")):
            values = [key(page) for page in pages]
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
        # Full view-model (authenticated); still excludes server-only fields.
        return {
            **self.bootstrap_config(),
            "targets": [t.model_dump(mode="json") for t in self.targets],
            "filters": self.filters.model_dump(mode="json"),
        }


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
