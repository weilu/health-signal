from pathlib import Path
from typing import Protocol

import pandas as pd

from .profile import ERVISS, FeedRow, Profile

_REQUIRED = pd.Index(["location", "period", "indicator", "value", "unit"])
# All cells as text, blanks kept as "": default NaN/type inference would turn a blank value into nan
# and mangle codes like "0-4". utf-8-sig drops Excel's BOM.
_READ_CSV = dict(dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8-sig")


class DataSource(Protocol):
    def query(self, *, location=None, indicator=None, week_from=None, week_to=None,
              **dimensions) -> list[FeedRow]: ...


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
        frames = [self._load(path) for path in sorted(data_dir.glob("*.csv"))]
        # concat leaves NaN where a file lacks an optional column.
        df = pd.concat(frames, ignore_index=True).fillna("") if frames else pd.DataFrame(columns=_REQUIRED)
        self._df = df.astype({"value": float})

    def _load(self, path: Path) -> pd.DataFrame:
        try:
            df = pd.read_csv(path, **_READ_CSV)
        except UnicodeDecodeError as e:
            # The bare decode error doesn't say which file; Greek Excel's plain "CSV" is cp1253.
            raise ValueError(f"{path.name}: not valid UTF-8 (byte {e.start}) — re-save it as 'CSV UTF-8'") from e
        except pd.errors.ParserError as e:
            # e.g. an unclosed quote, which would otherwise swallow the rows after it.
            raise ValueError(f"{path.name}: malformed CSV ({e})") from e
        except pd.errors.EmptyDataError as e:
            raise ValueError(f"{path.name}: empty file") from e
        df.columns = df.columns.str.strip()
        missing = _REQUIRED.difference(df.columns, sort=False)
        if not missing.empty:
            raise ValueError(f"{path.name}: missing column(s) {', '.join(missing)}")
        df = df.apply(lambda col: col.str.strip())
        if (violation := self._profile.first_violation(df)) is not None:
            label, message = violation
            # A data-row number: the reader skips blank lines, so a file line would be off.
            raise ValueError(f"{path.name} row {label + 1}: {message}")
        return df

    def query(self, *, location=None, indicator=None, week_from=None, week_to=None,
              **dimensions) -> list[FeedRow]:
        unknown = dimensions.keys() - set(self._profile.dimension_keys)
        if unknown:
            raise ValueError(f"unknown filter(s) {', '.join(sorted(unknown))} for profile {self._profile.name}")
        df = self._df
        mask = pd.Series(True, index=df.index)
        for column, wanted in (("location", location), ("indicator", indicator), *dimensions.items()):
            if wanted is not None:
                mask &= df[column].eq(wanted) if column in df.columns else False
        if week_from is not None:
            mask &= df["period"].ge(week_from)
        if week_to is not None:
            mask &= df["period"].le(week_to)
        return self._to_rows(df[mask])

    def _to_rows(self, df: pd.DataFrame) -> list[FeedRow]:
        dims = [k for k in self._profile.dimension_keys if k in df.columns]
        return [
            FeedRow(
                location=r["location"], period=r["period"], indicator=r["indicator"],
                value=r["value"], unit=r["unit"], datasource=r.get("datasource") or None,
                dimensions={k: r[k] for k in dims if r[k]},
            )
            for r in df.to_dict("records")
        ]
