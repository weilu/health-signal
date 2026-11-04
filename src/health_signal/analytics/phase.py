from collections.abc import Callable
from urllib.parse import urlencode

from ..config import PhaseStreamsEntry
from ..methods import AEDSEO, MEM
from .series import Series

# Each phase-producing method's own combining rule (spec §6.3.1): aedseo's is SSI's, every stream active; MEM pairs
# the same streams the same way, so the two methods' seasons differ only in how each stream's is set.
RULES: dict[str, Callable[[list[str]], bool]] = {
    m.name: lambda phases, m=m: all(p in m.active_phases for p in phases) for m in (AEDSEO, MEM)}


def pathogen_phases(entry: PhaseStreamsEntry, by_role: dict[str, dict[str, str | None]], waves: bool,
                    provisional: dict[str, dict[str, bool]] | None = None) -> list[dict]:
    """The pathogen's phase for each week every stream has one: a lagging stream leaves the week out rather
    than reading as out of season. Provisional when any stream's grade that week is: a phase is as settled as
    its thinnest stream."""
    active, inactive = ("in_wave", "between_waves") if waves else ("in_season", "out_of_season")
    rule = RULES[entry.method]
    provisional = provisional or {}
    weeks = set.intersection(*({p for p, phase in phases.items() if phase} for phases in by_role.values()))
    return [{"location": entry.location, "pathogen": entry.pathogen, "period": week, "method": entry.method,
             "phase": active if rule([by_role[role][week] for role in by_role]) else inactive,
             "provisional": any(provisional.get(role, {}).get(week, False) for role in by_role)}
            for week in sorted(weeks)]


def stream_rows(entry: PhaseStreamsEntry, resolved: dict[str, Series]) -> list[dict]:
    """Each role's series as the data pins it, not as its panel's query states it: a query may leave a dimension
    (e.g. age) implicit, and the descriptor must still name exactly one series."""
    return [{"location": entry.location, "pathogen": entry.pathogen, "method": entry.method, "role": role,
             "feed": s.feed, "series": urlencode({"indicator": s.indicator, **s.dimensions})}
            for role, s in sorted(resolved.items())]
