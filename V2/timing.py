from __future__ import annotations

from .profiles import EngineParameters

KPA_PER_PSI = 6.895


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def mechanical_progress(rpm: float, spec: EngineParameters) -> float:
    if rpm <= spec.idle_rpm:
        return 0.0
    if rpm >= spec.peak_torque_rpm:
        return 1.0
    return clamp01(
        (rpm - spec.idle_rpm)
        / max(spec.peak_torque_rpm - spec.idle_rpm, 1.0)
    )


def mechanical_timing(rpm: float, spec: EngineParameters) -> float:
    """100-kPa master timing curve."""
    if rpm <= spec.cranking_rpm:
        return float(spec.cranking_timing)
    if rpm <= spec.idle_rpm:
        return float(spec.base_timing)
    if rpm >= spec.peak_torque_rpm:
        return float(spec.mech_timing_at_peak_torque)

    progress = mechanical_progress(rpm, spec)
    return float(
        spec.base_timing
        + (spec.mech_timing_at_peak_torque - spec.base_timing) * progress
    )


def vacuum_map_fraction(map_kpa: float, spec: EngineParameters) -> float:
    """0 at atmosphere, 1 at/below the full-vacuum diaphragm stop."""
    if map_kpa >= spec.atm_kpa:
        return 0.0
    if map_kpa <= spec.vacuum_full_map_kpa:
        return 1.0
    return clamp01(
        (spec.atm_kpa - map_kpa)
        / max(spec.atm_kpa - spec.vacuum_full_map_kpa, 1.0)
    )


def vacuum_add_at(rpm: float, map_kpa: float, spec: EngineParameters) -> float:
    """Vacuum advance scaled from the atmospheric master curve.

    Full vacuum total is reached only once the mechanical curve is all-in.
    Below peak torque, available vacuum addition is scaled by mechanical progress.
    MAP interpolation uses the actual MAP value and is independent of table size.
    """
    full_add = max(
        0.0,
        spec.vacuum_total_timing - spec.mech_timing_at_peak_torque,
    )
    return (
        full_add
        * mechanical_progress(rpm, spec)
        * vacuum_map_fraction(map_kpa, spec)
    )


def suggested_boost_limit_from_rate(spec: EngineParameters) -> float:
    """Heuristic full-boost target using degrees of retard per psi."""
    return float(
        spec.mech_timing_at_peak_torque
        - max(0.0, spec.boost_psi) * spec.boost_retard_deg_per_psi
    )


def boost_map_fraction(map_kpa: float, spec: EngineParameters) -> float:
    """0 at atmosphere, 1 at/above configured maximum boost MAP."""
    if spec.boost_psi <= 0.0 or map_kpa <= spec.atm_kpa:
        return 0.0
    full_map = spec.max_boost_map_kpa
    if map_kpa >= full_map:
        return 1.0
    return clamp01(
        (map_kpa - spec.atm_kpa)
        / max(full_map - spec.atm_kpa, 1.0)
    )


def full_boost_target_at_rpm(rpm: float, spec: EngineParameters) -> float:
    """Inverted target fan for the boost side.

    This does not start with a fixed number of degrees and subtract it blindly
    from the low-RPM master curve. Instead, the full-boost target itself moves
    from base timing toward the configured minimum as the RPM curve progresses.

    At/below idle: full-boost target == base timing.
    At/above peak torque: full-boost target == boost_timing_limit.
    """
    progress = mechanical_progress(rpm, spec)
    return float(
        spec.base_timing
        + (spec.boost_timing_limit - spec.base_timing) * progress
    )


def pressure_timing(rpm: float, map_kpa: float, spec: EngineParameters) -> float:
    """Mechanical + pressure behavior before idle/limiter overrides."""
    master = mechanical_timing(rpm, spec)

    if map_kpa < spec.atm_kpa:
        return master + vacuum_add_at(rpm, map_kpa, spec)

    if map_kpa > spec.atm_kpa and spec.boost_psi > 0.0:
        fraction = boost_map_fraction(map_kpa, spec)
        target = full_boost_target_at_rpm(rpm, spec)
        return master + (target - master) * fraction

    return master


def idle_pocket_target(rpm: float, spec: EngineParameters) -> float:
    """Explicit idle-pocket timing target vs RPM."""
    low_timing, target_timing, high_timing = spec.derived_idle_targets()
    lo = spec.idle_pocket_lo_rpm
    center = spec.idle_rpm
    hi = spec.idle_pocket_hi_rpm

    if rpm <= center:
        if center <= lo:
            return target_timing
        t = clamp01((rpm - lo) / (center - lo))
        return low_timing + (target_timing - low_timing) * t

    if hi <= center:
        return target_timing
    t = clamp01((rpm - center) / (hi - center))
    return target_timing + (high_timing - target_timing) * t


def apply_idle_pocket(
    value: float,
    rpm: float,
    map_kpa: float,
    spec: EngineParameters,
) -> float:
    """Protect the local idle basin from the generic pressure surface."""
    if rpm < spec.idle_pocket_lo_rpm or rpm > spec.idle_pocket_hi_rpm:
        return value
    if map_kpa < spec.idle_map_lo or map_kpa > spec.idle_map_hi:
        return value
    return idle_pocket_target(rpm, spec)


def soft_limit_correction(rpm: float, spec: EngineParameters) -> float:
    start = spec.soft_limit_start_rpm
    if rpm <= start:
        return 0.0
    if rpm >= spec.redline_rpm:
        return -float(spec.soft_limit_retard)
    t = clamp01((rpm - start) / max(spec.redline_rpm - start, 1.0))
    # Smoothstep keeps the onset gentle while retaining an exact endpoint.
    smooth = t * t * (3.0 - 2.0 * t)
    return -float(spec.soft_limit_retard) * smooth


def timing_at(
    rpm: float,
    map_kpa: float,
    spec: EngineParameters,
    *,
    include_idle_pocket: bool = True,
    include_soft_limit: bool = True,
) -> float:
    """Canonical V2 ignition calculation for one RPM/MAP coordinate."""
    value = pressure_timing(float(rpm), float(map_kpa), spec)

    if include_idle_pocket:
        value = apply_idle_pocket(value, float(rpm), float(map_kpa), spec)

    if include_soft_limit:
        value += soft_limit_correction(float(rpm), spec)

    return value
