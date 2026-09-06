"""Ignition surface model from Swicked Racing research notes.

Build in layers. Current review layer: mechanical + vacuum advance.
Boost / idle pocket / soft limit are staged next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .table import TimingTable
from .units import inhg_gauge_to_kpa_abs

KPA_PER_PSI = 6.895

LayerName = Literal["mechanical", "vacuum", "full"]


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
    # Vacuum advance (additive; full-in MAP is static)
    vacuum_advance: float = 10.0
    vacuum_full_map_kpa: float = 50.0
    # Later layers (kept for full model)
    idle_pocket_width: float = 250.0
    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    vacuum_advance_per_kpa: float = 0.35  # legacy full-model rate; unused by vacuum layer
    vacuum_advance_max: float = 42.0
    # RPM where vacuum add is fully phased in (0 = auto: pocket_hi + ramp)
    vacuum_full_rpm: float = 0.0  # total ° ceiling under vacuum
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
    - Idle → peak torque RPM: **linear** climb to mech_timing_at_peak_torque
      (starts advancing right out of idle — not after the idle pocket)
    - Above peak torque: hold that total
    """
    base = spec.base_timing
    peak = spec.mech_timing_at_peak_torque
    idle = max(spec.idle_rpm, 1.0)
    if rpm <= idle:
        return base
    if rpm >= spec.peak_torque_rpm:
        return peak
    t = (rpm - idle) / max(spec.peak_torque_rpm - idle, 1.0)
    return base + (peak - base) * t


def vacuum_advance(map_kpa: float, spec: EngineSpec) -> float:
    """Additive vacuum advance vs MAP (RPM-independent).

    Full advance at/below static ``vacuum_full_map_kpa`` (default **50 kPa**).
    Linear taper from that MAP up to atmosphere → 0°. Above atm → 0°.
    """
    atm = spec.atm_kpa
    full_at = spec.vacuum_full_map_kpa
    add = spec.vacuum_advance
    if map_kpa >= atm:
        return 0.0
    if map_kpa <= full_at:
        return add
    # full_at < map < atm
    t = (map_kpa - full_at) / max(atm - full_at, 1.0)
    return add * (1.0 - t)



def _pocket_hi_rpm(spec: EngineSpec) -> float:
    half = max(spec.idle_pocket_width / 2.0, 50.0)
    return float(spec.idle_rpm) + half


def vacuum_full_in_rpm(spec: EngineSpec) -> float:
    """RPM at which vacuum advance is fully applied (above idle pocket)."""
    if spec.vacuum_full_rpm and spec.vacuum_full_rpm > 0:
        return float(spec.vacuum_full_rpm)
    pocket_hi = _pocket_hi_rpm(spec)
    # ~0.8–1.0k above pocket so idle corner stays at mechanical base
    return pocket_hi + max(800.0, float(spec.idle_rpm) * 0.75)


def vacuum_rpm_scale(rpm: float, spec: EngineSpec) -> float:
    """0 through the idle pocket; linear to 1 by vacuum_full_in_rpm.

    Keeps cranking/idle cells on mechanical base so vacuum does not
    light up the whole idle corner of the map.
    """
    pocket_hi = _pocket_hi_rpm(spec)
    full_at = vacuum_full_in_rpm(spec)
    if rpm <= pocket_hi:
        return 0.0
    if rpm >= full_at:
        return 1.0
    return (rpm - pocket_hi) / max(full_at - pocket_hi, 1.0)


def vacuum_advance_at(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    """MAP vacuum curve gated by RPM (no vac in the idle pocket)."""
    return vacuum_advance(map_kpa, spec) * vacuum_rpm_scale(rpm, spec)


def describe_mechanical_curve(spec: EngineSpec) -> str:
    return (
        f"Mechanical: {spec.base_timing:.0f}° at idle "
        f"({spec.idle_rpm:.0f} RPM) → linear to {spec.mech_timing_at_peak_torque:.0f}° "
        f"by peak torque ({spec.peak_torque_rpm:.0f} RPM), hold above"
    )


def describe_vacuum_curve(spec: EngineSpec) -> str:
    pocket_hi = _pocket_hi_rpm(spec)
    full_rpm = vacuum_full_in_rpm(spec)
    return (
        f"Vacuum: +{spec.vacuum_advance:.0f}° full at ≤{spec.vacuum_full_map_kpa:.0f} kPa, "
        f"taper to 0° by atm ({spec.atm_kpa:.0f} kPa); "
        f"0° through idle pocket (≤{pocket_hi:.0f} RPM), full by {full_rpm:.0f} RPM; "
        f"total ceiling {spec.vacuum_advance_max:.0f}°"
    )


def pressure_delta(map_kpa: float, spec: EngineSpec) -> float:
    """Legacy full-model vac/boost blend (boost path still used by layers=full)."""
    atm = spec.atm_kpa
    if map_kpa <= atm:
        return vacuum_advance(map_kpa, spec)
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
    mech = mechanical_advance(rpm, spec)

    if layers == "mechanical":
        return int(round(max(0.0, mech)))

    if layers == "vacuum":
        value = mech + vacuum_advance_at(rpm, map_kpa, spec)
        if map_kpa < spec.atm_kpa:
            value = min(value, spec.vacuum_advance_max)
        return int(round(max(0.0, value)))

    # full — vacuum RPM-gated; boost / idle / soft still staged here
    atm = spec.atm_kpa
    if map_kpa <= atm:
        vac_boost = vacuum_advance_at(rpm, map_kpa, spec)
    else:
        over_psi = (map_kpa - atm) / KPA_PER_PSI
        vac_boost = -over_psi * spec.boost_retard_per_psi
    value = mech + vac_boost + idle_pocket_correction(rpm, map_kpa, spec)
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
