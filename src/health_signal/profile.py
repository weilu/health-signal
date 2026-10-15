import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class FeedRow(BaseModel):
    # ERVISS's own column names (spec §6.1), so a published ERVISS file loads without renaming.
    survtype: str
    countryname: str = Field(min_length=1)
    region: str | None = None  # extension: sub-national rows (e.g. Attica); ERVISS itself is national
    yearweek: str = Field(min_length=1)
    pathogen: str | None = None
    pathogentype: str | None = None
    pathogensubtype: str | None = None
    indicator: str
    age: str
    value: float = Field(allow_inf_nan=False)  # nan would serialize to JSON null and read as a gap
    unit: str | None = None  # from the profile, not the feed; None where the source doesn't document it
    datasource: str | None = None


class Profile(BaseModel):
    name: str
    version: str
    required_columns: list[str]  # must be present in the file and non-blank in every row
    optional_columns: list[str]  # may be absent from a file or blank in a row
    indicators: set[str]
    vocab: dict[str, set[str]]  # column -> allowed values; columns without an entry are unconstrained
    period_pattern: str  # yearweek format: week_from/week_to filters compare it as a string
    indicator_units: dict[str, str]
    unit_overrides: dict[str, dict[str, str]] = {}  # countryname -> {indicator: unit}

    @property
    def columns(self) -> list[str]:
        return [*self.required_columns, *self.optional_columns]

    def first_violation(self, df: pd.DataFrame) -> tuple[int, str] | None:
        """(row label, message) of the first row breaking the profile, rule by rule; None if clean."""
        value = pd.to_numeric(df["value"], errors="coerce")
        rules = [(df[c].eq(""), lambda r, c=c: f"{c} is empty") for c in self.required_columns if c != "value"]
        rules += [
            (~np.isfinite(value), lambda r: f"value {r['value']!r} is not a finite number"),
            (~df["yearweek"].str.fullmatch(self.period_pattern),
             lambda r: f"yearweek {r['yearweek']!r} does not match {self.period_pattern!r} for profile {self.name}"),
            (~df["indicator"].isin(self.indicators),
             lambda r: f"unknown indicator {r['indicator']!r} for profile {self.name}"),
        ]
        for col, allowed in self.vocab.items():
            rules.append((df[col].ne("") & ~df[col].isin(allowed),
                          lambda r, c=col: f"{c} {r[c]!r} not allowed in profile {self.name}"))
        for mask, message in rules:
            if mask.any():
                label = mask.idxmax()
                return label, message(df.loc[label])
        return None

    def units(self, df: pd.DataFrame) -> pd.Series:
        unit = df["indicator"].map(self.indicator_units)
        for country, overrides in self.unit_overrides.items():
            here = df["countryname"].eq(country)
            unit = unit.mask(here, df["indicator"].map(overrides).fillna(unit))
        return unit


_PER_100 = "per_100_consultations"

# ECDC/WHO-Europe ERVISS respiratory profile (spec §6.2), pinned to the public dataset
# EU-ECDC/Respiratory_viruses_weekly_data. Variant/sequencing files and derived Status/Trend
# assessments are separate contracts (spec §6.3), not rows of this profile.
ERVISS = Profile(
    name="erviss",
    version="2026-W40",
    required_columns=["survtype", "countryname", "yearweek", "indicator", "age", "value"],
    optional_columns=["region", "pathogen", "pathogentype", "pathogensubtype", "datasource"],
    indicators={
        "ILIconsultationrate", "ARIconsultationrate", "SARIrate", "tests", "detections",
        "positivity", "hospitaladmissions", "ICUadmissions", "ICUinpatients", "deaths",
    },
    vocab={
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
    # ILI/ARI per the ERVISS README; positivity/counts confirmed from the data (0-100; integers).
    # SARIrate's unit is not documented by ERVISS, so it is left unset rather than guessed.
    indicator_units={
        "ILIconsultationrate": "per_100k_population", "ARIconsultationrate": "per_100k_population",
        "positivity": "percent",
        **{i: "count" for i in ("tests", "detections", "hospitaladmissions", "ICUadmissions",
                                "ICUinpatients", "deaths")},
    },
    unit_overrides={
        **{c: {"ILIconsultationrate": _PER_100, "ARIconsultationrate": _PER_100}
           for c in ("Cyprus", "Luxembourg", "Malta")},
        "Finland": {"ILIconsultationrate": "per_100k_consultations",
                    "ARIconsultationrate": "per_100k_consultations"},
    },
)
