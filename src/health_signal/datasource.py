import csv
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from .profile import ERVISS, FeedRow, Profile


class DataSource(Protocol):
    def query(self, *, pathogen=None, indicator=None, location=None,
              age=None, week_from=None, week_to=None) -> list[FeedRow]: ...


class EmptyDataSource:
    def query(self, **_kwargs) -> list[FeedRow]:
        return []


class FileDataSource:
    def __init__(self, data_dir: str | Path, profile: Profile = ERVISS) -> None:
        self._profile = profile
        self._rows = [r for path in sorted(Path(data_dir).glob("*.csv")) for r in self._load(path)]

    def _load(self, path: Path) -> list[FeedRow]:
        rows: list[FeedRow] = []
        with path.open(newline="", encoding="utf-8") as f:
            for i, rec in enumerate(csv.DictReader(f), start=2):  # line 1 is the header
                dims = {k: v for k in self._profile.dimension_keys if (v := (rec.get(k) or "").strip())}
                try:
                    row = FeedRow(
                        location=rec["location"], period=rec["period"],
                        indicator=rec["indicator"], value=rec["value"],
                        unit=rec["unit"], datasource=(rec.get("datasource") or None),
                        dimensions=dims,
                    )
                except (ValidationError, KeyError) as e:
                    # Name the file/line so a bad feed is debuggable, not a bare pydantic traceback.
                    raise ValueError(f"{path.name}:{i}: bad value ({e})") from e
                self._profile.validate(row)
                rows.append(row)
        return rows

    def query(self, *, pathogen=None, indicator=None, location=None,
              age=None, week_from=None, week_to=None) -> list[FeedRow]:
        out = []
        for r in self._rows:
            if location is not None and r.location != location:
                continue
            if indicator is not None and r.indicator != indicator:
                continue
            if pathogen is not None and r.dimensions.get("pathogen") != pathogen:
                continue
            if age is not None and r.dimensions.get("age") != age:
                continue
            if week_from is not None and r.period < week_from:
                continue
            if week_to is not None and r.period > week_to:
                continue
            out.append(r)
        return out
