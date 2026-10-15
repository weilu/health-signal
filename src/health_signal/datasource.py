import csv
from pathlib import Path
from typing import Protocol

from .profile import ERVISS, FeedRow, Profile

_REQUIRED = ("location", "period", "indicator", "value", "unit")


class DataSource(Protocol):
    def query(self, *, pathogen=None, indicator=None, location=None,
              age=None, week_from=None, week_to=None) -> list[FeedRow]: ...


class EmptyDataSource:
    def query(self, **_kwargs) -> list[FeedRow]:
        return []


class FileDataSource:
    def __init__(self, data_dir: str | Path, profile: Profile = ERVISS) -> None:
        data_dir = Path(data_dir)
        if not data_dir.is_dir():
            # A mistyped/missing dir would otherwise serve an empty feed that looks healthy.
            raise ValueError(f"data dir {str(data_dir)!r} is not a directory")
        self._profile = profile
        self._rows = [r for path in sorted(data_dir.glob("*.csv")) for r in self._load(path)]

    def _load(self, path: Path) -> list[FeedRow]:
        rows: list[FeedRow] = []
        try:
            # utf-8-sig: Excel's "CSV UTF-8" export prepends a BOM that would otherwise corrupt the first header.
            with path.open(newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                missing = [c for c in _REQUIRED if c not in (reader.fieldnames or [])]
                if missing:
                    raise ValueError(f"{path.name}: missing column(s) {', '.join(missing)}")
                for i, rec in enumerate(reader, start=2):  # line 1 is the header
                    cell = {k: (v or "").strip() for k, v in rec.items() if k is not None}
                    dims = {k: cell[k] for k in self._profile.dimension_keys if cell.get(k)}
                    try:
                        row = FeedRow(
                            location=cell["location"], period=cell["period"],
                            indicator=cell["indicator"], value=cell["value"],
                            unit=cell["unit"], datasource=cell.get("datasource") or None,
                            dimensions=dims,
                        )
                        self._profile.validate_row(row)
                    except (ValueError, KeyError) as e:  # ValidationError is a ValueError
                        # Name the file/line so a bad feed is debuggable, not a bare traceback.
                        raise ValueError(f"{path.name}:{i}: {e}") from e
                    rows.append(row)
        except UnicodeDecodeError as e:
            # The bare decode error doesn't say which file; Greek Excel's plain "CSV" is cp1253.
            raise ValueError(f"{path.name}: not valid UTF-8 (byte {e.start}) — re-save it as 'CSV UTF-8'") from e
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
