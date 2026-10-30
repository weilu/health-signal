"""A deployment's own UI text (spec §9): its targets, pages, panels, locations and the units its profile
extensions add, one JSON file per offered language. The browser merges it over the library's catalogue."""
import json
from pathlib import Path


def load_overlays(directory: Path | None, languages: list[str]) -> dict[str, dict]:
    """{language: catalogue} read from `<directory>/<language>.json`, checked at startup so a missing or broken
    file fails loudly instead of leaving every label in that language as its raw id."""
    if directory is None:
        return {}
    overlays = {}
    for language in languages:
        path = Path(directory) / f"{language}.json"
        if not path.is_file():
            raise ValueError(f"site.locales_dir has no {path.name} for offered language {language!r}")
        try:
            catalogue = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name} is not valid JSON: {e}") from e
        if not isinstance(catalogue, dict):
            raise ValueError(f"{path.name} must be a JSON object of keys to text")
        _check_text(catalogue, path.name)
        overlays[language] = catalogue
    return overlays


def _check_text(catalogue: dict, file: str, prefix: str = "") -> None:
    for key, value in catalogue.items():
        if isinstance(value, dict):
            _check_text(value, file, f"{prefix}{key}.")
        elif not isinstance(value, str):
            raise ValueError(f"{file}: {prefix}{key} must be text or a group of keys, not {type(value).__name__}")
