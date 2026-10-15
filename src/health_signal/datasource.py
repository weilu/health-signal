from pathlib import Path
from typing import Protocol

import pandas as pd

from .profile import ERVISS, FeedRow, Profile

# Read every cell as text and keep blanks as "": pandas' default NaN/type inference would silently
# turn a blank value into nan and ERVISS's literal "NA" subtype into a missing value.
# utf-8-sig drops Excel's BOM.
_READ_CSV = dict(dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8-sig")


class DataSource(Protocol):
    def query(self, *, countryname=None, region=None, pathogen=None, indicator=None,
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
        frames = [self._load(path) for path in sorted(data_dir.glob("*.csv"))]
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=profile.columns)
        df = df.astype({"value": float})
        df["unit"] = profile.units(df).fillna("")
        self._df = df

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
        missing = pd.Index(self._profile.required_columns).difference(df.columns, sort=False)
        if not missing.empty:
            raise ValueError(f"{path.name}: missing column(s) {', '.join(missing)}")
        # Optional columns a file lacks become blank; columns outside the profile are dropped.
        df = df.reindex(columns=self._profile.columns, fill_value="").apply(lambda col: col.str.strip())
        if (violation := self._profile.first_violation(df)) is not None:
            label, message = violation
            # A data-row number, not a file line: the reader skips blank lines and quoted cells can span lines.
            raise ValueError(f"{path.name} row {label + 1}: {message}")
        return df

    def query(self, *, countryname=None, region=None, pathogen=None, indicator=None,
              age=None, week_from=None, week_to=None) -> list[FeedRow]:
        df = self._df
        mask = pd.Series(True, index=df.index)
        for column, wanted in (("countryname", countryname), ("region", region), ("pathogen", pathogen),
                               ("indicator", indicator), ("age", age)):
            if wanted is not None:
                mask &= df[column].eq(wanted)
        if week_from is not None:
            mask &= df["yearweek"].ge(week_from)
        if week_to is not None:
            mask &= df["yearweek"].le(week_to)
        # Blank cells are absent values in the API (null), not empty strings.
        return [FeedRow(**{k: (v if k == "value" else v or None) for k, v in r.items()})
                for r in df[mask].to_dict("records")]
