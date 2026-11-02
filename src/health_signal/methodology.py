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
# The library text is in named sections, so a deployment can set its own reasoning between them.
_SECTION = re.compile(r"<!-- section: ([a-z_]+) -->")
BLOCKS = ("streams", "indicator_models", "phase_patterns", "levels")
_PLACEHOLDER = re.compile(r"\{\{\s*(>\s*)?([a-z_.]+)\s*\}\}")
# Anything in double braces, so a misspelt placeholder is caught rather than shown; maths spans are set apart,
# since LaTeX writes double braces of its own.
_BRACES = re.compile(r"\{\{(.*?)\}\}")
_MATH = re.compile(r"\$\$.*?\$\$|\$[^$\n]+\$")


def load_methodology(config: Config) -> dict[str, dict]:
    """{language: {"markdown", "blocks"}}: values become inline markers the browser styles as settings, blocks
    become fenced markers it draws from `blocks` with its own labels, so tables read as the tabs do."""
    values = placeholder_values(config)
    blocks = block_data(config)
    directory = config.site.methodology_dir
    pages = {}
    for language in config.site.locales:
        method_text = lambda name: _library_text(language, values, name)  # noqa: E731 - only when asked for
        if directory is None:
            markdown = method_text("method")
        else:
            path = Path(directory) / f"{language}.md"
            if not path.is_file():
                raise ValueError(f"site.methodology_dir has no {path.name} for offered language {language!r}")
            markdown = _fill(path.read_text(encoding="utf-8"), path.name, values, method_text)
        pages[language] = {"markdown": markdown, "blocks": blocks}
    return pages


def _library_path(language: str) -> Path:
    # A language the library has no text for reads it in English, as the rest of the interface does.
    path = TEXT_DIR / f"{AEDSEO.name}.{language}.md"
    return path if path.is_file() else TEXT_DIR / f"{AEDSEO.name}.en.md"


def _sections(language: str) -> dict[str, str]:
    sections, name = {}, None
    for line in _library_path(language).read_text(encoding="utf-8").splitlines():
        marker = _SECTION.fullmatch(line.strip())
        if marker:
            name = marker.group(1)
            sections[name] = []
        elif name is not None:
            sections[name].append(line)
    return {name: "\n".join(lines).strip() + "\n" for name, lines in sections.items()}


def library_sections(language: str) -> list[str]:
    return list(_sections(language))


def _library_text(language: str, values: dict[str, str], name: str) -> str:
    sections = _sections(language)
    text = "\n".join(sections.values()) if name == "method" else sections[name.split(".", 1)[1]]
    return _fill(text, _library_path(language).name, values, None)


def _fill(text: str, file: str, values: dict[str, str], method_text: Callable[[], str] | None) -> str:
    lines, fenced, display_math = [], False, False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        # An author showing a placeholder in code means it as written.
        if fenced or line.lstrip().startswith("```"):
            lines.append(line)
            continue
        if line.strip() == "$$":
            display_math = not display_math
        if display_math or line.strip() == "$$":
            lines.append(_in_maths(line, values))
            continue
        block = _PLACEHOLDER.fullmatch(line.strip())
        if block and block.group(1):
            name = block.group(2)
            method = name == "method" or (name.startswith("method.") and name[7:] in library_sections("en"))
            if not (method or name in BLOCKS) or (method and method_text is None):
                raise ValueError(f"{file} line {number}: unknown placeholder {block.group(0)}")
            lines.append(method_text(name) if method else f"```hs-block\n{name}\n```")
            continue
        lines.append(_fill_line(line, f"{file} line {number}", values))
    return "\n".join(lines) + "\n"


def _fill_line(line: str, where: str, values: dict[str, str]) -> str:
    out, last = [], 0
    for math in _MATH.finditer(line):
        out += [_fill_prose(line[last:math.start()], where, values), _in_maths(math.group(0), values)]
        last = math.end()
    out.append(_fill_prose(line[last:], where, values))
    return "".join(out)


def _fill_prose(text: str, where: str, values: dict[str, str]) -> str:
    def value(match: re.Match) -> str:
        placeholder = _PLACEHOLDER.fullmatch(match.group(0))
        if placeholder and placeholder.group(1):
            raise ValueError(f"{where}: {match.group(0)} must stand on its own line")
        if placeholder is None or placeholder.group(2) not in values:
            raise ValueError(f"{where}: unknown placeholder {match.group(0)}")
        return values[placeholder.group(2)]
    filled = _BRACES.sub(value, text)
    if "{{" in filled or "}}" in filled:
        raise ValueError(f"{where}: a placeholder is missing a brace")
    return filled


def _in_maths(text: str, values: dict[str, str]) -> str:
    # KaTeX can't show the marked value, so maths gets the bare one; LaTeX's own double braces stay.
    def bare(match: re.Match) -> str:
        placeholder = _PLACEHOLDER.fullmatch(match.group(0))
        if placeholder is None or placeholder.group(1) or placeholder.group(2) not in values:
            return match.group(0)
        return values[placeholder.group(2)].strip("`").removeprefix("hs:")
    return _PLACEHOLDER.sub(bare, text)


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
    # Named in the prose, translated, rather than a table: a deployment flags few such qualities, if any.
    censored = {feed: sorted(p.censored_qualities) for feed, p in config.feed_profiles().items() if p.censored_qualities}
    qualities = sorted({q for qs in censored.values() for q in qs})
    values["censored.qualities"] = ", ".join(_label(f"quality.{q}") for q in qualities) or _label("methodology.none")
    values["censored.feeds"] = ", ".join(_label(f"feeds.{f}") for f in censored) or _label("methodology.none")
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
        "levels": {"method": AEDSEO.name},
    }
