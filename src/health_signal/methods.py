from pydantic import BaseModel, model_validator

class Method(BaseModel):
    # Levels are ordered lowest first: the UI colours by position, so any method's grades fit the tiles.
    name: str
    levels: list[str]
    phases: list[str]
    trend: bool
    trends: list[str] = []   # a method's own trend words: MEM says "not assessed" where aedseo says "inconclusive"
    active_phases: list[str] = []  # the phases that shade a chart; the rest mean "not now"
    stream_roles: list[str] = []  # roles of the series a derived pathogen-level phase uses (spec §6.3)
    # The fit's settings, here rather than with the fitting code so the methodology page shows the ones in use.
    parameters: dict[str, int | float | str | list[float]] = {}

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
                trends=["increasing", "stable", "decreasing", "inconclusive"],
                parameters={"n_peak": 3, "conf_levels": 0.975, "decay_factor": 0.8, "burden_family": "lnorm",
                            "onset_family": "quasipoisson", "window_weeks": 5, "interval_percent": 95})

MAX_DIP = 1      # below-threshold weeks a season survives: a brief lull, not its end
MAX_MISSING = 8  # missing weeks a season survives: a reporting outage, not its end

# The Moving Epidemic Method (Vega et al. 2013, 2015; R package mem): epidemic and intensity thresholds from past
# seasons, week-on-week trend during an epidemic. It grades each series on its own: no phases. Its parameters are
# mem's defaults (i.param, i.level.intensity, i.level.threshold).
MEM = Method(name="mem", levels=["baseline", "low", "medium", "high", "very_high"], phases=[], trend=True,
             trends=["increasing", "stable", "decreasing", "not_assessed"],
             parameters={"epidemic_param": 2.8, "intensity_levels": [0.4, 0.9, 0.975], "threshold_level": 0.95})

METHODS = {m.name: m for m in (AEDSEO, MEM)}
