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


def pressure_span_kpa(spec: EngineParameters) -> float:
    """Shared pressure scale either side of atmosphere.

    The vacuum side establishes the physical kPa span. With the normal
    100 -> 40 kPa vacuum curve this is 60 kPa. Boost mirrors that same
    pressure distance above atmosphere before the optional boost gain is applied.
    """
    return max(spec.atm_kpa - spec.vacuum_full_map_kpa, 1.0)


def vacuum_map_fraction(map_kpa: float, spec: EngineParameters) -> float:
    """0 at atmosphere, 1 at/below the full-vacuum diaphragm stop."""
    if map_kpa >= spec.atm_kpa:
        return 0.0
    return clamp01((spec.atm_kpa - map_kpa) / pressure_span_kpa(spec))


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


def boost_map_fraction(map_kpa: float, spec: EngineParameters) -> float:
    """Mirror the vacuum kPa curve above atmosphere, then apply boost gain.

    A gain of 1.0 is a literal mirror of the vacuum pressure scale. If the
    vacuum curve reaches its stop 60 kPa below atmosphere, boost reaches its
    timing limit 60 kPa above atmosphere.

    Gain > 1.0 brings retard in sooner. Gain < 1.0 brings it in more slowly.
    This is deliberately a pressure-domain gain, not degrees-per-psi math.

    Example with a 60-kPa vacuum span:
      gain 1.00 -> full retard at 160 kPa
      gain 0.75 -> full retard at 180 kPa
      gain 0.60 -> full retard at 200 kPa
      gain 1.50 -> full retard at 140 kPa
    """
    if spec.boost_psi <= 0.0 or map_kpa <= spec.atm_kpa:
        return 0.0
    gain = max(0.0, float(spec.boost_retard_gain))
    return clamp01(
        ((map_kpa - spec.atm_kpa) / pressure_span_kpa(spec)) * gain
    )


def full_boost_target_at_rpm(rpm: float, spec: EngineParameters) -> float:
    """Absolute boost timing limit phased in with mechanical progress.

    The tuner enters the desired total timing limit directly. IgnGen performs
    the subtraction internally, so no retard-angle arithmetic is required.
    """
    progress = mechanical_progress(rpm, spec)
    return float(
        spec.base_timing
        + (spec.boost_timing_limit - spec.base_timing) * progress
    )


def pressure_timing(rpm: float, map_kpa: float, spec: EngineParameters) -> float:
    """100-kPa master curve with mirrored vacuum/boost pressure corrections."""
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
