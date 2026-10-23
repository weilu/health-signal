from pydantic import BaseModel, model_validator

# Trend vocabulary shared by every method that has one (spec §6.3).
TRENDS = frozenset({"increasing", "stable", "decreasing", "inconclusive"})


class Method(BaseModel):
    # Levels are ordered lowest first: the UI colours by position, so any method's grades fit the tiles.
    name: str
    levels: list[str]
    phases: list[str]
    trend: bool
    active_phases: list[str] = []  # the phases that shade a chart; the rest mean "not now"
    stream_roles: list[str] = []  # roles of the series a derived pathogen-level phase uses (spec §6.3)

    @model_validator(mode="after")
    def _distinct(self) -> "Method":
        if len(set(self.levels)) != len(self.levels) or len(set(self.phases)) != len(self.phases):
            raise ValueError(f"method {self.name!r} repeats a level or phase")
        if not set(self.active_phases) <= set(self.phases):
            raise ValueError(f"method {self.name!r}: active phases must be among its phases")
        return self


# SSI's aedseo (spec §6.3): seasonal burden levels, growth-rate trend, season or wave phase.
# SSI's pairing: a community stream and an admissions stream each onset and overlap.
AEDSEO = Method(name="aedseo", levels=["very_low", "low", "medium", "high", "very_high"],
                phases=["in_season", "in_wave", "out_of_season"], trend=True,
                active_phases=["in_season", "in_wave"], stream_roles=["cases", "admissions"])

METHODS = {m.name: m for m in (AEDSEO,)}
