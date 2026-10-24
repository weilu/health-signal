import csv
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from ..assessments import AssessmentSource
from ..methods import METHODS
from ..profile import Profile
from .engine import SeriesResult
from .rules import SeasonState
from .series import Series

SETTINGS_FILE = "assessed_with.csv"
_TMP = ".assess-tmp"
_GROWTH = ("growth_rate", "growth_lower", "growth_upper")


class SettingsChanged(Exception):
    """The existing rows were computed under other settings: mixing them with new ones needs `--full`."""


def _key(location: str, indicator: str, method: str, dimensions: dict[str, str]) -> tuple:
    return location, indicator, method, tuple(sorted(dimensions.items()))


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    # repr round-trips a float exactly, so a rerun writes the bytes it read.
    return repr(float(value)) if isinstance(value, float | int) else str(value)


def write_validated(files: dict[Path, tuple[list[str], list[list]]], validate: Callable[[dict[Path, Path]], object]):
    """Write each table beside its destination, validate the drafts, then replace the served files, so a
    table the app would reject never replaces one it is serving."""
    drafts = {path: path.parent / _TMP / path.name for path in files}
    try:
        for path, (header, rows) in files.items():
            drafts[path].parent.mkdir(parents=True, exist_ok=True)
            with drafts[path].open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, lineterminator="\n")
                writer.writerow(header)
                writer.writerows([_text(v) for v in row] for row in rows)
        validate(drafts)
        for path, draft in drafts.items():
            os.replace(draft, path)
    finally:
        for parent in {d.parent for d in drafts.values()}:
            shutil.rmtree(parent, ignore_errors=True)


class FeedStore:
    """One feed's assessment tables as incremental state (spec §6.3.1)."""

    def __init__(self, directory: str | Path, profile: Profile, *, full: bool):
        self.directory, self.profile, self.full = Path(directory), profile, full
        self._rows: dict[tuple, dict[str, dict]] = {}
        self._spans: dict[tuple, list[list]] = {}   # key -> [[from, to, bounds], ...] in order
        self._settings: set[tuple[str, str, str]] | None = None
        if full or not self.directory.is_dir():
            return
        source = AssessmentSource(self.directory, profile)
        for r in source.assessments():
            row = {"period": r.period, "level": r.level, "provisional": r.provisional, "trend": r.trend,
                   **{g: getattr(r, g) for g in _GROWTH}, "phase": r.phase}
            self._rows.setdefault(_key(r.location, r.indicator, r.method, r.dimensions), {})[r.period] = row
        spans: dict[tuple, dict[tuple[str, str], dict[str, float]]] = {}
        for t in source.thresholds():
            key = _key(t.location, t.indicator, t.method, t.dimensions)
            spans.setdefault(key, {}).setdefault((t.from_, t.to), {})[t.level] = t.lower_bound
        for key, by_span in spans.items():
            levels = METHODS[key[2]].levels[1:]
            self._spans[key] = [[start, end, tuple(bounds[level] for level in levels)]
                                for (start, end), bounds in sorted(by_span.items())]
        if (self.directory / SETTINGS_FILE).is_file():
            with (self.directory / SETTINGS_FILE).open(encoding="utf-8") as f:
                self._settings = {(r["method"], r["setting"], r["value"]) for r in csv.DictReader(f)}

    def check_settings(self, settings: list[tuple[str, str, str]]) -> None:
        if self.full:
            return
        if self._settings is None:
            if self._rows:
                raise SettingsChanged(f"{self.directory} has rows but no {SETTINGS_FILE} (another producer's?); "
                                      f"run assess --full to recompute them")
            return
        changed = sorted({f"{m}.{s}" for m, s, _ in self._settings ^ set(settings)})
        if changed:
            raise SettingsChanged(f"{self.directory} was assessed with other settings ({', '.join(changed)}); "
                                  f"run assess --full to recompute it")

    def _series_key(self, series: Series, method: str) -> tuple:
        return _key(series.location, series.indicator, method, series.dimensions)

    def last_week(self, series: Series, method: str) -> str | None:
        rows = self._rows.get(self._series_key(series, method))
        return max(rows) if rows else None

    def resume(self, series: Series, method: str) -> SeasonState:
        key = self._series_key(series, method)
        last = self.last_week(series, method)
        if last is None:
            return SeasonState()
        if self._rows[key][last]["phase"] != "in_season":
            return SeasonState(last_period=last)
        # A season held over one week below its threshold must end at the next, as in a full rebuild.
        value = dict(zip(series.periods, series.values)).get(last)
        floor = next((b[0] for start, end, b in self._spans.get(key, []) if start <= last <= end), None)
        below = int(value is not None and floor is not None and value < floor)
        return SeasonState(True, below, last)

    def add(self, series: Series, method: str, result: SeriesResult) -> None:
        key = self._series_key(series, method)
        self._rows.setdefault(key, {}).update({row["period"]: row for row in result.rows})
        spans = self._spans.setdefault(key, [])
        for week, bounds in result.bounds:
            if spans and spans[-1][2] == tuple(bounds) and spans[-1][1] < week:
                spans[-1][1] = week
            else:
                spans.append([week, week, tuple(bounds)])

    def write(self, settings: list[tuple[str, str, str]]) -> None:
        dims = self.profile.dimension_keys
        assessment = []
        thresholds = []
        for key in sorted(self._rows):
            location, indicator, method, items = key
            d = dict(items)
            for period in sorted(self._rows[key]):
                row = self._rows[key][period]
                assessment.append([location, period, *(d.get(k) for k in dims), indicator, method, row["level"],
                                   row["provisional"], row["trend"], *(row[g] for g in _GROWTH), row["phase"]])
        for key in sorted(self._spans):
            location, indicator, method, items = key
            d = dict(items)
            for start, end, bounds in self._spans[key]:
                for level, bound in zip(METHODS[method].levels[1:], bounds):
                    thresholds.append([location, *(d.get(k) for k in dims), indicator, method, start, end, level, bound])
        files = {
            self.directory / "assessment.csv": (
                ["location", "period", *dims, "indicator", "method", "level", "provisional", "trend", *_GROWTH, "phase"],
                assessment),
            self.directory / "thresholds.csv": (
                ["location", *dims, "indicator", "method", "from", "to", "level", "lower_bound"], thresholds),
            self.directory / SETTINGS_FILE: (["method", "setting", "value"], sorted(settings)),
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        write_validated(files, lambda drafts: AssessmentSource(next(iter(drafts.values())).parent, self.profile))
