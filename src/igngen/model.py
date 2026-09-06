"""Ignition surface model from Swicked Racing research notes.

Vacuum advance and boost retard are asymmetric. Steps control how fast
timing moves with MAP; limits are absolute total timing (° BTDC), not
add/subtract amounts.
"""

from __future__ import annotations

from dataclasses import dataclass

from .table import TimingTable
from .units import inhg_gauge_to_kpa_abs

KPA_PER_PSI = 6.895


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
    # Vacuum: ° added per kPa below atm; vacuum_advance_max = total ° ceiling
    vacuum_advance_per_kpa: float = 0.35
    vacuum_advance_max: float = 42.0
    # Boost: ° removed per psi above atm; boost_retard_max = total ° floor
    boost_retard_per_psi: float = 1.5
    boost_retard_max: float = 10.0
    map_floor: float = 0.0
    map_ceiling: float = 50.0
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
    base = spec.base_timing
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


def pressure_delta(map_kpa: float, spec: EngineSpec) -> float:
    """Uncapped MAP step only (°). Limits are applied as total timing in timing_at."""
    atm = spec.atm_kpa
    if map_kpa <= atm:
        return (atm - map_kpa) * spec.vacuum_advance_per_kpa
    over_psi = (map_kpa - atm) / KPA_PER_PSI
    return -over_psi * spec.boost_retard_per_psi


def pressure_correction(map_kpa: float, spec: EngineSpec) -> float:
    """Backward-compatible name: MAP step delta (limits are total ° in timing_at)."""
    return pressure_delta(map_kpa, spec)


def idle_pocket_correction(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    half = spec.idle_pocket_width / 2.0
    if half <= 0 or abs(rpm - spec.idle_rpm) > half:
        return 0.0
    if map_kpa > 60.0:
        return 0.0
    delta_rpm = rpm - spec.idle_rpm
    return -4.0 * (delta_rpm / half)


def soft_limit_correction(rpm: float, spec: EngineSpec) -> float:
    start = spec.redline_rpm - spec.soft_limit_rpm_before_redline
    if rpm < start:
        return 0.0
    if rpm >= spec.redline_rpm:
        return -spec.soft_limit_retard
    t = (rpm - start) / max(spec.soft_limit_rpm_before_redline, 1.0)
    return -spec.soft_limit_retard * _smoothstep(t)


def timing_at(rpm: float, map_kpa: float, spec: EngineSpec) -> int:
    mech = mechanical_advance(rpm, spec)
    value = (
        mech
        + pressure_delta(map_kpa, spec)
        + idle_pocket_correction(rpm, map_kpa, spec)
    )
    atm = spec.atm_kpa
    # Limits are absolute total timing, not add/subtract caps
    if map_kpa < atm:
        value = min(value, spec.vacuum_advance_max)
    elif map_kpa > atm:
        value = max(value, spec.boost_retard_max)

    value += soft_limit_correction(rpm, spec)

    in_idle_pocket = (
        abs(rpm - spec.idle_rpm) <= spec.idle_pocket_width / 2.0 and map_kpa <= 60.0
    )
    floor = spec.map_floor if in_idle_pocket else max(spec.map_floor, spec.normal_min)
    if soft_limit_correction(rpm, spec) < 0 or map_kpa > atm:
        # boost / soft-limit may go below normal_min; still honor boost total floor
        # unless soft limit is pulling further down for overspeed
        if map_kpa > atm and soft_limit_correction(rpm, spec) >= 0:
            floor = max(spec.map_floor, spec.boost_retard_max)
        else:
            floor = spec.map_floor
    ceiling = max(spec.map_ceiling, spec.vacuum_advance_max)
    clamped = min(ceiling, max(floor, value))
    return int(round(clamped))


def generate_table(
    rpm: list[float],
    load: list[float],
    *,
    spec: EngineSpec | None = None,
    load_unit: str = "inhg",
) -> TimingTable:
    spec = spec or EngineSpec()
    rpm_i = [float(int(round(r))) for r in rpm]
    load_i = [float(int(round(v))) for v in load]
    values: list[list[float]] = []
    for r in rpm_i:
        row: list[float] = []
        for load_v in load_i:
            unit = load_unit.lower()
            if unit in {"inhg", "inhg_gauge"}:
                map_kpa = inhg_gauge_to_kpa_abs(load_v, spec.atm_kpa)
            else:
                map_kpa = float(load_v)
            row.append(float(timing_at(r, map_kpa, spec)))
        values.append(row)
    return TimingTable(
        rpm=rpm_i,
        load=load_i,
        values=values,
        load_unit="inHg" if load_unit.lower().startswith("inhg") else load_unit,
    )


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)
