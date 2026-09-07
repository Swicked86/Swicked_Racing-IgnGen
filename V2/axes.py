from __future__ import annotations

import math

from .profiles import EngineParameters


RPM_STEPS = (50, 100, 250, 500, 1000)
MAP_STEPS = (5, 10, 20, 25, 50)


def _unique_sorted(values: list[float]) -> list[float]:
    return sorted({float(round(v)) for v in values})


def _nearest_step(raw_spacing: float, choices: tuple[int, ...]) -> int:
    """Choose a clean step that is not larger than the useful raw spacing."""
    if raw_spacing <= choices[0]:
        return choices[0]
    eligible = [s for s in choices if s <= raw_spacing]
    return eligible[-1] if eligible else choices[0]


def _snap(value: float, step: int) -> float:
    return float(int(round(value / step) * step))


def _fill_clean_interval(
    lo: float,
    hi: float,
    count: int,
    *,
    protected: set[float],
    steps: tuple[int, ...] = RPM_STEPS,
) -> list[float]:
    """Generate clean interior points without moving protected landmarks."""
    if count <= 0 or hi <= lo:
        return []

    raw_spacing = (hi - lo) / (count + 1)
    step = _nearest_step(raw_spacing, steps)
    ladder = [
        float(v)
        for v in range(
            int(math.ceil((lo + 1) / step) * step),
            int(hi),
            step,
        )
        if float(v) not in protected
    ]

    # If the chosen ladder is too coarse, progressively use a finer ladder.
    if len(ladder) < count:
        for finer in reversed([s for s in steps if s < step]):
            ladder = [
                float(v)
                for v in range(
                    int(math.ceil((lo + 1) / finer) * finer),
                    int(hi),
                    finer,
                )
                if float(v) not in protected
            ]
            if len(ladder) >= count:
                step = finer
                break

    if len(ladder) <= count:
        return ladder

    ideals = [lo + (hi - lo) * i / (count + 1) for i in range(1, count + 1)]
    selected: list[float] = []
    available = set(ladder)
    for ideal in ideals:
        if not available:
            break
        candidate = min(available, key=lambda x: (abs(x - ideal), x))
        selected.append(candidate)
        available.remove(candidate)
    return sorted(selected)


def _rpm_structural_anchors(spec: EngineParameters) -> list[float]:
    return _unique_sorted(
        [
            spec.cranking_rpm,
            spec.idle_pocket_lo_rpm,
            spec.idle_rpm,
            spec.idle_pocket_hi_rpm,
            spec.peak_torque_rpm,
            spec.soft_limit_start_rpm,
            spec.redline_rpm,
            spec.overspeed_rpm,
        ]
    )


def generate_rpm_axis(spec: EngineParameters, count: int) -> list[float]:
    """Generate RPM breakpoints using protected anchors + 2:1 discretionary budget.

    The 2:1 ratio is applied only after structural landmarks have been placed.
    Duplicate landmarks (for example cranking == idle-pocket lower edge) consume
    one cell, freeing the duplicate cell for useful resolution elsewhere.
    """
    if count < 2:
        raise ValueError("RPM axis requires at least 2 cells")

    anchors = _rpm_structural_anchors(spec)
    if len(anchors) > count:
        # Extremely constrained tables: keep the most important control landmarks.
        priority = [
            spec.cranking_rpm,
            spec.idle_rpm,
            spec.idle_pocket_hi_rpm,
            spec.peak_torque_rpm,
            spec.soft_limit_start_rpm,
            spec.redline_rpm,
            spec.overspeed_rpm,
            spec.idle_pocket_lo_rpm,
        ]
        selected: list[float] = []
        for value in priority:
            v = float(round(value))
            if v not in selected:
                selected.append(v)
            if len(selected) == count:
                break
        return sorted(selected)

    result = list(anchors)
    protected = set(result)
    remaining = count - len(result)

    # Peak HP is a preferred post-torque landmark when it is meaningful and fits.
    hp_rpm = float(round(spec.peak_hp_rpm))
    if (
        remaining > 0
        and spec.peak_hp_rpm > spec.peak_torque_rpm
        and spec.peak_hp_rpm < spec.overspeed_rpm
        and hp_rpm not in protected
    ):
        result.append(hp_rpm)
        protected.add(hp_rpm)
        remaining -= 1

    # Approximately 2/3 of discretionary resolution before peak torque, 1/3 after.
    pre_extra = int(round(remaining * 2.0 / 3.0))
    post_extra = remaining - pre_extra

    pre = _fill_clean_interval(
        spec.idle_pocket_hi_rpm,
        spec.peak_torque_rpm,
        pre_extra,
        protected=protected,
        steps=RPM_STEPS,
    )
    result.extend(pre)
    protected.update(pre)

    # Spend the post-torque budget over the full high-RPM region. Existing soft-limit,
    # redline, overspeed, and optional peak-HP anchors remain fixed.
    post = _fill_clean_interval(
        spec.peak_torque_rpm,
        spec.overspeed_rpm,
        post_extra,
        protected=protected,
        steps=RPM_STEPS,
    )
    result.extend(post)

    # If snapping/collisions left cells unused, fill the largest useful clean gaps.
    result = _unique_sorted(result)
    guard = 0
    while len(result) < count and guard < 100:
        guard += 1
        gaps = sorted(
            ((result[i + 1] - result[i], i) for i in range(len(result) - 1)),
            reverse=True,
        )
        placed = False
        for _, idx in gaps:
            lo, hi = result[idx], result[idx + 1]
            region_steps = RPM_STEPS
            candidates = _fill_clean_interval(
                lo,
                hi,
                1,
                protected=set(result),
                steps=region_steps,
            )
            if candidates:
                result.append(candidates[0])
                result = _unique_sorted(result)
                placed = True
                break
        if not placed:
            break

    if len(result) != count:
        raise ValueError(
            f"could not create {count} unique RPM cells; generated {len(result)}"
        )
    return result


def _nice_map_step(max_map: float, count: int) -> int:
    span = max(max_map - 20.0, 1.0)
    raw = span / max(count - 1, 1)
    return _nearest_step(raw, MAP_STEPS)


def _clean_map(value: float, step: int) -> float:
    return _snap(value, step)


def generate_load_axis(spec: EngineParameters, count: int) -> list[float]:
    """Generate a clean kPa-absolute load axis with mandatory 100-kPa crossover."""
    if count < 2:
        raise ValueError("load axis requires at least 2 cells")

    max_map_actual = max(spec.atm_kpa, spec.max_boost_map_kpa)
    provisional_step = _nice_map_step(max_map_actual + 20.0, count)

    if spec.boost_psi > 0.0:
        max_boost_anchor = _clean_map(max_map_actual, provisional_step)
        if max_boost_anchor <= spec.atm_kpa:
            max_boost_anchor = spec.atm_kpa + provisional_step
        overboost = max_boost_anchor + provisional_step
    else:
        max_boost_anchor = spec.atm_kpa
        overboost = spec.atm_kpa + provisional_step

    mandatory = _unique_sorted(
        [
            spec.map_floor_kpa,
            spec.vacuum_full_map_kpa,
            spec.atm_kpa,
            max_boost_anchor,
            overboost,
        ]
    )
    preferred = _unique_sorted(
        [
            spec.idle_map_lo,
            (spec.idle_map_lo + spec.idle_map_hi) / 2.0,
            spec.idle_map_hi,
            60.0,
            80.0,
        ]
    )

    result = list(mandatory)
    for value in preferred:
        if len(result) >= count:
            break
        if spec.map_floor_kpa <= value <= overboost and value not in result:
            result.append(value)
    result = _unique_sorted(result)

    if len(result) > count:
        # Keep mandatory values, then retain preferred values nearest the idle/vacuum region.
        keep = set(mandatory)
        extras = [v for v in result if v not in keep]
        extras.sort(key=lambda v: (abs(v - ((spec.idle_map_lo + spec.idle_map_hi) / 2.0)), v))
        result = _unique_sorted(list(keep) + extras[: max(0, count - len(keep))])

    step = _nice_map_step(overboost, count)
    ladder = [float(v) for v in range(int(spec.map_floor_kpa), int(overboost) + 1, step)]
    if float(round(spec.atm_kpa)) not in ladder:
        ladder.append(float(round(spec.atm_kpa)))
    ladder = _unique_sorted(ladder)

    while len(result) < count:
        result = _unique_sorted(result)
        best_candidate = None
        best_gap = -1.0
        for candidate in ladder:
            if candidate in result or candidate <= result[0] or candidate >= result[-1]:
                continue
            lower = max(v for v in result if v < candidate)
            upper = min(v for v in result if v > candidate)
            gap = upper - lower
            # Prefer filling the largest current gap; ties favor the lower MAP value.
            if gap > best_gap or (abs(gap - best_gap) < 1e-9 and (best_candidate is None or candidate < best_candidate)):
                best_gap = gap
                best_candidate = candidate
        if best_candidate is None:
            # Fall back to a finer clean ladder if necessary.
            finer = next((s for s in MAP_STEPS if s < step), None)
            if finer is None:
                break
            step = finer
            ladder = _unique_sorted(
                [float(v) for v in range(int(spec.map_floor_kpa), int(overboost) + 1, step)]
                + [spec.atm_kpa]
            )
            continue
        result.append(best_candidate)

    result = _unique_sorted(result)
    if len(result) != count:
        raise ValueError(
            f"could not create {count} unique load cells; generated {len(result)}"
        )
    if float(round(spec.atm_kpa)) not in result:
        raise AssertionError("atmosphere crossover was lost from load axis")
    return result
