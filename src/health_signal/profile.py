import re

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

    def validate(self, row: FeedRow) -> None:
        if not re.fullmatch(self.period_pattern, row.period):
            raise ValueError(f"period {row.period!r} does not match {self.period_pattern!r} for profile {self.name}")
        if row.indicator not in self.indicators:
            raise ValueError(f"unknown indicator {row.indicator!r} for profile {self.name}")
        if row.unit not in self.units:
            raise ValueError(f"unknown unit {row.unit!r} for profile {self.name}")
        for key, value in row.dimensions.items():
            allowed = self.dimension_vocab.get(key)
            # Dimensions without a vocab entry (e.g. pathogensubtype) are unconstrained.
            if allowed is not None and value not in allowed:
                raise ValueError(f"value {value!r} not allowed for dimension {key!r} in profile {self.name}")


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
)
