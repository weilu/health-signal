from collections.abc import Callable
from urllib.parse import urlencode

from ..config import Config, PhaseStreamsEntry

ACTIVE = ("in_season", "in_wave")
# Each phase-producing method's own combining rule (spec §6.3.1): aedseo's is SSI's, every stream active.
RULES: dict[str, Callable[[list[str]], bool]] = {"aedseo": lambda phases: all(p in ACTIVE for p in phases)}


def pathogen_phases(entry: PhaseStreamsEntry, by_role: dict[str, dict[str, str | None]], waves: bool) -> list[dict]:
    """The pathogen's phase for each week every stream has one: a lagging stream leaves the week out rather
    than reading as out of season."""
    active, inactive = ("in_wave", "between_waves") if waves else ("in_season", "out_of_season")
    rule = RULES[entry.method]
    weeks = set.intersection(*({p for p, phase in phases.items() if phase} for phases in by_role.values()))
    return [{"location": entry.location, "pathogen": entry.pathogen, "period": week, "method": entry.method,
             "phase": active if rule([by_role[role][week] for role in by_role]) else inactive}
            for week in sorted(weeks)]


def stream_rows(entry: PhaseStreamsEntry, config: Config) -> list[dict]:
    rows = []
    for role, ref in sorted(entry.streams.items()):
        query = config.panel(entry.pathogen, ref).query
        rows.append({"location": entry.location, "pathogen": entry.pathogen, "method": entry.method, "role": role,
                     "feed": query.feed, "series": urlencode({"indicator": query.indicator, **query.dimensions})})
    return rows
