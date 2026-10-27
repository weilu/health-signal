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


def implies_message(indicator: str, dim: str, value: str) -> str:
    return f"indicator {indicator!r} carries no {dim}" if value == "" else f"indicator {indicator!r} implies {dim} {value!r}"

class Denominator(BaseModel):
    indicator: str  # the series whose value is this rate's exposure, same key otherwise
    per: float      # the rate's scale: 100 for a percentage of tests


class Profile(BaseModel):
    name: str
    version: str
    dimension_keys: list[str]
    indicators: set[str]
    units: set[str]
    dimension_vocab: dict[str, set[str]]  # dimension name -> allowed values; pathogen comes from PATHOGENS
    period_pattern: str  # granularity: week_range filters compare periods as strings, so format must be fixed
    required_dimensions: set[str] = set()
    qualities: set[str] = set()  # allowed `quality` values
    # Qualities whose value is a stand-in, not a measurement (e.g. below the limit of detection): graded as the
    # value, but fitted as a gap, so a non-detect's 0 doesn't read as a -100% fall and back (spec §6.3.1).
    censored_qualities: set[str] = set()
    # indicator -> {dimension: value} it fixes, e.g. ODM measure fluA -> pathogen Influenza, so feeds join.
    # An empty value means the indicator carries no value for that dimension (PMMoV has no pathogen).
    indicator_implies: dict[str, dict[str, str]] = {}
    count_units: set[str] = set()  # graded on aedseo's cases path; every other unit is a rate or load
    # rate indicator -> its own denominator series, aedseo's exposure offset: growth of positivity must be
    # modelled against tests, not population (greece-public-health's AEDSEO_INPUTS note).
    denominators: dict[str, Denominator] = {}

    def vocab(self, dim: str) -> set[str] | None:
        # Every profile spells pathogens from the one registry, so feeds join on it.
        return set(PATHOGENS) if dim == "pathogen" else self.dimension_vocab.get(dim)

    def key_violation(self, df: pd.DataFrame, period_columns=("period",)) -> tuple[int, str] | None:
        """The series-key rules alone, for tables keyed like the feed (assessments, thresholds)."""
        rules = [(df["location"].eq(""), lambda r: "location is empty")]
        for col in period_columns:
            rules += [
                (df[col].eq(""), lambda r, c=col: f"{c} is empty"),
                (~df[col].str.fullmatch(self.period_pattern),
                 lambda r, c=col: f"{c} {r[c]!r} does not match {self.period_pattern!r} for profile {self.name}"),
                # The pattern only fixes the shape; 2025-W53 fits it but doesn't exist and would fall off the axis.
                (df[col].str.fullmatch(r"\d{4}-W\d{2}")
                 & pd.to_datetime(df[col] + "-1", format="%G-W%V-%u", errors="coerce").isna(),
                 lambda r, c=col: f"{c} {r[c]!r} is not a week of its ISO year"),
            ]
        rules.append((~df["indicator"].isin(self.indicators),
                      lambda r: f"unknown indicator {r['indicator']!r} for profile {self.name}"))
        # Dimensions without a vocab entry (e.g. pathogensubtype) are unconstrained.
        for dim in self.dimension_keys:
            if (allowed := self.vocab(dim)) is not None and dim in df.columns:
                rules.append((df[dim].ne("") & ~df[dim].isin(allowed),
                              lambda r, d=dim: f"value {r[d]!r} not allowed for dimension {d!r} in profile {self.name}"))
        for dim in sorted({d for implied in self.indicator_implies.values() for d in implied}):
            expected = df["indicator"].map({i: m[dim] for i, m in self.indicator_implies.items() if dim in m})
            actual = df[dim] if dim in df.columns else pd.Series("", index=df.index)
            rules.append((expected.notna() & actual.ne(expected),
                          lambda r, d=dim, e=expected: implies_message(r["indicator"], d, e[r.name])))
        for dim in sorted(self.required_dimensions):
            absent = df[dim].eq("") if dim in df.columns else pd.Series(True, index=df.index)
            rules.append((absent, lambda r, d=dim: f"missing required dimension {d!r} for profile {self.name}"))
        return first_match(df, rules)

    def first_violation(self, df: pd.DataFrame) -> tuple[int, str] | None:
        """(row label, message) of the first row breaking the profile, rule by rule; None if clean."""
        value = pd.to_numeric(df["value"], errors="coerce")
        rules = [
            (~np.isfinite(value), lambda r: f"value {r['value']!r} is not a finite number"),
            (~df["unit"].isin(self.units), lambda r: f"unknown unit {r['unit']!r} for profile {self.name}"),
        ]
        if "quality" in df.columns:
            rules.append((df["quality"].ne("") & ~df["quality"].isin(self.qualities),
                          lambda r: f"unknown quality {r['quality']!r} for profile {self.name}"))
        return first_match(df, rules) or self.key_violation(df)


def first_match(df: pd.DataFrame, rules) -> tuple[int, str] | None:
    """(row label, message) of the first row any rule flags, rules in order; None if none does."""
    for mask, message in rules:
        if mask.any():
            label = mask.idxmax()
            return label, message(df.loc[label])
    return None

# Canonical pathogen keys (spec §6.1): ERVISS's spellings, which its published data already uses; display
# names come from i18n. Profiles, the phase table and target ids all validate against this one set.
PATHOGENS = frozenset({"SARS-CoV-2", "Influenza", "RSV"})

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
        "pathogentype": {"Influenza", "Influenza A", "Influenza B", "Influenza untyped",
                         "RSV", "RSV untyped", "RSV-A", "RSV-B", "SARS-CoV-2"},
        # "NA" is a literal ERVISS value, not a missing cell (the loader keeps it as text).
        "pathogensubtype": {"A (unknown)", "A(H1)pdm09", "A(H3)", "B (unknown)", "B/Vic", "B/Yam",
                            "Influenza untyped", "NA", "RSV", "SARS-CoV-2", "total"},
        "age": {"0-4", "5-14", "15-64", "65+", "total", "unk"},
    },
    period_pattern=r"\d{4}-W\d{2}",
    required_dimensions={"survtype", "age"},  # spec §6.2: only the pathogen fields are nullable
    count_units={"count"},
    denominators={"positivity": Denominator(indicator="tests", per=100)},
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
        "aggregation": {"me", "med", "gmn", "floMean", "pmmovNorm", "pmFloMean"},
        "fraction": {"liq", "sol", "mix", "mul"},
    },
    period_pattern=r"\d{4}-W\d{2}",
    required_dimensions={"aggregation"},
    qualities={"beLOD"},  # below LOD: the value is the producer's stand-in (0, LOD/2, …), not a measurement
    censored_qualities={"beLOD"},
    indicator_implies={measure: {"pathogen": p} for measure, p in {**_ODM_PATHOGEN, "ppmv": ""}.items()},
)

PROFILES = {p.name: p for p in (ERVISS, PHES_ODM)}
