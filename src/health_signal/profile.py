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
    quality: str | None = None  # annotates the value (e.g. ODM beLOD), so it never splits a series


class Profile(BaseModel):
    name: str
    version: str
    dimension_keys: list[str]
    indicators: set[str]
    units: set[str]
    dimension_vocab: dict[str, set[str]]  # dimension name -> allowed values
    period_pattern: str  # granularity: week_range filters compare periods as strings, so format must be fixed
    required_dimensions: set[str] = set()
    qualities: set[str] = set()  # allowed `quality` values
    # indicator -> {dimension: value} it fixes, e.g. ODM measure fluA -> pathogen Influenza, so feeds join.
    indicator_implies: dict[str, dict[str, str]] = {}

    def first_violation(self, df: pd.DataFrame) -> tuple[int, str] | None:
        """(row label, message) of the first row breaking the profile, rule by rule; None if clean."""
        value = pd.to_numeric(df["value"], errors="coerce")
        rules = [
            (df["location"].eq(""), lambda r: "location is empty"),
            (df["period"].eq(""), lambda r: "period is empty"),
            (~np.isfinite(value), lambda r: f"value {r['value']!r} is not a finite number"),
            (~df["period"].str.fullmatch(self.period_pattern),
             lambda r: f"period {r['period']!r} does not match {self.period_pattern!r} for profile {self.name}"),
            # The pattern only fixes the shape; 2025-W53 fits it but doesn't exist and would fall off the axis.
            (df["period"].str.fullmatch(r"\d{4}-W\d{2}")
             & pd.to_datetime(df["period"] + "-1", format="%G-W%V-%u", errors="coerce").isna(),
             lambda r: f"period {r['period']!r} is not a week of its ISO year"),
            (~df["indicator"].isin(self.indicators),
             lambda r: f"unknown indicator {r['indicator']!r} for profile {self.name}"),
            (~df["unit"].isin(self.units), lambda r: f"unknown unit {r['unit']!r} for profile {self.name}"),
        ]
        # Dimensions without a vocab entry (e.g. pathogensubtype) are unconstrained.
        for dim, allowed in self.dimension_vocab.items():
            if dim in df.columns:
                rules.append((df[dim].ne("") & ~df[dim].isin(allowed),
                              lambda r, d=dim: f"value {r[d]!r} not allowed for dimension {d!r} in profile {self.name}"))
        for dim in sorted({d for implied in self.indicator_implies.values() for d in implied}):
            expected = df["indicator"].map({i: m[dim] for i, m in self.indicator_implies.items() if dim in m})
            actual = df[dim] if dim in df.columns else pd.Series("", index=df.index)
            rules.append((expected.notna() & actual.ne(expected),
                          lambda r, d=dim, e=expected: f"indicator {r['indicator']!r} implies {d} {e[r.name]!r}"))
        if "quality" in df.columns:
            rules.append((df["quality"].ne("") & ~df["quality"].isin(self.qualities),
                          lambda r: f"unknown quality {r['quality']!r} for profile {self.name}"))
        for dim in sorted(self.required_dimensions):
            absent = df[dim].eq("") if dim in df.columns else pd.Series(True, index=df.index)
            rules.append((absent, lambda r, d=dim: f"missing required dimension {d!r} for profile {self.name}"))
        for mask, message in rules:
            if mask.any():
                label = mask.idxmax()
                return label, message(df.loc[label])
        return None


# ECDC/WHO-Europe ERVISS respiratory profile (spec §6.2); vocabularies pinned to the published dataset
# EU-ECDC/Respiratory_viruses_weekly_data. Status/Trend are a separate assessment contract (§6.3).
ERVISS = Profile(
    name="erviss",
    version="2026-W40",
    dimension_keys=["survtype", "pathogen", "pathogentype", "pathogensubtype", "age"],
    indicators={
        "ILIconsultationrate", "ARIconsultationrate", "SARIrate", "tests", "detections",
        "positivity", "hospitaladmissions", "ICUadmissions", "ICUinpatients", "deaths",
    },
    # ERVISS reports ILI/ARI per 100k population, except per 100 consultations (Cyprus, Luxembourg,
    # Malta) and per 100k consultations (Finland) — per its README.
    units={"per_100k", "per_100_consultations", "per_100k_consultations", "count", "percent", "rate"},
    dimension_vocab={
        "survtype": {"primary care sentinel", "primary care syndromic", "non-sentinel",
                     "SARI syndromic", "SARI virological"},
        "pathogen": {"Influenza", "RSV", "SARS-CoV-2"},
        "pathogentype": {"Influenza", "Influenza A", "Influenza B", "Influenza untyped",
                         "RSV", "RSV untyped", "RSV-A", "RSV-B", "SARS-CoV-2"},
        # "NA" is a literal ERVISS value, not a missing cell (the loader keeps it as text).
        "pathogensubtype": {"A (unknown)", "A(H1)pdm09", "A(H3)", "B (unknown)", "B/Vic", "B/Yam",
                            "Influenza untyped", "NA", "RSV", "SARS-CoV-2", "total"},
        "age": {"0-4", "5-14", "15-64", "65+", "total", "unk"},
    },
    period_pattern=r"\d{4}-W\d{2}",
    required_dimensions={"survtype", "age"},  # spec §6.2: only the pathogen fields are nullable
)


# PHES-ODM v3.0.1 wastewater profile (spec §6.3): the respiratory subset of the ODM dictionary. The
# indicator is ODM's measure (gene target); pathogen keeps ERVISS spelling so feeds join.
_ODM_PATHOGEN = {
    "cov": "SARS-CoV-2", "covN1": "SARS-CoV-2", "covN2": "SARS-CoV-2", "covE": "SARS-CoV-2",
    "fluA": "Influenza", "fluB": "Influenza",
    "rsvMe": "RSV", "rsvAMe": "RSV", "rsvB": "RSV", "rsvAB": "RSV",
}
PHES_ODM = Profile(
    name="phes_odm",
    version="3.0.1",
    dimension_keys=["pathogen", "aggregation", "fraction"],
    indicators=set(_ODM_PATHOGEN) | {"ppmv"},  # ppmv: the PMMoV faecal-strength marker, no pathogen
    units={"gcL", "gcMl", "log10cpL", "gCGS", "gcPpmov", "gcDay", "gcDay100k"},
    dimension_vocab={
        "pathogen": {"Influenza", "RSV", "SARS-CoV-2"},
        "aggregation": {"me", "med", "gmn", "floMean", "pmmovNorm", "pmFloMean"},
        "fraction": {"liq", "sol", "mix", "mul"},
    },
    period_pattern=r"\d{4}-W\d{2}",
    required_dimensions={"aggregation"},
    qualities={"beLOD"},  # below LOD: the value is the producer's stand-in (0, LOD/2, …), not a measurement
    indicator_implies={measure: {"pathogen": p} for measure, p in _ODM_PATHOGEN.items()},
)

PROFILES = {p.name: p for p in (ERVISS, PHES_ODM)}
