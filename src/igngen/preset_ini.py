"""Load preset .ini files for output format and table geometry."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from importlib import resources
from pathlib import Path


@dataclass
class PresetIni:
    name: str
    load_unit: str
    origin: str
    axes: str  # fixed | generated
    layout: str
    export: str
    include_headers: bool = True
    delimiter: str = "comma"
    decimal_places: int = 0
    rows: int | None = None
    cols: int | None = None
    rpm_count: int | None = None
    load_count: int | None = None
    path: str | None = None


def _parse(path: Path) -> PresetIni:
    cp = configparser.ConfigParser()
    cp.read(path)
    preset = cp["preset"] if cp.has_section("preset") else {}
    output = cp["output"] if cp.has_section("output") else {}
    table = cp["table"] if cp.has_section("table") else {}

    def geti(section, key, default=None):
        if key not in section:
            return default
        return int(section.get(key))

    return PresetIni(
        name=preset.get("name", path.stem),
        load_unit=preset.get("load_unit", "inHg"),
        origin=preset.get("origin", "bottom_left"),
        axes=preset.get("axes", "fixed"),
        layout=("default" if output.get("layout", "default") == "swicked" else output.get("layout", "default")),
        export=("default" if output.get("export", "default") == "swicked" else output.get("export", "default")),
        include_headers=output.get("include_headers", "true").lower() in {"1", "true", "yes"},
        delimiter=output.get("delimiter", "comma"),
        decimal_places=int(output.get("decimal_places", "0")),
        rows=geti(table, "rows"),
        cols=geti(table, "cols"),
        rpm_count=geti(table, "rpm_count"),
        load_count=geti(table, "load_count"),
        path=str(path),
    )


def find_preset_ini(name: str, search_dirs: list[Path] | None = None) -> PresetIni | None:
    """Load presets/<name>.ini from CWD, package data, or explicit search dirs."""
    key = name.strip().lower()
    candidates: list[Path] = []
    for d in search_dirs or []:
        candidates.append(Path(d) / f"{key}.ini")
    candidates.append(Path.cwd() / "presets" / f"{key}.ini")
    candidates.append(Path(__file__).resolve().parents[2] / "presets" / f"{key}.ini")
    for path in candidates:
        if path.is_file():
            return _parse(path)
    return None
