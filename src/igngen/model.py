"""Ignition surface model from Swicked Racing research notes.

Pipeline:
  engine inputs → landmarks → (axes) → distributor-like surface
  → idle pocket → soft redline retard → safety bounds

Pressure correction is asymmetric: vacuum advance ≠ mirrored boost retard.
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
    boost_retard_per_10kpa: float = 2.0
    map_ceiling: float = 50.0
    map_floor: float = -5.0
    atm_kpa: float = 100.0


def validate_power(spec: EngineSpec) -> list[str]:
    """Return human-readable consistency warnings (empty if OK)."""
    warnings: list[str] = []
    hp_from_tq = (spec.peak_torque_lbft * spec.peak_torque_rpm) / 5252.0
    tq_at_hp = (spec.peak_hp * 5252.0) / max(spec.peak_hp_rpm, 1.0)
    if tq_at_hp > spec.peak_torque_lbft * 1.02:
        warnings.append(
            "Peak HP implies more torque at HP RPM than stated peak torque "
            f"(~{tq_at_hp:.0f} lb-ft needed vs {spec.peak_torque_lbft:.0f} given)."
        )
    if abs(hp_from_tq - (spec.peak_torque_lbft * spec.peak_torque_rpm / 5252.0)) < 0:
        pass
    _ = hp_from_tq
    return warnings


def mechanical_advance(rpm: float, spec: EngineSpec) -> float:
    """RPM advance curve anchored at idle base and peak-torque WOT."""
    base = spec.base_timing
    # Target ~30° at peak-torque RPM (research default for 4-valve), then climb slowly.
    tq_target = 30.0
    hp_target = 33.0
    if rpm <= spec.idle_rpm:
        return base
    if rpm <= spec.peak_torque_rpm:
        t = (rpm - spec.idle_rpm) / max(spec.peak_torque_rpm - spec.idle_rpm, 1.0)
        return base + (tq_target - base) * _smoothstep(t)
    if rpm <= spec.peak_hp_rpm:
        t = (rpm - spec.peak_torque_rpm) / max(spec.peak_hp_rpm - spec.peak_torque_rpm, 1.0)
        return tq_target + (hp_target - tq_target) * _smoothstep(t)
    # Past HP peak, mostly flat until soft limit region
    return hp_target


def pressure_correction(map_kpa: float, spec: EngineSpec) -> float:
    """Asymmetric vacuum advance / boost retard around atmosphere."""
    atm = spec.atm_kpa
    if map_kpa <= atm:
        # 0 at atm → +vacuum_advance_max near ~30–40 kPa
        span = max(atm - 35.0, 1.0)
        t = min(1.0, max(0.0, (atm - map_kpa) / span))
        return spec.vacuum_advance_max * _smoothstep(t)
    # Boost retard: milder than mirrored vacuum
    over = map_kpa - atm
    return -(over / 10.0) * spec.boost_retard_per_10kpa


def idle_pocket_correction(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    """Localized spark idle control near idle RPM + light load only."""
    half = spec.idle_pocket_width / 2.0
    if abs(rpm - spec.idle_rpm) > half:
        return 0.0
    # Only bite at light load (roughly idle MAP band)
    if map_kpa > 55.0:
        return 0.0
    # Below target idle → add timing; above → retard
    # Gentler than the original 15°/100RPM idea to reduce hunt.
    delta_rpm = rpm - spec.idle_rpm
    # ±5° across the pocket half-width
    return -5.0 * (delta_rpm / max(half, 1.0))


def soft_limit_correction(rpm: float, spec: EngineSpec) -> float:
    start = spec.redline_rpm - spec.soft_limit_rpm_before_redline
    if rpm < start:
        return 0.0
    if rpm >= spec.redline_rpm:
        return -spec.soft_limit_retard
    t = (rpm - start) / max(spec.soft_limit_rpm_before_redline, 1.0)
    return -spec.soft_limit_retard * _smoothstep(t)


def timing_at(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    value = (
        mechanical_advance(rpm, spec)
        + pressure_correction(map_kpa, spec)
        + idle_pocket_correction(rpm, map_kpa, spec)
        + soft_limit_correction(rpm, spec)
    )
    return min(spec.map_ceiling, max(spec.map_floor, value))


def generate_table(
    rpm: list[float],
    load: list[float],
    *,
    spec: EngineSpec | None = None,
    load_unit: str = "inhg",
) -> TimingTable:
    """Fill an RPM×load grid using the research model.

    ``load_unit``:
      - ``inhg``: ALPHAlink-style gauge inHg (0≈atm)
      - ``kpa``: absolute kPa
    """
    spec = spec or EngineSpec()
    values: list[list[float]] = []
    for r in rpm:
        row: list[float] = []
        for load_v in load:
            if load_unit.lower() in {"inhg", "inHg".lower(), "inhg_gauge"}:
                map_kpa = inhg_gauge_to_kpa_abs(load_v, spec.atm_kpa)
            else:
                map_kpa = float(load_v)
            row.append(round(timing_at(r, map_kpa, spec), 2))
        values.append(row)
    return TimingTable(rpm=list(rpm), load=list(load), values=values)


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)
