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
    if count < 2:
        raise ValueError("RPM axis requires at least 2 cells")

    anchors = _rpm_structural_anchors(spec)
    if len(anchors) > count:
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

    post = _fill_clean_interval(
        spec.peak_torque_rpm,
        spec.overspeed_rpm,
        post_extra,
        protected=protected,
        steps=RPM_STEPS,
    )
    result.extend(post)

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
            candidates = _fill_clean_interval(
                lo,
                hi,
                1,
                protected=set(result),
                steps=RPM_STEPS,
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


def _nice_map_step(span: float, count: int) -> int:
    raw = max(span, 1.0) / max(count - 1, 1)
    return _nearest_step(raw, MAP_STEPS)


def _clean_map(value: float, step: int) -> float:
    return _snap(value, step)


def _decel_anchor(spec: EngineParameters) -> float:
    """One clean row below the lowest normal idle-MAP boundary."""
    idle_lo = float(spec.idle_map_lo)
    step = 10 if idle_lo >= 30 else 5
    candidate = math.floor((idle_lo - step) / step) * step
    return float(max(5.0, candidate))


def _load_ladder(lo: float, hi: float, step: int) -> list[float]:
    start = int(math.ceil(lo / step) * step)
    end = int(math.floor(hi / step) * step)
    if end < start:
        return []
    return [float(v) for v in range(start, end + 1, step)]


def _select_evenly(candidates: list[float], count: int) -> list[float]:
    """Choose evenly distributed candidates without manufacturing odd breakpoints."""
    values = sorted(set(candidates))
    if count <= 0:
        return []
    if len(values) <= count:
        return values
    if count == 1:
        return [values[len(values) // 2]]

    selected: list[float] = []
    available = set(values)
    ideals = [i * (len(values) - 1) / (count - 1) for i in range(count)]
    for ideal in ideals:
        target = values[int(round(ideal))]
        candidate = min(available, key=lambda x: (abs(x - target), x))
        selected.append(candidate)
        available.remove(candidate)
    return sorted(selected)


def generate_load_axis(spec: EngineParameters, count: int) -> list[float]:
    """Generate a tuner-oriented MAP axis in kPa absolute.

    Policy:
      * exactly one structural row below the lowest normal idle MAP for decel;
      * preserve idle MAP low/mid/high landmarks when table size permits;
      * place no discretionary rows below or inside the idle band;
      * spend discretionary NA resolution above idle toward 100 kPa;
      * always preserve 100 kPa as the atmosphere crossover;
      * for boosted engines, preserve max boost and one overboost row and spend
        remaining rows cleanly between atmosphere and max boost.
    """
    if count < 2:
        raise ValueError("load axis requires at least 2 cells")

    atm = float(round(spec.atm_kpa))
    idle_lo = float(round(spec.idle_map_lo))
    idle_hi = float(round(spec.idle_map_hi))
    if idle_hi < idle_lo:
        idle_lo, idle_hi = idle_hi, idle_lo
    idle_mid = float(round((idle_lo + idle_hi) / 2.0))
    decel = _decel_anchor(spec)

    boosted = spec.boost_psi > 0.0
    if boosted:
        boost_span = max(spec.max_boost_map_kpa - atm, 1.0)
        boost_step = _nice_map_step(boost_span, max(3, count // 3))
        max_boost = _clean_map(spec.max_boost_map_kpa, boost_step)
        if max_boost <= atm:
            max_boost = atm + boost_step
        overboost = max_boost + boost_step
    else:
        max_boost = atm
        overboost = atm + 5.0

    priority = [decel, idle_lo, idle_mid, idle_hi, atm]
    if boosted:
        priority.extend([max_boost, overboost])
    else:
        priority.append(overboost)

    result: list[float] = []
    for value in priority:
        value = float(round(value))
        if value not in result:
            result.append(value)
        if len(result) == count:
            return sorted(result)

    result = _unique_sorted(result)
    remaining = count - len(result)

    if remaining > 0:
        upper_start = max(idle_hi, decel)
        na_span = max(atm - upper_start, 1.0)
        if boosted:
            boost_span = max(max_boost - atm, 1.0)
            na_extra = int(round(remaining * na_span / (na_span + 0.65 * boost_span)))
            na_extra = max(0, min(remaining, na_extra))
            boost_extra = remaining - na_extra
        else:
            na_extra = remaining
            boost_extra = 0

        na_step = _nice_map_step(na_span, max(na_extra + 2, 2))
        na_candidates = [
            v
            for v in _load_ladder(upper_start, atm, na_step)
            if upper_start < v < atm and v not in result
        ]
        result.extend(_select_evenly(na_candidates, na_extra))

        if boosted and boost_extra > 0:
            boost_candidates = [
                v
                for v in _load_ladder(atm, max_boost, boost_step)
                if atm < v < max_boost and v not in result
            ]
            result.extend(_select_evenly(boost_candidates, boost_extra))

    result = _unique_sorted(result)

    # If a coarse clean ladder cannot satisfy a large requested table, refine only
    # above the idle band. The idle box itself keeps just lo/mid/hi, and only the
    # single decel row is permitted below idle_lo.
    for step in (5, 2, 1):
        if len(result) >= count:
            break
        candidates = [
            v
            for v in _load_ladder(idle_hi, overboost, step)
            if v not in result and idle_hi < v < overboost
        ]
        while len(result) < count and candidates:
            gaps: list[tuple[float, float]] = []
            for candidate in candidates:
                lower = max((v for v in result if v < candidate), default=result[0])
                upper = min((v for v in result if v > candidate), default=result[-1])
                gaps.append((upper - lower, candidate))
            _, candidate = max(gaps, key=lambda item: (item[0], -item[1]))
            result.append(candidate)
            result = _unique_sorted(result)
            candidates.remove(candidate)

    if len(result) != count:
        raise ValueError(
            f"could not create {count} unique load cells; generated {len(result)}"
        )
    if atm not in result:
        raise AssertionError("atmosphere crossover was lost from load axis")

    below_idle = [value for value in result if value < idle_lo]
    if len(below_idle) > 1:
        raise AssertionError("load axis allocated more than one row below idle MAP")

    inside_idle = [value for value in result if idle_lo < value < idle_hi]
    allowed_inside = {idle_mid}
    if any(value not in allowed_inside for value in inside_idle):
        raise AssertionError("load axis allocated discretionary rows inside idle MAP band")

    return result
