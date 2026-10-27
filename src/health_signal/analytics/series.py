from dataclasses import dataclass, field
from typing import Literal

from ..config import Config
from ..datasource import FileDataSource
from ..profile import FeedRow
from .rules import value_scale


@dataclass
class Series:
    feed: str
    pathogen: str
    location: str
    indicator: str
    dimensions: dict[str, str]
    unit: str
    periods: list[str]
    values: list[float]
    kind: Literal["count", "incidence"]
    exposure: list[float] = field(default_factory=list)
    per: float = 1.0
    scale: float = 1.0   # fit on values × scale, thresholds divided back (rules.value_scale)
    censored: list[bool] = field(default_factory=list)   # value is a stand-in (e.g. below LOD): fitted as a gap

    @property
    def key(self) -> tuple[str, str, tuple[tuple[str, str], ...]]:
        return self.location, self.indicator, tuple(sorted(self.dimensions.items()))


def _common_dimensions(rows: list[FeedRow]) -> dict[str, str]:
    # Every dimension the series' rows share, so assessment rows carry the profile's required ones (e.g. age)
    # even when the panel's query leaves them implicit.
    first = rows[0].dimensions
    return {k: v for k, v in first.items() if all(r.dimensions.get(k) == v for r in rows)}


def _by_location(rows: list[FeedRow]) -> dict[str, list[FeedRow]]:
    out: dict[str, list[FeedRow]] = {}
    for row in sorted(rows, key=lambda r: r.period):
        out.setdefault(row.location, []).append(row)
    return out


def assessed_series(config: Config, sources: dict[str, FileDataSource]):
    """The series panels show (spec §6.3.1): each single-series panel of an assessed feed, at every location
    a viewer can select (all in the data when there's no location filter). Returns the series, each panel
    reference's series by (pathogen, location, "<page>/<panel>"), and warnings for panels that can't be assessed."""
    assessed = {f.id for f in config.data.feeds if f.assessments}
    location_filter = config.filters.location
    selectable = {o.value for o in location_filter.options} if location_filter else None
    series: dict[tuple, Series] = {}
    refs: dict[tuple[str, str, str], Series] = {}
    warnings: list[str] = []
    for target in config.targets:
        for page in target.pages:
            for panel in page.panels:
                query = panel.query
                if query is None or panel.series_by is not None or query.feed not in assessed:
                    continue
                source = sources[query.feed]
                ref = f"{page.id}/{panel.id}"
                for location, rows in _by_location(source.query(indicator=query.indicator,
                                                                **query.dimensions)).items():
                    if selectable is not None and location not in selectable:
                        continue
                    if len({r.period for r in rows}) != len(rows):
                        warnings.append(f"{ref} at {location}: the query matches several rows per week; "
                                        f"pin more dimensions to assess it")
                        continue
                    found = _series(query.feed, target.id, location, rows, source, ref, warnings)
                    if found is not None:
                        refs[(target.id, location, ref)] = series.setdefault((found.feed, found.key), found)
    return list(series.values()), refs, warnings


def _series(feed: str, pathogen: str, location: str, rows: list[FeedRow], source: FileDataSource, ref: str,
            warnings: list[str]) -> Series | None:
    profile = source.profile
    first = rows[0]
    dims = _common_dimensions(rows)
    values = {r.period: r.value for r in rows}
    censored = {r.period for r in rows if r.quality in profile.censored_qualities}
    periods = list(values)
    if first.unit in profile.count_units:
        return Series(feed, pathogen, location, first.indicator, dims, first.unit, periods,
                      [values[p] for p in periods], "count", censored=[p in censored for p in periods])
    denominator = profile.denominator_for(first.indicator, first.unit)
    if denominator is None:
        # A rate or load with no denominator series: a constant exposure, which cancels in the growth model.
        return Series(feed, pathogen, location, first.indicator, dims, first.unit, periods,
                      [values[p] for p in periods], "incidence", [1.0] * len(periods), 1.0,
                      value_scale(list(values.values())), [p in censored for p in periods])
    denominators = source.query(location=location, indicator=denominator.indicator, **dims)
    if len({r.period for r in denominators}) != len(denominators):
        warnings.append(f"{ref} at {location}: several {denominator.indicator} rows per week match its rate; "
                        f"pin more dimensions to assess it")
        return None
    exposure = {r.period: r.value for r in denominators}
    periods = [p for p in periods if exposure.get(p, 0) > 0]   # a rate without its denominator isn't modelled
    if not periods:
        warnings.append(f"{ref} at {location}: no {denominator.indicator} to model its rate against")
        return None
    return Series(feed, pathogen, location, first.indicator, dims, first.unit, periods,
                  [values[p] for p in periods], "incidence", [exposure[p] for p in periods], denominator.per,
                  censored=[p in censored for p in periods])
