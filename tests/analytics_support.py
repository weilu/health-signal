import math
from datetime import date, timedelta
from pathlib import Path

from health_signal.analytics.backend import FitError, FitInput, WeekFit

ERVISS_HEADER = "location,period,survtype,pathogen,pathogentype,pathogensubtype,age,indicator,value,unit\n"


def weeks(start_year: int, n: int) -> list[str]:
    first = date.fromisocalendar(start_year, 1, 1)
    out = []
    for i in range(n):
        year, week, _ = (first + timedelta(weeks=i)).isocalendar()
        out.append(f"{year}-W{week:02d}")
    return out


def erviss_rows(location, indicator, unit, values, *, survtype="primary care sentinel", pathogen="", age="total",
                periods=None) -> str:
    periods = periods or weeks(2021, len(values))
    return "".join(f"{location},{p},{survtype},{pathogen},,,{age},{indicator},{v},{unit}\n"
                   for p, v in zip(periods, values) if v is not None)


def write_feed(directory: Path, body: str, header: str = ERVISS_HEADER) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "feed.csv").write_text(header + body, encoding="utf-8")
    return directory


class FakeBackend:
    """Deterministic stand-in for aedseo: fixed bands, growth from the last two values, an onset alarm when
    rising above the floor, in a wave whenever above it. Fails on fewer than 3 weeks, like a thin series."""
    version = "fake-1"
    thresholds = (10.0, 20.0, 40.0, 80.0)

    def fit(self, data: FitInput) -> WeekFit:
        if len(data.values) < 3:
            raise FitError("too few weeks")
        last, prev = data.values[-1], data.values[-2]
        r = math.log(last / prev) if last > 0 and prev > 0 else math.nan
        return WeekFit(thresholds=self.thresholds, growth=(r, r - 0.1, r + 0.1),
                       alarm=last >= self.thresholds[0] and last > prev,
                       in_wave=(last >= self.thresholds[0]) if data.waves else None)


class FlakyBackend(FakeBackend):
    """Fails on the 5th week only: a mid-season week aedseo can't fit."""

    def fit(self, data: FitInput) -> WeekFit:
        if len(data.values) == 5:
            raise FitError("this week only")
        return super().fit(data)


class NeverFitsBackend(FakeBackend):
    def fit(self, data: FitInput) -> WeekFit:
        raise FitError("never")


class BandsBackend(FakeBackend):
    """FakeBackend with chosen bands, e.g. partly NaN or not rising."""

    def __init__(self, thresholds):
        self.thresholds = thresholds
