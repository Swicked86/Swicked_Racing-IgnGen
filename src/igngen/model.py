"""Ignition surface model from Swicked Racing research notes.

Build in layers. Current review: idle pocket (±2° across idle MAP 30–45 kPa).
Boost / idle pocket / soft limit are staged next.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .table import TimingTable
from .units import inhg_gauge_to_kpa_abs

KPA_PER_PSI = 6.895

LayerName = Literal["mechanical", "vacuum", "boost", "idle", "full"]


@dataclass
class EngineSpec:
    displacement_cc: float = 1600.0
    peak_hp: float = 280.0
    peak_hp_rpm: float = 7800.0
    peak_torque_lbft: float = 189.0
    peak_torque_rpm: float = 4800.0
    redline_rpm: float = 9300.0
    boost_psi: float = 0.0
    # Mechanical curve (configurable)
    base_timing: float = 10.0
    mech_timing_at_peak_torque: float = 32.0
    idle_rpm: float = 1100.0
    # Vacuum: absolute total timing at ≤ vacuum_full_map_kpa (fixed 40 kPa)
    vacuum_total_timing: float = 50.0
    vacuum_full_map_kpa: float = 40.0
    # Later layers (kept for full model)
    idle_pocket_width: float = 100.0  # ±RPM from idle (not total span)
    # Idle vacuum band (kPa abs) — typical ~30–45; +2° at lo, −2° at hi
    idle_map_lo: float = 30.0
    idle_map_hi: float = 45.0
    idle_pocket_bump: float = 2.0  # degrees at bottom / top of MAP band
    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    vacuum_advance_per_kpa: float = 0.35  # legacy
    vacuum_advance: float = 10.0  # legacy alias; prefer vacuum_total_timing
    vacuum_advance_max: float = 50.0  # kept as soft ceiling (= total by default)
    # RPM where vacuum is fully phased in (0 = auto: pocket_hi + ramp)
    vacuum_full_rpm: float = 0.0
    boost_retard_per_psi: float = 1.5  # legacy rate; unused by boost layer
    # Total ° minimum under full boost (mirror of vacuum_total_timing)
    boost_timing_limit: float = 20.0
    boost_retard_max: float = 20.0  # alias / floor compat (= boost_timing_limit)
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



def boost_retard_full(spec: EngineSpec) -> float:
    """Max boost retard (°): full mechanical minus boost timing limit.

    NA (``boost_psi == 0``): ignored — no retard.
    """
    if float(spec.boost_psi) <= 0.0:
        return 0.0
    limit = float(getattr(spec, "boost_timing_limit", spec.boost_retard_max))
    return max(0.0, float(spec.mech_timing_at_peak_torque) - limit)


def boost_retard_at_rpm(rpm: float, spec: EngineSpec) -> float:
    """Available boost retard at this RPM — full retard × mechanical progress."""
    return boost_retard_full(spec) * mechanical_progress(rpm, spec)


def boost_low_at_rpm(rpm: float, spec: EngineSpec) -> float:
    """Timing at full boost: master curve minus scaled retard."""
    return mechanical_advance(rpm, spec) - boost_retard_at_rpm(rpm, spec)


def max_boost_map_kpa(spec: EngineSpec) -> float:
    """Configured max boost MAP (atm + gauge boost). Overboost is above this."""
    return float(spec.atm_kpa) + max(0.0, float(spec.boost_psi)) * KPA_PER_PSI


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
    half = max(float(spec.idle_pocket_width), 1.0)
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
    """Vacuum-only row: boost side stays on the mechanical master curve."""
    return pressure_row_timings(rpm, loads_kpa, spec, include_boost=False)


def pressure_row_timings(
    rpm: float,
    loads_kpa: list[float],
    spec: EngineSpec,
    *,
    include_boost: bool = True,
) -> list[int]:
    """Whole-degree timings fanning from the 100 kPa master curve.

    Vacuum (below atm): add = (total − peak_mech) × mechanical_progress
    Boost (above atm): retard = (peak_mech − boost_limit) × mechanical_progress
    Full vac at ≤40 kPa; full retard at ≥ configured max boost MAP.
    """
    mech = int(round(mechanical_advance(rpm, spec)))
    high = int(round(vacuum_high_at_rpm(rpm, spec)))
    # boost_psi == 0 → NA: ignore boost retard entirely (atm + tip stay on master curve)
    use_boost = bool(include_boost) and float(spec.boost_psi) > 0.0
    low = int(round(boost_low_at_rpm(rpm, spec))) if use_boost else mech
    full_at = float(spec.vacuum_full_map_kpa)
    atm = float(spec.atm_kpa)
    boost_full = max_boost_map_kpa(spec)

    vac_full_idxs = [i for i, x in enumerate(loads_kpa) if x <= full_at]
    vac_mid_idxs = [i for i, x in enumerate(loads_kpa) if full_at < x < atm]
    if use_boost:
        atm_idxs = [i for i, x in enumerate(loads_kpa) if abs(x - atm) < 0.51]
        boost_mid_idxs = [i for i, x in enumerate(loads_kpa) if atm < x < boost_full]
        boost_full_idxs = [i for i, x in enumerate(loads_kpa) if x >= boost_full]
    else:
        atm_idxs = [i for i, x in enumerate(loads_kpa) if x >= atm]
        boost_mid_idxs = []
        boost_full_idxs = []

    out = [mech] * len(loads_kpa)
    for i in vac_full_idxs:
        out[i] = high
    vac_mids = _whole_degree_taper(high, mech, len(vac_mid_idxs))
    for i, idx in enumerate(vac_mid_idxs):
        out[idx] = vac_mids[i]
    for i in atm_idxs:
        out[i] = mech
    if use_boost:
        boost_mids = _whole_degree_taper(mech, low, len(boost_mid_idxs))
        for i, idx in enumerate(boost_mid_idxs):
            out[idx] = boost_mids[i]
        for i in boost_full_idxs:
            out[i] = low
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
        f"scaled by mechanical progress; whole° load-cell steps to atm"
    )


def describe_boost_curve(spec: EngineSpec) -> str:
    limit = float(getattr(spec, "boost_timing_limit", spec.boost_retard_max))
    retard = boost_retard_full(spec)
    mb = max_boost_map_kpa(spec)
    if spec.boost_psi <= 0:
        return "Boost: off (0 psi)"
    return (
        f"Boost: fans from 100 kPa master curve; "
        f"−{retard:.0f}° max → {limit:.0f}° at ≥{mb:.0f} kPa "
        f"once mechanical is all-in ({spec.peak_torque_rpm:.0f} RPM); "
        f"scaled by mechanical progress; whole° load-cell steps from atm"
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


def idle_pocket_half_rpm(spec: EngineSpec) -> float:
    """±RPM of the idle pocket — matches axes._pocket_edges."""
    return max(float(spec.idle_pocket_width), 1.0)


def idle_pocket_correction(rpm: float, map_kpa: float, spec: EngineSpec) -> float:
    """Localized idle basin: RPM pocket × idle MAP band.

    At idle vacuum (default 30–45 kPa): stabilization vs RPM —
    axis pocket lower +bump°, idle 0°, pocket upper −bump°
    (e.g. 620→+2, 670→0, 720→−2 with bump=2). Outside RPM/MAP → 0.

    ±RPM matches the axis landmark pocket (idle_pocket_width is ± from idle).
    """
    half = idle_pocket_half_rpm(spec)
    idle = float(spec.idle_rpm)
    if abs(rpm - idle) > half + 1e-9:
        return 0.0
    lo = float(spec.idle_map_lo)
    hi = float(spec.idle_map_hi)
    if hi < lo or map_kpa < lo or map_kpa > hi:
        return 0.0
    bump = float(getattr(spec, "idle_pocket_bump", 2.0))
    # −1 at pocket_lo, 0 at idle, +1 at pocket_hi (same edges as RPM axis)
    t = (rpm - idle) / half
    return -bump * t


def describe_idle_pocket(spec: EngineSpec) -> str:
    half = idle_pocket_half_rpm(spec)
    bump = float(getattr(spec, "idle_pocket_bump", 2.0))
    lo_rpm = spec.idle_rpm - half
    hi_rpm = spec.idle_rpm + half
    return (
        f"Idle pocket: {lo_rpm:.0f}/{spec.idle_rpm:.0f}/{hi_rpm:.0f} RPM "
        f"@ {spec.idle_map_lo:.0f}–{spec.idle_map_hi:.0f} kPa; "
        f"+{bump:.0f}° / 0° / −{bump:.0f}° (stabilization)"
    )


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

    if layers in {"vacuum", "boost"}:
        use_boost = layers == "boost" and float(spec.boost_psi) > 0.0
        high = vacuum_high_at_rpm(rpm, spec)
        low = boost_low_at_rpm(rpm, spec) if use_boost else mech
        full_at = float(spec.vacuum_full_map_kpa)
        atm = float(spec.atm_kpa)
        boost_full = max_boost_map_kpa(spec)
        if map_kpa <= full_at:
            value = high
        elif map_kpa < atm:
            t = (map_kpa - full_at) / max(atm - full_at, 1.0)
            value = high + (mech - high) * t
        elif map_kpa <= atm or not use_boost:
            value = mech
        elif map_kpa >= boost_full:
            value = low
        else:
            t = (map_kpa - atm) / max(boost_full - atm, 1.0)
            value = mech + (low - mech) * t
        return int(round(max(0.0, value)))

    if layers == "idle":
        base = float(timing_at(rpm, map_kpa, spec, layers="boost"))
        value = base + idle_pocket_correction(rpm, map_kpa, spec)
        return int(round(max(0.0, value)))

    # full — idle layer + soft redline (staged)
    base = float(timing_at(rpm, map_kpa, spec, layers="idle"))
    value = base + soft_limit_correction(rpm, spec)
    atm = spec.atm_kpa
    limit = float(getattr(spec, "boost_timing_limit", spec.boost_retard_max))
    if map_kpa < atm:
        value = min(value, spec.vacuum_total_timing)
    elif map_kpa > atm:
        value = max(value, limit)
    in_idle_pocket = (
        abs(rpm - spec.idle_rpm) <= idle_pocket_half_rpm(spec) and spec.idle_map_lo <= map_kpa <= spec.idle_map_hi
    )
    floor = spec.map_floor if in_idle_pocket else max(spec.map_floor, spec.normal_min)
    if map_kpa > atm:
        floor = max(floor, limit) if soft_limit_correction(rpm, spec) >= 0 else spec.map_floor
    ceiling = max(spec.map_ceiling, spec.vacuum_total_timing)
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
        elif layers == "boost":
            row_i = pressure_row_timings(r, maps, spec, include_boost=True)
            values.append([float(v) for v in row_i])
        elif layers == "idle":
            row_i = pressure_row_timings(r, maps, spec, include_boost=True)
            row_i = [
                int(round(v + idle_pocket_correction(r, maps[j], spec)))
                for j, v in enumerate(row_i)
            ]
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
