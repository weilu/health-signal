from pydantic import BaseModel


class FeedRow(BaseModel):
    location: str
    period: str
    dimensions: dict[str, str]
    indicator: str
    value: float
    unit: str
    datasource: str | None = None


class Profile(BaseModel):
    name: str
    version: str
    dimension_keys: list[str]
    indicators: set[str]
    units: set[str]
    dimension_vocab: dict[str, set[str]]  # dimension name -> allowed values

    def validate(self, row: FeedRow) -> None:
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
)
