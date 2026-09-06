"""Ignition surface model from Swicked Racing research notes.

Build in layers. Current review layer: mechanical + vacuum (total timing @ ≤40 kPa).
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
    # Vacuum: absolute total timing at ≤ vacuum_full_map_kpa (fixed 40 kPa)
    vacuum_total_timing: float = 50.0
    vacuum_full_map_kpa: float = 40.0
    # Later layers (kept for full model)
    idle_pocket_width: float = 250.0
    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    vacuum_advance_per_kpa: float = 0.35  # legacy
    vacuum_advance: float = 10.0  # legacy alias; prefer vacuum_total_timing
    vacuum_advance_max: float = 50.0  # kept as soft ceiling (= total by default)
    # RPM where vacuum is fully phased in (0 = auto: pocket_hi + ramp)
    vacuum_full_rpm: float = 0.0
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



def mechanical_progress(rpm: float, spec: EngineSpec) -> float:
    """Normalized mechanical-advance progress: 0 at/below idle, 1 at/above peak torque.

    Same schedule as ``mechanical_advance`` (linear idle → peak-torque RPM).
    """
    idle = max(spec.idle_rpm, 1.0)
    peak_rpm = float(spec.peak_torque_rpm)
    if rpm <= idle:
        return 0.0
    if rpm >= peak_rpm:
        return 1.0
    return (rpm - idle) / max(peak_rpm - idle, 1.0)


def vacuum_add_full(spec: EngineSpec) -> float:
    """Max vacuum add (°): total timing at ≤40 kPa minus full mechanical."""
    return max(
        0.0,
        float(spec.vacuum_total_timing) - float(spec.mech_timing_at_peak_torque),
    )


def vacuum_add_at_rpm(rpm: float, spec: EngineSpec) -> float:
    """Available vacuum add at this RPM — full add × mechanical progress."""
    return vacuum_add_full(spec) * mechanical_progress(rpm, spec)


def vacuum_high_at_rpm(rpm: float, spec: EngineSpec) -> float:
    """Timing at ≤40 kPa: master (100 kPa) curve + scaled vacuum add."""
    return mechanical_advance(rpm, spec) + vacuum_add_at_rpm(rpm, spec)


def vacuum_advance(map_kpa: float, spec: EngineSpec) -> float:
    """Legacy MAP-only full-add helper (assumes mechanical is all-in)."""
    add = vacuum_add_full(spec)
    if spec.vacuum_advance and abs(spec.vacuum_advance - 10.0) > 1e-9 and add == 0:
        add = float(spec.vacuum_advance)
    full_at = spec.vacuum_full_map_kpa
    atm = spec.atm_kpa
    if map_kpa >= atm:
        return 0.0
    if map_kpa <= full_at:
        return add
    t = (map_kpa - full_at) / max(atm - full_at, 1.0)
    return add * (1.0 - t)


def _pocket_hi_rpm(spec: EngineSpec) -> float:
    half = max(spec.idle_pocket_width / 2.0, 50.0)
    return float(spec.idle_rpm) + half


def vacuum_full_in_rpm(spec: EngineSpec) -> float:
    """RPM where vacuum reaches its max add (= peak-torque RPM)."""
    if spec.vacuum_full_rpm and spec.vacuum_full_rpm > 0:
        return float(spec.vacuum_full_rpm)
    return float(spec.peak_torque_rpm)


def vacuum_rpm_scale(rpm: float, spec: EngineSpec) -> float:
    """Alias for mechanical_progress (vacuum fans with the master curve)."""
    return mechanical_progress(rpm, spec)


def vacuum_advance_at(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    """MAP taper of the RPM-scaled vacuum add."""
    add = vacuum_add_at_rpm(rpm, spec)
    full_at = spec.vacuum_full_map_kpa
    atm = spec.atm_kpa
    if map_kpa >= atm:
        return 0.0
    if map_kpa <= full_at:
        return add
    t = (map_kpa - full_at) / max(atm - full_at, 1.0)
    return add * (1.0 - t)


def _whole_degree_taper(high: int, low: int, n_mid: int) -> list[int]:
    """n_mid whole° steps between high (exclusive) and low (exclusive).

    Splits (high - low) across (n_mid + 1) gaps so every cell stays an int.
    """
    if n_mid <= 0:
        return []
    high_i, low_i = int(high), int(low)
    gaps = n_mid + 1
    diff = high_i - low_i
    if diff <= 0:
        return [high_i] * n_mid
    base, rem = divmod(diff, gaps)
    gap_sizes = [base + (1 if i < rem else 0) for i in range(gaps)]
    out: list[int] = []
    cur = high_i
    for g in gap_sizes[:-1]:
        cur -= g
        out.append(cur)
    return out


def vacuum_row_timings(
    rpm: float,
    loads_kpa: list[float],
    spec: EngineSpec,
) -> list[int]:
    """Whole-degree vacuum-layer timings for one RPM across load breakpoints.

    The 100 kPa (atmosphere) row is the master mechanical RPM curve.
    Vacuum fans outward from that curve: available add =
    (total_timing − peak_mech) × mechanical_progress(rpm).
    Max total (e.g. 50° at ≤40 kPa) only when mechanical is all-in.

    - MAP ≥ atm: mechanical (master)
    - MAP ≤ 40 kPa: mechanical + scaled vacuum add
    - Between: whole° staircase across those load cells
    """
    mech = int(round(mechanical_advance(rpm, spec)))
    high = int(round(vacuum_high_at_rpm(rpm, spec)))
    full_at = float(spec.vacuum_full_map_kpa)
    atm = float(spec.atm_kpa)

    full_idxs = [i for i, m in enumerate(loads_kpa) if m <= full_at]
    mid_idxs = [i for i, m in enumerate(loads_kpa) if full_at < m < atm]
    atm_idxs = [i for i, m in enumerate(loads_kpa) if m >= atm]

    out = [mech] * len(loads_kpa)
    for i in full_idxs:
        out[i] = high
    for i in atm_idxs:
        out[i] = mech
    mids = _whole_degree_taper(high, mech, len(mid_idxs))
    for i, idx in enumerate(mid_idxs):
        out[idx] = mids[i] if i < len(mids) else mech
    return out


def describe_mechanical_curve(spec: EngineSpec) -> str:
    return (
        f"Mechanical: {spec.base_timing:.0f}° at idle "
        f"({spec.idle_rpm:.0f} RPM) → linear to {spec.mech_timing_at_peak_torque:.0f}° "
        f"by peak torque ({spec.peak_torque_rpm:.0f} RPM), hold above"
    )


def describe_vacuum_curve(spec: EngineSpec) -> str:
    add = vacuum_add_full(spec)
    return (
        f"Vacuum: fans from 100 kPa master curve; "
        f"+{add:.0f}° max → {spec.vacuum_total_timing:.0f}° at ≤{spec.vacuum_full_map_kpa:.0f} kPa "
        f"once mechanical is all-in ({spec.peak_torque_rpm:.0f} RPM); "
        f"scaled by mechanical progress below that; whole° load-cell steps to atm"
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
        # Single-point approx (tables use vacuum_row_timings for whole° cells)
        high = vacuum_high_at_rpm(rpm, spec)
        full_at = float(spec.vacuum_full_map_kpa)
        atm = float(spec.atm_kpa)
        if map_kpa <= full_at:
            value = high
        elif map_kpa >= atm:
            value = mech
        else:
            t = (map_kpa - full_at) / max(atm - full_at, 1.0)
            value = high + (mech - high) * t
        return int(round(max(0.0, value)))

    # full — vacuum total/RPM-gated; boost / idle / soft still staged here
    atm = spec.atm_kpa
    if map_kpa <= atm:
        # reuse vacuum-layer absolute timing then add idle pocket on top
        vac_abs = float(
            timing_at(rpm, map_kpa, spec, layers="vacuum")
        )
        value = vac_abs + idle_pocket_correction(rpm, map_kpa, spec)
    else:
        over_psi = (map_kpa - atm) / KPA_PER_PSI
        value = (
            mech
            - over_psi * spec.boost_retard_per_psi
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
    ceiling = max(spec.map_ceiling, spec.vacuum_total_timing, spec.vacuum_advance_max)
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
    # Precompute MAP for each load breakpoint
    maps: list[float] = []
    unit = load_unit.lower()
    for load_v in load_i:
        if unit in {"inhg", "inhg_gauge"}:
            maps.append(float(inhg_gauge_to_kpa_abs(load_v, spec.atm_kpa)))
        else:
            maps.append(float(load_v))

    for r in rpm_i:
        if layers == "vacuum":
            row_i = vacuum_row_timings(r, maps, spec)
            values.append([float(v) for v in row_i])
        else:
            row: list[float] = []
            for map_kpa in maps:
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
