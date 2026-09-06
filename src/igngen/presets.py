"""Built-in table axis presets for target tuning software."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisPreset:
    name: str
    description: str
    rpm: tuple[float, ...]
    load: tuple[float, ...]
    load_unit: str
    # Visual / export origin for this preset
    # alpha: top-left (RPM↓ Load→) — matches ALPHAlink screen
    # base:  bottom-left (RPM→ Load↑) — Swicked research default
    origin: str = "bottom_left"  # "top_left" | "bottom_left"
    default_layout: str = "swicked"  # "alpha" | "swicked"
    default_export: str = "swicked"


# Alpha / ALPHAlink High Cam Ignition layout (20×16).
# Load is gauge inHg: vacuum negative, ~0 ≈ atmosphere, boost positive.
# Origin is TOP-LEFT on the map (low RPM, deep vacuum).
ALPHA = AxisPreset(
    name="alpha",
    description=(
        "Alpha (ALPHAlink) High Cam grid: 20×16, Load in inHg. "
        "Map origin is top-left (RPM down, load right)."
    ),
    rpm=(
        0,
        600,
        1000,
        1500,
        2000,
        2500,
        3000,
        3550,
        4000,
        4500,
        4800,
        5000,
        5300,
        5550,
        6000,
        6500,
        7000,
        7500,
        8050,
        9000,
    ),
    load=(
        -90.1,
        -78.41,
        -66.71,
        -55.08,
        -43.39,
        -31.69,
        -20.0,
        -10.61,
        -2.51,
        2.62,
        13.51,
        26.61,
        39.02,
        52.19,
        64.6,
        77.7,
    ),
    load_unit="inHg",
    origin="top_left",
    default_layout="alpha",
    default_export="alpha",
)

# Base / Swicked research grid. MAP in kPa absolute; 100 = atmosphere crossover.
# Origin is BOTTOM-LEFT (RPM right, load up).
BASE = AxisPreset(
    name="base",
    description=(
        "Base Swicked grid: 16×12 MAP(kPa)×RPM-style axes with atmosphere at 100. "
        "Map origin is bottom-left (RPM right, load up)."
    ),
    rpm=(
        400,
        800,
        1100,
        1500,
        2000,
        2500,
        3000,
        3500,
        4000,
        4800,
        5500,
        6500,
        7500,
        8500,
        9300,
        10300,
    ),
    load=(
        20,
        30,
        40,
        50,
        60,
        70,
        80,
        90,
        100,  # atmosphere — always present
        110,
        120,
        140,
    ),
    load_unit="kPa",
    origin="bottom_left",
    default_layout="swicked",
    default_export="swicked",
)

PRESETS: dict[str, AxisPreset] = {
    ALPHA.name: ALPHA,
    BASE.name: BASE,
    "alphalink-high-cam": ALPHA,
}


def get_preset(name: str) -> AxisPreset:
    key = name.strip().lower()
    if key not in PRESETS:
        known = ", ".join(sorted({p.name for p in PRESETS.values()}))
        raise ValueError(f"unknown preset {name!r}; known: {known}")
    return PRESETS[key]
