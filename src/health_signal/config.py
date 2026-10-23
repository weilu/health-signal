import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, computed_field, field_validator, model_validator

from .methods import METHODS
from .profile import PATHOGENS, PROFILES, implies_message


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
    feed: str  # no default: every panel says which feed it reads
    indicator: str
    dimensions: dict[str, str] = Field(default_factory=dict)


class Panel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    type: Literal["timeseries", "phase", "summary"] = "timeseries"  # phase and summary build the Overview
    query: PanelQuery | None = None
    series_by: str | None = None  # one line per value of this dimension

    @model_validator(mode="after")
    def _fields_fit_the_kind(self) -> "Panel":
        # phase and summary work from their target and the location filter, not a query.
        if self.type == "timeseries" and self.query is None:
            raise ValueError(f"panel {self.id!r}: a timeseries panel needs a query")
        if self.type != "timeseries" and (self.query is not None or self.series_by is not None):
            raise ValueError(f"panel {self.id!r}: a {self.type} panel takes no query or series_by")
        return self

    @computed_field
    @property
    def label_key(self) -> str:  # i18n key, by convention (spec §9); not settable in config
        return f"panels.{self.id}"


_PAGE_ID = re.compile(r"[a-z0-9_-]+")  # a URL segment as-is: no encoding, no case folding


def page_path(target_id: str, page_id: str) -> str:
    # Derived, never configured (spec §6.1): unique because target ids and page ids are.
    return f"/{target_id.lower()}/{page_id}"


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    panels: list[Panel] = Field(default_factory=list)

    @computed_field
    @property
    def label_key(self) -> str:
        return f"pages.{self.id}"

    @field_validator("id")
    @classmethod
    def _url_safe(cls, page_id: str) -> str:
        if not _PAGE_ID.fullmatch(page_id):
            raise ValueError(f"page id {page_id!r} must be lower-case letters, digits, '-' or '_'")
        return page_id

    @model_validator(mode="after")
    def _unique_panel_ids(self) -> "Page":
        ids = [panel.id for panel in self.panels]
        if len(ids) != len(set(ids)):
            raise ValueError(f"page {self.id!r} has duplicate panel ids")
        return self


class Target(BaseModel):
    # A surveillance subject: its id is a pathogen registry key, so tabs, phases and tiles share one key.
    model_config = ConfigDict(extra="forbid")
    id: str
    pages: list[Page] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _is_pathogen(cls, target_id: str) -> str:
        if target_id not in PATHOGENS:
            raise ValueError(f"target id {target_id!r} is not in the pathogen registry {sorted(PATHOGENS)}")
        return target_id

    @computed_field
    @property
    def label_key(self) -> str:
        return f"targets.{self.id}"

    @model_validator(mode="after")
    def _unique_page_ids(self) -> "Target":
        # An id names a page within its target's tab row, so it may repeat across targets.
        ids = [page.id for page in self.pages]
        if len(ids) != len(set(ids)):
            raise ValueError(f"target {self.id!r} has duplicate page ids")
        return self


class LocationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(min_length=1)  # a feed `location`, e.g. "Greece"; "" would mean no filter (all regions)
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


class DateRangeFilter(BaseModel):
    # The header's Date range control; always on, since every feed is weekly.
    model_config = ConfigDict(extra="forbid")
    default_weeks: PositiveInt | Literal["all"] = 52  # counted back from the feed's latest week
    # Where each yearly preset begins, e.g. 21 for a W21-W20 respiratory year. W53 is excluded because
    # most years don't have one.
    year_start_week: int = Field(default=1, ge=1, le=52)


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: LocationFilter | None = None
    date_range: DateRangeFilter = Field(default_factory=DateRangeFilter)


class FeedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)  # the client drops empty query params, so "" could never be requested
    profile: str
    dir: str
    assessments: str | None = None  # Status/Trend tables for this feed's series (spec §6.3)

    @field_validator("profile")
    @classmethod
    def _known_profile(cls, name: str) -> str:
        if name not in PROFILES:
            raise ValueError(f"unknown profile {name!r}; one of {sorted(PROFILES)}")
        return name


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feeds: list[FeedConfig] = Field(min_length=1)
    phases: str | None = None  # the pathogen-level phase CSV, one per dashboard (spec §6.3)
    phase_streams: str | None = None  # the series behind each computed phase (spec §6.3)

    @model_validator(mode="after")
    def _unique_ids(self) -> "DataConfig":
        ids = [f.id for f in self.feeds]
        if len(ids) != len(set(ids)):
            raise ValueError("feed ids must be unique")
        return self


def _panel_problem(panel: Panel, profiles: dict) -> str | None:
    q = panel.query
    profile = profiles.get(q.feed)
    if profile is None:
        return f"feed {q.feed!r} is not configured under data.feeds"
    if q.indicator not in profile.indicators:
        return f"unknown indicator {q.indicator!r} for feed {q.feed!r} ({profile.name})"
    for dim, value in q.dimensions.items():
        if dim not in profile.dimension_keys:
            return f"{dim!r} is not a dimension of feed {q.feed!r} ({profile.name})"
        allowed = profile.vocab(dim)
        if allowed is not None and value not in allowed:
            return f"{dim} {value!r} not allowed for feed {q.feed!r} ({profile.name})"
        # e.g. fluA with pathogen RSV: each value is valid, but no row can carry both, so the panel would
        # read as "no data" rather than as a config mistake.
        implied = profile.indicator_implies.get(q.indicator, {}).get(dim)
        if implied is not None and value != implied:
            return f"{implies_message(q.indicator, dim, implied)}, not {value!r}"
    if panel.series_by is not None and panel.series_by not in profile.dimension_keys:
        return f"series_by {panel.series_by!r} is not a dimension of feed {q.feed!r} ({profile.name})"
    return None


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
        # Target ids key tabs and derived paths.
        target_ids = [t.id for t in self.targets]
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("duplicate target ids")
        return self

    @model_validator(mode="after")
    def _panels_match_their_feeds(self) -> "Config":
        # Checked here, not on the panel: only the config knows which profile a feed id means.
        profiles = {f.id: PROFILES[f.profile] for f in self.data.feeds} if self.data else {}
        for target in self.targets:
            for page in target.pages:
                for panel in page.panels:
                    if panel.query is None:
                        continue
                    if (problem := _panel_problem(panel, profiles)) is not None:
                        raise ValueError(f"panel {panel.id!r} on page {page.id!r}: {problem}")
                    # Explicit, or implied by the indicator (wastewater cov is always SARS-CoV-2).
                    implied = profiles[panel.query.feed].indicator_implies.get(panel.query.indicator, {})
                    pathogen = panel.query.dimensions.get("pathogen") or implied.get("pathogen") or None
                    if pathogen is not None and pathogen != target.id:
                        raise ValueError(f"panel {panel.id!r} on page {page.id!r} queries pathogen {pathogen!r} "
                                         f"but sits under target {target.id!r}")
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
            "targets": [
                {**t.model_dump(mode="json"),
                 "pages": [{**p.model_dump(mode="json"), "path": page_path(t.id, p.id)} for p in t.pages]}
                for t in self.targets
            ],
            "filters": self.filters.model_dump(mode="json"),
            "methods": {name: m.model_dump(mode="json", exclude={"name"}) for name, m in METHODS.items()},
        }


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
