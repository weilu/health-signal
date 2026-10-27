from pathlib import Path
from urllib.parse import parse_qsl

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .datasource import PROVENANCE, drop_copies_reject_conflicts, filter_rows, raise_row, read_table, with_provenance
from .methods import METHODS, TRENDS
from .profile import PATHOGENS, Profile, first_match, implies_message


class AssessmentRow(BaseModel):
    location: str
    period: str
    dimensions: dict[str, str]
    indicator: str
    method: str
    level: str | None
    provisional: bool
    trend: str | None
    growth_rate: float | None
    growth_lower: float | None
    growth_upper: float | None
    phase: str | None


class ThresholdRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)
    location: str
    dimensions: dict[str, str]
    indicator: str
    method: str
    from_: str = Field(alias="from")  # `from` is a Python keyword
    to: str
    level: str
    lower_bound: float


class PhaseRow(BaseModel):
    location: str
    pathogen: str
    period: str
    method: str
    phase: str


_GROWTH = ["growth_rate", "growth_lower", "growth_upper"]
_ASSESSMENT_COLUMNS = ["location", "period", "indicator", "method", "level", "provisional", "trend", *_GROWTH, "phase"]
_THRESHOLD_COLUMNS = ["location", "indicator", "method", "from", "to", "level", "lower_bound"]
_PHASE_COLUMNS = ["location", "pathogen", "period", "method", "phase"]


def _outside_method(df: pd.DataFrame, column: str, vocabulary: str) -> pd.Series:
    # Vocabularies are per method (spec §6.3): `alert` is fine for an IDSR method, not for aedseo.
    allowed = df["method"].map(lambda method: getattr(METHODS[method], vocabulary) if method in METHODS else [])
    return df[column].ne("") & ~pd.Series([value in values for value, values in zip(df[column], allowed)],
                                          index=df.index, dtype=bool)


def _load(directory: Path, name: str, required: list[str], check) -> pd.DataFrame:
    path = directory / name
    if not path.is_file():
        return pd.DataFrame(columns=[*required, *PROVENANCE])
    df = read_table(path, required)
    raise_row(path, check(df))
    return with_provenance(df, path)


def _dims(profile: Profile, df: pd.DataFrame) -> list[str]:
    return [dim for dim in profile.dimension_keys if dim in df.columns]


class AssessmentSource:
    def __init__(self, directory: str | Path, profile: Profile) -> None:
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError(f"assessments dir {str(directory)!r} is not a directory")
        self.profile = profile
        assessments = _load(directory, "assessment.csv", _ASSESSMENT_COLUMNS, self._assessment_violation)
        # Compared as numbers, as feeds are: 0.2 and 0.20 are one reading, not a conflict.
        assessments[_GROWTH] = assessments[_GROWTH].replace("", np.nan).astype(float)
        key = ["location", "period", "indicator", "method", *_dims(profile, assessments)]
        self._assessments = drop_copies_reject_conflicts(assessments, key).drop(columns=PROVENANCE)
        thresholds = _load(directory, "thresholds.csv", _THRESHOLD_COLUMNS, self._threshold_violation)
        thresholds["lower_bound"] = thresholds["lower_bound"].astype(float)
        series = ["location", "indicator", "method", *_dims(profile, thresholds)]
        thresholds = drop_copies_reject_conflicts(thresholds, [*series, "from", "level"])
        _check_spans(thresholds, series)
        self._thresholds = thresholds.drop(columns=PROVENANCE)

    def _assessment_violation(self, df: pd.DataFrame):
        # astype: an empty column stays object dtype after to_numeric, and isfinite rejects object.
        growth = df[_GROWTH].apply(pd.to_numeric, errors="coerce").astype(float)
        blank = df[_GROWTH].eq("")
        no_trend = df["method"].map(lambda method: method in METHODS and not METHODS[method].trend).astype(bool)
        in_interval = (np.isfinite(growth).all(axis=1) & (growth["growth_lower"] <= growth["growth_rate"])
                       & (growth["growth_rate"] <= growth["growth_upper"]))
        rules = [
            (~df["method"].isin(METHODS), lambda r: f"unknown method {r['method']!r}"),
            (_outside_method(df, "level", "levels"), lambda r: f"level {r['level']!r} is not a {r['method']} level"),
            (_outside_method(df, "phase", "phases"), lambda r: f"phase {r['phase']!r} is not a {r['method']} phase"),
            (~df["provisional"].isin({"true", "false"}),
             lambda r: f"provisional {r['provisional']!r} is not true or false"),
            (df["trend"].ne("") & ~df["trend"].isin(TRENDS), lambda r: f"unknown trend {r['trend']!r}"),
            (df["trend"].ne("") & no_trend, lambda r: f"method {r['method']} has no trend"),
            (blank.any(axis=1) & ~blank.all(axis=1),
             lambda r: "growth_rate, growth_lower and growth_upper must be all set or all blank"),
            (~blank.any(axis=1) & ~in_interval,
             lambda r: f"growth {r['growth_rate']} is not a finite rate within [{r['growth_lower']}, {r['growth_upper']}]"),
        ]
        return first_match(df, rules) or self.profile.key_violation(df)

    def _threshold_violation(self, df: pd.DataFrame):
        bound = pd.to_numeric(df["lower_bound"], errors="coerce").astype(float)
        rules = [
            (~df["method"].isin(METHODS), lambda r: f"unknown method {r['method']!r}"),
            (df["level"].eq("") | _outside_method(df, "level", "levels"),
             lambda r: f"level {r['level']!r} is not a {r['method']} level"),
            (~np.isfinite(bound), lambda r: f"lower_bound {r['lower_bound']!r} is not a finite number"),
            (df["from"] > df["to"], lambda r: f"from {r['from']} is after to {r['to']}"),
        ]
        return first_match(df, rules) or self.profile.key_violation(df, period_columns=("from", "to"))

    def assessments(self, *, location=None, indicator=None, week_from=None, week_to=None, dimensions=None,
                    method=None) -> list[AssessmentRow]:
        df = filter_rows(self._assessments, location=location, indicator=indicator, week_from=week_from, week_to=week_to,
                         dimensions={**(dimensions or {}), "method": method})
        dims = _dims(self.profile, df)
        return [AssessmentRow(
            location=r["location"], period=r["period"], indicator=r["indicator"], method=r["method"],
            dimensions={dim: r[dim] for dim in dims if r[dim]}, level=r["level"] or None,
            provisional=r["provisional"] == "true", trend=r["trend"] or None, phase=r["phase"] or None,
            **{field: None if pd.isna(r[field]) else r[field] for field in _GROWTH},
        ) for r in df.to_dict("records")]

    def thresholds(self, *, location=None, indicator=None, week_from=None, week_to=None, dimensions=None,
                   method=None) -> list[ThresholdRow]:
        df = filter_rows(self._thresholds, location=location, indicator=indicator,
                         dimensions={**(dimensions or {}), "method": method})
        # A span overlapping the range counts, so a range starting mid-season still gets its season's bands.
        if week_from is not None:
            df = df[df["to"] >= week_from]
        if week_to is not None:
            df = df[df["from"] <= week_to]
        dims = _dims(self.profile, df)
        return [ThresholdRow(
            location=r["location"], indicator=r["indicator"], method=r["method"], from_=r["from"], to=r["to"],
            level=r["level"], lower_bound=r["lower_bound"], dimensions={dim: r[dim] for dim in dims if r[dim]},
        ) for r in df.to_dict("records")]


def _check_spans(thresholds: pd.DataFrame, series: list[str]) -> None:
    for _, group in thresholds.groupby(series, sort=False):
        spans = group.drop_duplicates(["from", "to"]).sort_values("from")
        for (_, earlier), (_, later) in zip(spans.iterrows(), spans.iloc[1:].iterrows()):
            if later["from"] <= earlier["to"]:
                raise ValueError(f"{later['_file']} row {later['_row']}: span {later['from']}..{later['to']} overlaps "
                                 f"{earlier['from']}..{earlier['to']}")
        for _, span in group.groupby(["from", "to"], sort=False):
            order = METHODS[span["method"].iat[0]].levels
            ranked = span.assign(_rank=span["level"].map(order.index)).sort_values("_rank")
            bounds = ranked["lower_bound"].tolist()
            for (_, row), lower, upper in zip(ranked.iloc[1:].iterrows(), bounds, bounds[1:]):
                if upper <= lower:
                    raise ValueError(f"{row['_file']} row {row['_row']}: lower bounds must rise in level order")


class PhaseSource:
    def __init__(self, path: str | Path) -> None:
        path = Path(path)
        if not path.is_file():
            # One file per dashboard, so a configured path that doesn't exist is a typo, not "no phases".
            raise ValueError(f"phases file {str(path)!r} does not exist")
        df = _load(path.parent, path.name, _PHASE_COLUMNS, self._violation)
        key = ["location", "pathogen", "period", "method"]
        self._phases = drop_copies_reject_conflicts(df, key).drop(columns=PROVENANCE)

    @staticmethod
    def _violation(df: pd.DataFrame):
        week = pd.to_datetime(df["period"] + "-1", format="%G-W%V-%u", errors="coerce")
        rules = [
            (df["location"].eq(""), lambda r: "location is empty"),
            (~df["pathogen"].isin(PATHOGENS), lambda r: f"pathogen {r['pathogen']!r} is not in the pathogen registry"),
            (~df["period"].str.fullmatch(r"\d{4}-W\d{2}") | week.isna(),
             lambda r: f"period {r['period']!r} is not an ISO week"),
            (~df["method"].isin(METHODS), lambda r: f"unknown method {r['method']!r}"),
            (df["phase"].eq("") | _outside_method(df, "phase", "phases"),
             lambda r: f"phase {r['phase']!r} is not a {r['method']} phase"),
        ]
        return first_match(df, rules)

    def phases(self, *, location=None, pathogen=None, method=None, week_from=None, week_to=None) -> list[PhaseRow]:
        df = filter_rows(self._phases, location=location, week_from=week_from, week_to=week_to,
                         dimensions={"pathogen": pathogen, "method": method})
        return [PhaseRow(**{column: r[column] for column in _PHASE_COLUMNS}) for r in df.to_dict("records")]


class PhaseStreamRow(BaseModel):
    location: str
    pathogen: str
    method: str
    role: str
    feed: str
    series: dict[str, str]  # /api/data parameters, so the overview fetches the stream directly


_STREAM_COLUMNS = ["location", "pathogen", "method", "role", "feed", "series"]


class PhaseStreamSource:
    def __init__(self, path: str | Path, feeds: dict[str, Profile]) -> None:
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"phase streams file {str(path)!r} does not exist")
        self._feeds = feeds
        df = _load(path.parent, path.name, _STREAM_COLUMNS, self._violation)
        key = ["location", "pathogen", "method", "role"]
        self._streams = drop_copies_reject_conflicts(df, key).drop(columns=PROVENANCE)

    def _series_problem(self, feed: str, series: str, pathogen: str) -> str | None:
        profile = self._feeds.get(feed)
        if profile is None:
            return f"feed {feed!r} is not configured"
        params = dict(parse_qsl(series))
        if params.get("indicator") not in profile.indicators:
            return f"indicator {params.get('indicator')!r} is not in feed {feed!r} ({profile.name})"
        for dim, value in params.items():
            if dim == "indicator":
                continue
            if dim not in profile.dimension_keys:
                return f"{dim!r} is not a dimension of feed {feed!r} ({profile.name})"
            allowed = profile.vocab(dim)
            if allowed is not None and value not in allowed:
                return f"{dim} {value!r} not allowed for feed {feed!r} ({profile.name})"
        # Checked apart from an explicit pathogen, which would otherwise let indicator=cov&pathogen=Influenza
        # pass as influenza evidence.
        implied = profile.indicator_implies.get(params["indicator"], {}).get("pathogen")
        if implied is not None and implied != pathogen:
            return f"{implies_message(params['indicator'], 'pathogen', implied)}, not {pathogen!r}"
        if params.get("pathogen", pathogen) != pathogen:
            return f"series names pathogen {params['pathogen']!r}, not {pathogen!r}"
        if implied is None and "pathogen" not in params and params["indicator"] in profile.pathogen_specific:
            return f"indicator {params['indicator']!r} is pathogen-specific; the series must name its pathogen"
        # parse_qsl drops blank values, so "aggregation=" reads as left out, as it should.
        if missing := sorted(d for d in profile.required_dimensions if d not in params):
            return f"series lacks {profile.name}'s required dimension {missing[0]!r}, so it would match several series"
        return None

    def _violation(self, df: pd.DataFrame):
        roles = df["method"].map(lambda method: METHODS[method].stream_roles if method in METHODS else [])
        series = pd.Series([self._series_problem(feed, query, pathogen)
                            for feed, query, pathogen in zip(df["feed"], df["series"], df["pathogen"])],
                           index=df.index, dtype=object)
        rules = [
            (df["location"].eq(""), lambda r: "location is empty"),
            (~df["pathogen"].isin(PATHOGENS), lambda r: f"pathogen {r['pathogen']!r} is not in the pathogen registry"),
            (~df["method"].isin(METHODS), lambda r: f"unknown method {r['method']!r}"),
            (pd.Series([role not in allowed for role, allowed in zip(df["role"], roles)], index=df.index, dtype=bool),
             lambda r: f"role {r['role']!r} is not a {r['method']} stream role"),
            (series.notna(), lambda r: series[r.name]),
        ]
        return first_match(df, rules)

    def _canonical(self, feed: str, series: dict[str, str]) -> dict[str, str]:
        # The same form as the client's panel queries, so the summary can match a stream to its panel.
        dims = self._feeds[feed].canonical(series["indicator"], {k: v for k, v in series.items() if k != "indicator"})
        return {"indicator": series["indicator"], **dims}

    def streams(self, *, location=None, pathogen=None, method=None) -> list[PhaseStreamRow]:
        df = filter_rows(self._streams, location=location, dimensions={"pathogen": pathogen, "method": method})
        return [PhaseStreamRow(**{column: r[column] for column in _STREAM_COLUMNS if column != "series"},
                               series=self._canonical(r["feed"], dict(parse_qsl(r["series"]))))
                for r in df.to_dict("records")]
