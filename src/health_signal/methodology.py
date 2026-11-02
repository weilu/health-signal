"""A deployment's methodology page (spec §9): Markdown per offered language whose placeholders the dashboard's own
settings fill, checked at startup so neither a typo nor a drifting number reaches readers."""
import json
import re
from collections.abc import Callable
from pathlib import Path

from .config import Config
from .datasource import read_table
from .methods import AEDSEO, MAX_DIP, MAX_MISSING

TEXT_DIR = Path(__file__).parent / "methodology_text"
BLOCKS = ("streams", "indicator_models", "phase_patterns", "censored", "levels", "method")
_PLACEHOLDER = re.compile(r"\{\{\s*(>\s*)?([a-z_.]+)\s*\}\}")


def load_methodology(config: Config) -> dict[str, dict]:
    """{language: {"markdown", "blocks"}}: values become inline markers the browser styles as settings, blocks
    become fenced markers it draws from `blocks` with its own labels, so tables read as the tabs do."""
    values = placeholder_values(config)
    blocks = block_data(config)
    directory = config.site.methodology_dir
    pages = {}
    for language in config.site.locales:
        method_text = lambda: _library_text(language, values)  # noqa: E731 - only when the page asks for it
        if directory is None:
            markdown = method_text()
        else:
            path = Path(directory) / f"{language}.md"
            if not path.is_file():
                raise ValueError(f"site.methodology_dir has no {path.name} for offered language {language!r}")
            markdown = _fill(path.read_text(encoding="utf-8"), path.name, values, method_text)
        pages[language] = {"markdown": markdown, "blocks": blocks}
    return pages


def _library_text(language: str, values: dict[str, str]) -> str:
    # A language the library has no text for reads it in English, as the rest of the interface does.
    path = TEXT_DIR / f"{AEDSEO.name}.{language}.md"
    if not path.is_file():
        path = TEXT_DIR / f"{AEDSEO.name}.en.md"
    return _fill(path.read_text(encoding="utf-8"), path.name, values, None)


def _fill(text: str, file: str, values: dict[str, str], method_text: Callable[[], str] | None) -> str:
    lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _PLACEHOLDER.finditer(line):
            block, name = match.group(1), match.group(2)
            known = name in BLOCKS and (method_text is not None or name != "method") if block else name in values
            if not known:
                raise ValueError(f"{file} line {number}: unknown placeholder {match.group(0)}")
            if block and line.strip() != match.group(0):
                raise ValueError(f"{file} line {number}: {match.group(0)} must stand on its own line")
        block = _PLACEHOLDER.fullmatch(line.strip())
        if block and block.group(1):
            name = block.group(2)
            lines.append(method_text() if name == "method" else f"```hs-block\n{name}\n```")
        else:
            lines.append(_PLACEHOLDER.sub(lambda m: values[m.group(2)], line))
    return "\n".join(lines) + "\n"


def _value(text) -> str:
    return f"`hs:{text}`"


def _label(key: str) -> str:
    return f"`hs:t:{key}`"


def placeholder_values(config: Config) -> dict[str, str]:
    start = config.surveillance.year_start_week
    wave_end = config.analytics.aedseo.wave_end
    values = {
        "surveillance.year_start_week": _value(start),
        "surveillance.year_end_week": _value(start - 1 if start > 1 else 52),
        "analytics.min_seasons": _value(config.analytics.min_seasons),
        "analytics.aedseo.wave_end.steps_with_decrease": _value(wave_end.steps_with_decrease),
        "analytics.aedseo.wave_end.burden_level_decrease": _label(f"level.{wave_end.burden_level_decrease.replace(' ', '_')}"),
        "phase.max_dip": _value(MAX_DIP),
        "phase.max_missing": _value(MAX_MISSING),
        "method.build": _value(", ".join(_builds(config)) or "—"),
    }
    values |= {f"method.{key}": _value(value) for key, value in AEDSEO.parameters.items()}
    return values


def _builds(config: Config) -> list[str]:
    # Each feed's tables record the build that graded them; feeds assessed by different builds show them all.
    builds = []
    for feed in config.data.feeds if config.data else []:
        path = Path(feed.assessments) / "assessed_with.csv" if feed.assessments else None
        if path is None or not path.is_file():
            continue
        rows = read_table(path, ["method", "setting", "value"])
        builds += [v for v in rows.loc[rows["setting"] == "package_version", "value"] if v not in builds]
    return builds


def block_data(config: Config) -> dict:
    options = config.filters.location.options if config.filters.location else []
    locations = [o.value for o in options] or sorted({e.location for e in config.analytics.phase_streams})
    entries = {(e.pathogen, e.location): e for e in config.analytics.phase_streams}

    def streams(target: str, location: str) -> dict | None:
        entry = entries.get((target, location))
        if entry is None:
            return None
        return {role: dict(zip(("page", "panel"), ref.split("/", 1))) for role, ref in entry.streams.items()}

    profiles = config.feed_profiles()
    rules = []
    for profile in profiles.values():
        if profile.count_units:
            rules.append({"kind": "count", "units": sorted(profile.count_units)})
        rules += [{"kind": "rate", "indicator": d.rate, "unit": d.unit, "denominator": d.denominator, "per": d.per}
                  for d in profile.denominators]
    rules.append({"kind": "constant"})
    unique = list({json.dumps(r, sort_keys=True): r for r in rules}.values())
    return {
        "streams": [{"target": t.id, "location": location, "streams": streams(t.id, location)}
                    for t in config.targets for location in locations],
        "phase_patterns": [{"target": t.id, "pattern": "waves" if t.id in config.analytics.wave_pathogens else "season"}
                           for t in config.targets],
        "indicator_models": unique,
        "censored": [{"feed": feed, "qualities": sorted(p.censored_qualities)}
                     for feed, p in profiles.items() if p.censored_qualities],
        "levels": {"method": AEDSEO.name},
    }
