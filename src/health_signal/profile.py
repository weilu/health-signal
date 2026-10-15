import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class FeedRow(BaseModel):
    location: str = Field(min_length=1)
    period: str = Field(min_length=1)
    dimensions: dict[str, str]
    indicator: str
    value: float = Field(allow_inf_nan=False)  # nan would serialize to JSON null and read as a gap
    unit: str
    datasource: str | None = None


class Profile(BaseModel):
    name: str
    version: str
    dimension_keys: list[str]
    indicators: set[str]
    units: set[str]
    dimension_vocab: dict[str, set[str]]  # dimension name -> allowed values
    period_pattern: str  # granularity: week_range filters compare periods as strings, so format must be fixed
    required_dimensions: set[str] = set()
    indicator_values: dict[str, set[float]] = {}  # indicator -> allowed values (e.g. a level scale)

    def first_violation(self, df: pd.DataFrame) -> tuple[int, str] | None:
        """(row label, message) of the first row breaking the profile, rule by rule; None if clean."""
        value = pd.to_numeric(df["value"], errors="coerce")
        rules = [
            (df["location"].eq(""), lambda r: "location is empty"),
            (df["period"].eq(""), lambda r: "period is empty"),
            (~np.isfinite(value), lambda r: f"value {r['value']!r} is not a finite number"),
            (~df["period"].str.fullmatch(self.period_pattern),
             lambda r: f"period {r['period']!r} does not match {self.period_pattern!r} for profile {self.name}"),
            (~df["indicator"].isin(self.indicators),
             lambda r: f"unknown indicator {r['indicator']!r} for profile {self.name}"),
            (~df["unit"].isin(self.units), lambda r: f"unknown unit {r['unit']!r} for profile {self.name}"),
        ]
        # Dimensions without a vocab entry (e.g. pathogensubtype) are unconstrained.
        for dim, allowed in self.dimension_vocab.items():
            if dim in df.columns:
                rules.append((df[dim].ne("") & ~df[dim].isin(allowed),
                              lambda r, d=dim: f"value {r[d]!r} not allowed for dimension {d!r} in profile {self.name}"))
        for dim in sorted(self.required_dimensions):
            absent = df[dim].eq("") if dim in df.columns else pd.Series(True, index=df.index)
            rules.append((absent, lambda r, d=dim: f"missing required dimension {d!r} for profile {self.name}"))
        for ind, levels in self.indicator_values.items():
            rules.append((df["indicator"].eq(ind) & ~value.isin(levels),
                          lambda r, i=ind, lv=levels: f"{i} value {r['value']!r} not in {sorted(lv)} for profile {self.name}"))
        for mask, message in rules:
            if mask.any():
                label = mask.idxmax()
                return label, message(df.loc[label])
        return None


# ECDC/WHO-Europe ERVISS respiratory clinical profile (spec §6.2). Wastewater (§6.3) and categorical
# derived rows are deferred; numeric status_level (0-4) is kept so later stages can read it.
ERVISS = Profile(
    name="erviss",
    version="2024-snapshot",
    dimension_keys=["survtype", "pathogen", "pathogentype", "pathogensubtype", "age"],
    indicators={
        "ILIconsultationrate", "ARIconsultationrate", "SARIrate", "tests", "detections",
        "positivity", "hospitaladmissions", "ICUadmissions", "ICUinpatients", "deaths",
        "status_level",
    },
    units={"per_100k", "count", "percent", "rate", "level"},
    dimension_vocab={
        "survtype": {"primary care sentinel", "primary care syndromic", "non-sentinel",
                     "SARI syndromic", "SARI virological"},
        "pathogen": {"Influenza", "RSV", "SARS-CoV-2"},
        "age": {"0-4", "5-14", "15-64", "65+", "total", "unk"},
    },
    period_pattern=r"\d{4}-W\d{2}",
    required_dimensions={"survtype", "age"},  # spec §6.2: only the pathogen fields are nullable
    indicator_values={"status_level": {0, 1, 2, 3, 4}},
)
