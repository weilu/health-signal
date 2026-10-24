from datetime import date, timedelta
from pathlib import Path

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
