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
    # The fit's settings, here rather than with the fitting code so the methodology page shows the ones in use.
    parameters: dict[str, int | float | str] = {}

    @model_validator(mode="after")
    def _distinct(self) -> "Method":
        if len(set(self.levels)) != len(self.levels) or len(set(self.phases)) != len(self.phases):
            raise ValueError(f"method {self.name!r} repeats a level or phase")
        if not set(self.active_phases) <= set(self.phases):
            raise ValueError(f"method {self.name!r}: active phases must be among its phases")
        return self


# SSI's aedseo (spec §6.3): seasonal burden levels, growth-rate trend; one season a year or year-round waves.
# SSI's pairing: a community stream and an admissions stream each onset and overlap.
# The aedseo paper's validated settings (SSI; medRxiv 2025, doi:10.1101/2025.11.18.25340240): the window, the
# families, decay_factor and the 95% interval are aedseo's defaults; n_peak=3 and conf_levels=0.975 (Supplement S5)
# override its 6 and 0.95.
AEDSEO = Method(name="aedseo", levels=["very_low", "low", "medium", "high", "very_high"],
                phases=["in_season", "out_of_season", "in_wave", "between_waves"], trend=True,
                active_phases=["in_season", "in_wave"], stream_roles=["cases", "admissions"],
                parameters={"n_peak": 3, "conf_levels": 0.975, "decay_factor": 0.8, "burden_family": "lnorm",
                            "onset_family": "quasipoisson", "window_weeks": 5, "interval_percent": 95})

MAX_DIP = 1      # below-threshold weeks a season survives: a brief lull, not its end
MAX_MISSING = 8  # missing weeks a season survives: a reporting outage, not its end

METHODS = {m.name: m for m in (AEDSEO,)}
