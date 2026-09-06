from __future__ import annotations

from .table import TimingTable


def generate_baseline(
    rpm: list[float],
    load: list[float],
    *,
    idle: float = 12.0,
    cruise: float = 28.0,
    wot: float = 18.0,
    rpm_base: float = 1000.0,
    rpm_slope: float = 1.5,
    minimum: float = 0.0,
    maximum: float = 45.0,
) -> TimingTable:
    """Build a simple RPM×load ignition map from tuner targets.

    Load blend (by position across the load axis):
    - first third → idle
    - middle third → cruise
    - last third → WOT
    with linear crossfades between regions.

    RPM curve adds ``rpm_slope`` degrees per 1000 RPM above ``rpm_base``.
    """
    if not rpm or not load:
        raise ValueError("rpm and load breakpoints required")

    values: list[list[float]] = []
    n = len(load)
    for r in rpm:
        rpm_add = max(0.0, (r - rpm_base) / 1000.0) * rpm_slope
        row: list[float] = []
        for j, _ in enumerate(load):
            t = j / max(n - 1, 1)
            base = _blend_load_targets(t, idle=idle, cruise=cruise, wot=wot)
            cell = min(maximum, max(minimum, base + rpm_add))
            row.append(round(cell, 2))
        values.append(row)

    return TimingTable(rpm=list(rpm), load=list(load), values=values)


def _blend_load_targets(
    t: float,
    *,
    idle: float,
    cruise: float,
    wot: float,
) -> float:
    """t in [0, 1] across load axis."""
    t = min(1.0, max(0.0, t))
    if t <= 0.33:
        # idle → cruise
        u = t / 0.33 if 0.33 else 0.0
        return idle + (cruise - idle) * u
    if t <= 0.66:
        # cruise plateau toward WOT start
        u = (t - 0.33) / 0.33
        return cruise + (wot - cruise) * (u * 0.35)
    # cruise/wot → full WOT
    u = (t - 0.66) / 0.34
    mid = cruise + (wot - cruise) * 0.35
    return mid + (wot - mid) * u
