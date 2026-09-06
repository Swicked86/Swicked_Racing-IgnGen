"""Ignition surface model from Swicked Racing research notes.

Build in layers. Current default: mechanical advance only.
Vacuum / boost / idle pocket / soft limit are staged next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .table import TimingTable
from .units import inhg_gauge_to_kpa_abs

KPA_PER_PSI = 6.895

LayerName = Literal["mechanical", "full"]


@dataclass
class EngineSpec:
    displacement_cc: float = 1600.0
    peak_hp: float = 280.0
    peak_hp_rpm: float = 7800.0
    peak_torque_lbft: float = 189.0
    peak_torque_rpm: float = 4800.0
    redline_rpm: float = 9300.0
    boost_psi: float = 7.0
    # Mechanical curve (configurable)
    base_timing: float = 10.0
    mech_timing_at_peak_torque: float = 32.0
    idle_rpm: float = 1100.0
    # Later layers (kept for full model; unused when layers=mechanical)
    idle_pocket_width: float = 250.0
    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    vacuum_advance_per_kpa: float = 0.35
    vacuum_advance_max: float = 42.0
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
    """Distributor mechanical curve vs RPM (load-independent).

    - At/below idle: base_timing (initial / static)
    - Idle → peak torque RPM: smooth ramp to mech_timing_at_peak_torque
    - Above peak torque: hold that total (no further climb)
    """
    base = spec.base_timing
    peak = spec.mech_timing_at_peak_torque
    idle = max(spec.idle_rpm, 1.0)
    if rpm <= idle:
        return base
    if rpm >= spec.peak_torque_rpm:
        return peak
    t = (rpm - idle) / max(spec.peak_torque_rpm - idle, 1.0)
    return base + (peak - base) * _smoothstep(t)


def describe_mechanical_curve(spec: EngineSpec) -> str:
    return (
        f"Mechanical only: {spec.base_timing:.0f}° at idle "
        f"({spec.idle_rpm:.0f} RPM) → {spec.mech_timing_at_peak_torque:.0f}° "
        f"by peak torque ({spec.peak_torque_rpm:.0f} RPM), hold above"
    )


def pressure_delta(map_kpa: float, spec: EngineSpec) -> float:
    atm = spec.atm_kpa
    if map_kpa <= atm:
        return (atm - map_kpa) * spec.vacuum_advance_per_kpa
    over_psi = (map_kpa - atm) / KPA_PER_PSI
    return -over_psi * spec.boost_retard_per_psi


def pressure_correction(map_kpa: float, spec: EngineSpec) -> float:
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


def timing_at(
    rpm: float,
    map_kpa: float,
    spec: EngineSpec,
    *,
    layers: LayerName = "mechanical",
) -> int:
    if layers == "mechanical":
        return int(round(max(0.0, mechanical_advance(rpm, spec))))

    # full stack (kept for later; not the default yet)
    value = (
        mechanical_advance(rpm, spec)
        + pressure_delta(map_kpa, spec)
        + idle_pocket_correction(rpm, map_kpa, spec)
    )
    atm = spec.atm_kpa
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
        if map_kpa > atm and soft_limit_correction(rpm, spec) >= 0:
            floor = max(spec.map_floor, spec.boost_retard_max)
        else:
            floor = spec.map_floor
    ceiling = max(spec.map_ceiling, spec.vacuum_advance_max)
    return int(round(min(ceiling, max(floor, value))))


def generate_table(
    rpm: list[float],
    load: list[float],
    *,
    spec: EngineSpec | None = None,
    load_unit: str = "inhg",
    layers: LayerName = "mechanical",
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
            row.append(float(timing_at(r, map_kpa, spec, layers=layers)))
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
