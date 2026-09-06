"""Ignition surface model from Swicked Racing research notes.

Pipeline:
  engine inputs → landmarks → distributor-like surface
  → idle pocket → soft redline retard → safety bounds

Normal generated maps stay at whole non-negative degrees.
Vacuum advance and boost retard are asymmetric (not mirrored).
"""

from __future__ import annotations

from dataclasses import dataclass

from .table import TimingTable
from .units import inhg_gauge_to_kpa_abs


@dataclass
class EngineSpec:
    displacement_cc: float = 1600.0
    peak_hp: float = 280.0
    peak_hp_rpm: float = 7800.0
    peak_torque_lbft: float = 189.0
    peak_torque_rpm: float = 4800.0
    redline_rpm: float = 9300.0
    boost_psi: float = 7.0
    base_timing: float = 15.0
    idle_rpm: float = 1100.0
    idle_pocket_width: float = 250.0
    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    vacuum_advance_max: float = 18.0
    # Milder boost retard so WOT/boost cells stay usable (not driven negative)
    boost_retard_per_10kpa: float = 1.25
    # Normal-map floor: generated base tables should not go below this
    map_floor: float = 0.0
    map_ceiling: float = 50.0
    # Soft floor for "normal running" cells before idle-pocket carve-out
    normal_min: float = 8.0
    atm_kpa: float = 100.0


def validate_power(spec: EngineSpec) -> list[str]:
    warnings: list[str] = []
    tq_at_hp = (spec.peak_hp * 5252.0) / max(spec.peak_hp_rpm, 1.0)
    if tq_at_hp > spec.peak_torque_lbft * 1.02:
        warnings.append(
            "Peak HP implies more torque at HP RPM than stated peak torque "
            f"(~{tq_at_hp:.0f} lb-ft needed vs {spec.peak_torque_lbft:.0f} given)."
        )
    return warnings


def mechanical_advance(rpm: float, spec: EngineSpec) -> float:
    """RPM advance at atmosphere — the 'vacuum hose disconnected' curve."""
    base = spec.base_timing
    # 4-valve research defaults: ~30° near peak torque, slight climb to HP peak
    tq_target = 30.0
    hp_target = 33.0
    if rpm <= max(spec.idle_rpm, 1.0):
        return base
    if rpm <= spec.peak_torque_rpm:
        t = (rpm - spec.idle_rpm) / max(spec.peak_torque_rpm - spec.idle_rpm, 1.0)
        return base + (tq_target - base) * _smoothstep(t)
    if rpm <= spec.peak_hp_rpm:
        t = (rpm - spec.peak_torque_rpm) / max(spec.peak_hp_rpm - spec.peak_torque_rpm, 1.0)
        return tq_target + (hp_target - tq_target) * _smoothstep(t)
    return hp_target


def pressure_correction(map_kpa: float, spec: EngineSpec) -> float:
    """Asymmetric vacuum advance / boost retard around 100 kPa."""
    atm = spec.atm_kpa
    if map_kpa <= atm:
        # 0 at atm → +vacuum_advance_max toward deep vacuum (~35 kPa)
        span = max(atm - 35.0, 1.0)
        t = min(1.0, max(0.0, (atm - map_kpa) / span))
        return spec.vacuum_advance_max * _smoothstep(t)
    over = map_kpa - atm
    # Cap boost retard so we don't erase the mechanical curve
    retard = (over / 10.0) * spec.boost_retard_per_10kpa
    return -min(retard, 12.0)


def idle_pocket_correction(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    """Localized idle spark control — light load near idle RPM only.

    Below target idle → add a little timing; above → retard a little.
    Kept gentle so it can't drag cells negative.
    """
    half = spec.idle_pocket_width / 2.0
    if abs(rpm - spec.idle_rpm) > half:
        return 0.0
    # Idle MAP is typically well under atmosphere
    if map_kpa > 60.0:
        return 0.0
    delta_rpm = rpm - spec.idle_rpm
    # ±4° across pocket half-width
    return -4.0 * (delta_rpm / max(half, 1.0))


def soft_limit_correction(rpm: float, spec: EngineSpec) -> float:
    """Pull timing before redline so overspeed feels like power loss."""
    start = spec.redline_rpm - spec.soft_limit_rpm_before_redline
    if rpm < start:
        return 0.0
    if rpm >= spec.redline_rpm:
        return -spec.soft_limit_retard
    t = (rpm - start) / max(spec.soft_limit_rpm_before_redline, 1.0)
    return -spec.soft_limit_retard * _smoothstep(t)


def timing_at(rpm: float, map_kpa: float, spec: EngineSpec) -> int:
    value = (
        mechanical_advance(rpm, spec)
        + pressure_correction(map_kpa, spec)
        + idle_pocket_correction(rpm, map_kpa, spec)
        + soft_limit_correction(rpm, spec)
    )
    # Normal generated map: whole degrees, never below map_floor (default 0)
    # Prefer normal_min away from the idle pocket carve-out at very light load.
    in_idle_pocket = (
        abs(rpm - spec.idle_rpm) <= spec.idle_pocket_width / 2.0 and map_kpa <= 60.0
    )
    floor = spec.map_floor if in_idle_pocket else max(spec.map_floor, spec.normal_min)
    # Soft-limit / high-boost regions may sit between map_floor and normal_min
    if soft_limit_correction(rpm, spec) < 0 or map_kpa > spec.atm_kpa:
        floor = spec.map_floor
    clamped = min(spec.map_ceiling, max(floor, value))
    return int(round(clamped))


def generate_table(
    rpm: list[float],
    load: list[float],
    *,
    spec: EngineSpec | None = None,
    load_unit: str = "inhg",
) -> TimingTable:
    """Fill an RPM×load grid. Timing cells are whole non-negative degrees."""
    spec = spec or EngineSpec()
    values: list[list[float]] = []
    for r in rpm:
        row: list[float] = []
        for load_v in load:
            unit = load_unit.lower()
            if unit in {"inhg", "inhg_gauge"}:
                map_kpa = inhg_gauge_to_kpa_abs(load_v, spec.atm_kpa)
            else:
                map_kpa = float(load_v)
            row.append(float(timing_at(r, map_kpa, spec)))
        values.append(row)
    return TimingTable(
        rpm=list(rpm),
        load=list(load),
        values=values,
        load_unit="inHg" if load_unit.lower().startswith("inhg") else load_unit,
    )


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)
