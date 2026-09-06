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
    row_axis: str = "rpm"
    column_axis: str = "load"
    rpm_increases: str = "down"
    load_increases: str = "right"


# Alpha / ALPHAlink High Cam Ignition layout (20×16).
# Load is gauge inHg: vacuum negative, ~0 ≈ atmosphere, boost positive.
ALPHA = AxisPreset(
    name="alpha",
    description=(
        "Alpha (ALPHAlink-style) High Cam grid: 20 RPM × 16 Load. "
        "Load axis is inHg (vacuum → boost). Heatmap display matches Alpha orientation."
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
)

PRESETS: dict[str, AxisPreset] = {
    ALPHA.name: ALPHA,
    # Back-compat alias
    "alphalink-high-cam": ALPHA,
}


def get_preset(name: str) -> AxisPreset:
    key = name.strip().lower()
    if key not in PRESETS:
        known = ", ".join(sorted({p.name for p in PRESETS.values()}))
        raise ValueError(f"unknown preset {name!r}; known: {known}")
    return PRESETS[key]
