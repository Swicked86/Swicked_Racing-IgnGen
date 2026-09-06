"""Built-in table axis presets for target tuning software."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxisPreset:
    name: str
    description: str
    rpm: tuple[float, ...]
    load: tuple[float, ...]  # load units described below
    load_unit: str
    # How ALPHAlink / similar Honda tools usually lay out the grid
    row_axis: str = "rpm"  # rows
    column_axis: str = "load"  # columns
    rpm_increases: str = "down"  # top → bottom in UI
    load_increases: str = "right"  # left → right


# Captured from ALPHAlink v0.1.47 High Cam Ignition (VX_180cc_base.bin):
# "Load (inHg) vs RPM (degrees advance, 6 boost columns)"
ALPHALINK_HIGH_CAM = AxisPreset(
    name="alphalink-high-cam",
    description=(
        "ALPHAlink High Cam Ignition layout: 20 RPM × 16 Load(inHg). "
        "Vacuum columns on the left, ~6 boost columns on the right; "
        "0 inHg ≈ atmospheric crossover."
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
    ALPHALINK_HIGH_CAM.name: ALPHALINK_HIGH_CAM,
}


def get_preset(name: str) -> AxisPreset:
    key = name.strip().lower()
    if key not in PRESETS:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"unknown preset {name!r}; known: {known}")
    return PRESETS[key]
