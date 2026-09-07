"""Nonlinear RPM/load axis generation.

RPM columns: low anchors always include the idle **pocket**
(cranking @500, pocket lower, idle, pocket upper). Remaining slots split **2:1**:
  2 — (above idle pocket → peak torque]  (mechanical climb)
  1 — (peak torque → overspeed]          (hold / soft later)

Profile / user landmarks stay exact. Generated filler RPMs snap to
increments of 50.

Load axis: landmarks through vehicle max boost/MAP (from the loaded
profile — any engine / edited defaults), plus **one overboost** row.
Overboost is **one logical round past** how max MAP "reads" on the
boost-region round ladder (not max+constant):
  snap max to nearest logical round (midpoint; ties read up),
  then take the next logical round after that.
Example: ~172 kPa reads as 180 → overboost **200**.
Ceiling stops there; no filler walk past overboost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .model import EngineSpec

RPM_FILL_STEP = 50
KPA_PER_PSI = 6.895
# Spacing of the *logical round ladder* above atmosphere (not "add N to max").
LOGICAL_MAP_LADDER_KPA = 20.0
LOGICAL_MAP_LADDER_INHG = 5.0


@dataclass(frozen=True)
class Landmark:
    value: float
    priority: int
    label: str


def _as_int(v: float) -> float:
    return float(int(round(v)))


def _snap_rpm(v: float, *, step: int = RPM_FILL_STEP) -> float:
    """Round to nearest step (default 50 RPM)."""
    return float(int(round(v / step) * step))


def _logical_rounds_above(start: float, ladder: float, past: float) -> list[float]:
    """Ascending logical round ladder from `start`, extending past `past`."""
    rounds: list[float] = []
    v = float(start)
    # enough headroom for snap + one step over
    limit = float(past) + 4 * ladder
    while v <= limit:
        rounds.append(float(int(round(v))))
        v += ladder
    return rounds


def _snap_to_logical(value: float, rounds: list[float]) -> float:
    """Nearest logical round; exact midpoint ties read upward."""
    v = float(value)
    if not rounds:
        return _as_int(v)
    # Find neighboring rounds
    lo = rounds[0]
    hi = rounds[-1]
    for i, r in enumerate(rounds):
        if r <= v:
            lo = r
        if r >= v:
            hi = r
            break
    if lo == hi:
        return float(lo)
    mid = (lo + hi) / 2.0
    # at/above mid → higher round ("read up")
    return float(hi if v >= mid else lo)


def _overboost_from_logical(value: float, rounds: list[float]) -> float:
    """One logical step over how `value` reads on the round ladder."""
    snapped = _snap_to_logical(value, rounds)
    for r in rounds:
        if r > snapped + 1e-9:
            return float(r)
    # extend one more ladder step if we ran out
    if len(rounds) >= 2:
        return float(rounds[-1] + (rounds[-1] - rounds[-2]))
    return float(snapped + LOGICAL_MAP_LADDER_KPA)


def _unique_sorted(values: list[float], *, min_gap: float = 1.0) -> list[float]:
    out: list[float] = []
    for v in sorted(_as_int(x) for x in values):
        if not out or abs(out[-1] - v) >= min_gap:
            out.append(v)
    return out


def _fill_between(
    lo: float,
    hi: float,
    n: int,
    *,
    include_hi: bool = True,
    snap: bool = True,
    forbidden: set[float] | None = None,
) -> list[float]:
    """Place n points in (lo, hi], optionally keeping hi exact and snapping fillers."""
    lo_i, hi_i = _as_int(lo), _as_int(hi)
    forbidden = {_as_int(x) for x in (forbidden or set())}
    if n <= 0:
        return []
    if n == 1 and include_hi:
        return [hi_i]
    if hi_i <= lo_i + 1:
        return [hi_i] if include_hi and n >= 1 else []

    interior_n = n - 1 if include_hi else n
    points: list[float] = []
    for i in range(1, interior_n + 1):
        raw = lo_i + (hi_i - lo_i) * i / (interior_n + 1)
        v = _snap_rpm(raw) if snap else _as_int(raw)
        if v <= lo_i:
            v = _snap_rpm(lo_i + RPM_FILL_STEP) if snap else lo_i + 1
        if v >= hi_i:
            v = _snap_rpm(hi_i - RPM_FILL_STEP) if snap else hi_i - 1
        if v <= lo_i or v >= hi_i:
            continue
        if v in forbidden:
            continue
        points.append(float(v))
    if include_hi:
        points.append(hi_i)
    return _unique_sorted(points, min_gap=float(RPM_FILL_STEP if snap else 1))[:n]


def _pocket_edges(spec: EngineSpec) -> tuple[float, float]:
    """Idle pocket lower/upper RPM.

    ``idle_pocket_width`` is **±RPM from idle** (not total span).
    e.g. idle 750, width 100 → 650 / 750 / 850.
    """
    idle = float(spec.idle_rpm)
    half = max(float(spec.idle_pocket_width), 1.0)
    pocket_lo = idle - half
    pocket_hi = idle + half
    cranking = float(getattr(spec, "cranking_rpm", 500.0))
    if pocket_lo <= cranking:
        pocket_lo = cranking + max(50.0, half * 0.5)
    if pocket_hi <= idle:
        pocket_hi = idle + half
    return float(pocket_lo), float(pocket_hi)


def generate_rpm_axis(spec: EngineSpec, count: int) -> list[float]:
    if count < 2:
        raise ValueError("axis count must be >= 2")

    idle = float(spec.idle_rpm)
    pocket_lo, pocket_hi = _pocket_edges(spec)
    tq = float(spec.peak_torque_rpm)
    redline = float(spec.redline_rpm)
    overspeed = redline + 1000.0
    cranking = float(getattr(spec, "cranking_rpm", 500.0))

    if tq <= pocket_hi + 100:
        pocket_hi = idle + max(50.0, (tq - idle) * 0.1)
        pocket_lo = min(pocket_lo, idle - max(50.0, (idle - cranking) * 0.25))

    specified = {
        _as_int(cranking),
        _as_int(pocket_lo),
        _as_int(idle),
        _as_int(pocket_hi),
        _as_int(tq),
        _as_int(redline),
        _as_int(overspeed),
    }

    low = _unique_sorted([cranking, pocket_lo, idle, pocket_hi], min_gap=40.0)

    if len(low) >= count:
        essential = _unique_sorted(
            [cranking, pocket_lo, idle, pocket_hi, tq, overspeed], min_gap=40.0
        )
        return essential[:count]

    remaining = count - len(low)
    dense_n = max(1, (remaining * 2) // 3)
    sparse_n = max(1, remaining - dense_n)
    if dense_n + sparse_n > remaining:
        sparse_n = remaining - dense_n

    dense = _fill_between(
        pocket_hi, tq, dense_n, include_hi=True, snap=True, forbidden=specified
    )
    if tq not in dense and dense_n >= 1:
        dense = _unique_sorted(dense + [tq], min_gap=40.0)[:dense_n]

    sparse_compulsory = [v for v in _unique_sorted([redline, overspeed], min_gap=50.0) if v > tq]
    if len(sparse_compulsory) >= sparse_n:
        sparse = [v for v in sparse_compulsory if v > tq][-sparse_n:]
    else:
        fill = sparse_n - len(sparse_compulsory)
        mids = _fill_between(
            tq,
            redline if redline > tq + 50 else overspeed,
            fill,
            include_hi=False,
            snap=True,
            forbidden=specified | set(sparse_compulsory),
        )
        sparse = _unique_sorted(mids + sparse_compulsory, min_gap=50.0)
        while len(sparse) > sparse_n:
            protected = {_as_int(redline), _as_int(overspeed)}
            droppable = [v for v in sparse if v not in protected]
            if not droppable:
                sparse = sparse[:sparse_n]
                break
            sparse = [v for v in sparse if v != droppable[0]]
        guard = 0
        while len(sparse) < sparse_n and guard < 20:
            guard += 1
            seq = _unique_sorted([tq] + sparse + [overspeed], min_gap=1.0)
            best = None
            best_span = 0.0
            for i in range(len(seq) - 1):
                span = seq[i + 1] - seq[i]
                if span > best_span:
                    best_span = span
                    best = i
            if best is None or best_span < 100:
                cand = _snap_rpm((sparse[-1] if sparse else tq) + 100)
            else:
                cand = _snap_rpm((seq[best] + seq[best + 1]) / 2.0)
            if cand > tq and cand not in sparse and cand not in specified:
                sparse.append(cand)
            elif cand in specified or cand in sparse:
                cand = _snap_rpm(cand + RPM_FILL_STEP)
                if cand > tq and cand < overspeed:
                    sparse.append(cand)
            sparse = _unique_sorted([v for v in sparse if v > tq], min_gap=50.0)

    axis = _unique_sorted(low + dense + sparse, min_gap=40.0)

    guard = 0
    while len(axis) < count and guard < 40:
        guard += 1
        best_i = None
        best_score = -1.0
        for i in range(len(axis) - 1):
            lo, hi = axis[i], axis[i + 1]
            span = hi - lo
            if span < 100:
                continue
            mid = (lo + hi) / 2.0
            if pocket_hi < mid <= tq:
                score = span * 3.0
            elif mid > tq:
                score = span * 1.0
            else:
                score = span * 0.2
            if score > best_score:
                best_score = score
                best_i = i
        if best_i is None:
            axis.append(_snap_rpm(axis[-1] + 100))
        else:
            mid = _snap_rpm((axis[best_i] + axis[best_i + 1]) / 2.0)
            if mid <= axis[best_i] or mid >= axis[best_i + 1] or mid in specified:
                placed = False
                for delta in (0, RPM_FILL_STEP, -RPM_FILL_STEP, 2 * RPM_FILL_STEP):
                    cand = _snap_rpm(mid + delta)
                    if axis[best_i] < cand < axis[best_i + 1] and cand not in axis:
                        axis.insert(best_i + 1, cand)
                        placed = True
                        break
                if not placed:
                    axis.append(_snap_rpm(axis[-1] + 100))
            else:
                axis.insert(best_i + 1, mid)
        axis = _unique_sorted(axis, min_gap=40.0)

    if len(axis) > count:
        protected = set(specified)
        while len(axis) > count:
            droppable = [v for v in axis if v not in protected and v > tq]
            if not droppable:
                droppable = [v for v in axis if v not in protected]
            if not droppable:
                axis = axis[:count]
                break
            axis.remove(droppable[0])

    return axis[:count]


def describe_rpm_axis(spec: EngineSpec, axis: list[float]) -> str:
    pocket_lo, pocket_hi = _pocket_edges(spec)
    tq = spec.peak_torque_rpm
    dense = sum(1 for x in axis if pocket_hi < x <= tq)
    sparse = sum(1 for x in axis if x > tq)
    return (
        f"RPM axis {len(axis)} cols — idle pocket "
        f"{int(pocket_lo)}…{int(spec.idle_rpm)}…{int(pocket_hi)}, "
        f"climb: {dense}, after peak TQ: {sparse} (budget 2:1; fillers ×{RPM_FILL_STEP})"
    )


def _max_load_kpa(spec: EngineSpec) -> float:
    """Highest profile MAP (kPa abs). NA (boost_psi=0) stops at atmosphere."""
    atm = spec.atm_kpa
    if spec.boost_psi > 0:
        return atm + spec.boost_psi * KPA_PER_PSI
    return float(atm)


def _max_load_inhg(spec: EngineSpec) -> float:
    """Highest profile boost (inHg gauge). NA → 0 (atmosphere)."""
    if spec.boost_psi > 0:
        return spec.boost_psi * 2.036
    return 0.0


def _overboost_kpa(spec: EngineSpec) -> float:
    """Overboost = one logical MAP round past how profile max reads."""
    max_map = _max_load_kpa(spec)
    atm = float(spec.atm_kpa)
    rounds = _logical_rounds_above(atm, LOGICAL_MAP_LADDER_KPA, max_map)
    return _overboost_from_logical(max_map, rounds)


def _overboost_inhg(spec: EngineSpec) -> float:
    """Overboost = one logical inHg round past how profile max reads."""
    max_b = _max_load_inhg(spec)
    rounds = _logical_rounds_above(0.0, LOGICAL_MAP_LADDER_INHG, max_b)
    return _overboost_from_logical(max_b, rounds)


def load_landmarks_kpa(spec: EngineSpec) -> list[Landmark]:
    atm = spec.atm_kpa
    max_boost_kpa = _max_load_kpa(spec)
    overboost = _overboost_kpa(spec)
    idle_map = 45.0
    marks = [
        Landmark(20, 100, "deep_vacuum"),
        Landmark(30, 70, "high_vacuum"),
        Landmark(idle_map, 90, "idle_map"),
        Landmark(35, 60, "idle_map_low"),
        Landmark(55, 60, "idle_map_high"),
        Landmark(60, 50, "part_throttle"),
        Landmark(80, 50, "high_part"),
        Landmark(atm, 100, "atmosphere"),
    ]
    # Boosted: light + max MAP. NA: only the single over-atm overboost row.
    if spec.boost_psi > 0:
        light = min(atm + 20, max_boost_kpa)
        if light > atm + 1e-9:
            marks.append(Landmark(light, 70, "light_boost"))
        if max_boost_kpa > atm + 1e-9:
            marks.append(Landmark(max_boost_kpa, 100, "max_boost"))
    if overboost > atm + 1e-9:
        marks.append(Landmark(overboost, 95, "overboost"))
    return marks


def load_landmarks_inhg(spec: EngineSpec) -> list[Landmark]:
    max_boost = _max_load_inhg(spec)
    overboost = _overboost_inhg(spec)
    marks = [
        Landmark(-90.0, 80, "deep_vacuum"),
        Landmark(-55.0, 60, "high_vacuum"),
        Landmark(-31.0, 50, "mod_vacuum"),
        Landmark(-20.0, 70, "idle_ish"),
        Landmark(-10.0, 50, "light_vacuum"),
        Landmark(-2.5, 70, "near_atm_vac"),
        Landmark(0.0, 100, "atmosphere"),
    ]
    if spec.boost_psi > 0:
        marks.append(Landmark(2.5, 70, "near_atm_boost"))
        light = min(13.5, max_boost)
        if light > 1e-9:
            marks.append(Landmark(light, 60, "light_boost"))
        if max_boost > 1e-9:
            marks.append(Landmark(max_boost, 100, "max_boost"))
            marks.append(Landmark(max_boost * 0.5, 50, "mid_boost"))
    if overboost > 1e-9:
        marks.append(Landmark(overboost, 95, "overboost"))
    return marks


def select_axis(
    landmarks: list[Landmark],
    count: int,
    *,
    ceiling: float | None = None,
    floor: float | None = None,
    no_fill_above: float | None = None,
) -> list[float]:
    """Pick landmarks then fill gaps. Never extends past ceiling (if set).

    ``no_fill_above``: never insert fillers strictly above this value (ceiling
    tip may still be pinned). Used for NA load axes so atm→overboost stays a
    single step no matter how large ``count`` is — extra rows densify below.
    """
    if count < 2:
        raise ValueError("axis count must be >= 2")

    ceil = _as_int(ceiling) if ceiling is not None else None
    fl = _as_int(floor) if floor is not None else None
    nfa = float(no_fill_above) if no_fill_above is not None else None

    best: dict[float, Landmark] = {}
    for lm in landmarks:
        key = _as_int(lm.value)
        if ceil is not None and key > ceil:
            continue
        if fl is not None and key < fl:
            continue
        # Drop mid-boost landmarks when NA tip-only region is active
        if nfa is not None and key > nfa + 1e-9 and (ceil is None or abs(key - ceil) > 1e-9):
            continue
        if key not in best or lm.priority > best[key].priority:
            best[key] = Landmark(key, lm.priority, lm.label)

    # Always pin floor/ceiling when provided
    if fl is not None:
        best[fl] = Landmark(fl, 100, "floor")
    if ceil is not None:
        best[ceil] = Landmark(ceil, 100, "ceiling")

    ranked = sorted(best.values(), key=lambda x: (-x.priority, x.value))

    chosen: list[Landmark] = []
    for lm in ranked:
        if len(chosen) >= count:
            break
        if any(abs(lm.value - c.value) < 1e-6 for c in chosen):
            continue
        chosen.append(lm)

    values = sorted(c.value for c in chosen)

    def _split_largest_gap() -> bool:
        gaps = [(values[i + 1] - values[i], i) for i in range(len(values) - 1)]
        gaps.sort(reverse=True)
        for gap_size, i in gaps:
            if gap_size <= 1:
                return False
            # Do not densify above the NA atmosphere fence
            if nfa is not None and values[i] >= nfa - 1e-9:
                continue
            mid = _as_int((values[i] + values[i + 1]) / 2.0)
            if mid <= values[i] or mid >= values[i + 1] or mid in values:
                mid = values[i] + 1
                if mid >= values[i + 1]:
                    continue
            if nfa is not None and mid > nfa + 1e-9:
                continue
            if ceil is not None and mid > ceil:
                continue
            if fl is not None and mid < fl:
                continue
            values.insert(i + 1, mid)
            return True
        return False

    while len(values) < count:
        if not _split_largest_gap():
            break
        values[:] = _unique_sorted(values)

    guard = 0
    while len(values) < count and guard < 40:
        guard += 1
        if not _split_largest_gap():
            break
        values[:] = _unique_sorted(values)

    if ceil is not None:
        values = [v for v in values if v <= ceil]
    if fl is not None:
        values = [v for v in values if v >= fl]
    values = _unique_sorted(values)
    return [float(v) for v in values[:count]]



def generate_load_axis(spec: EngineSpec, count: int, *, unit: str = "kPa") -> list[float]:
    """Build load breakpoints (landmark priority + gap fill, like RPM).

    NA (``boost_psi == 0``): atmosphere is a fence — fillers densify at/below
    it for any table size (12, 24, …); exactly one tip row sits above (overboost).
    """
    if unit.lower() in {"inhg", "inhg_gauge"}:
        floor = -90.0
        over = _overboost_inhg(spec)
        marks = load_landmarks_inhg(spec)
        nfa = 0.0 if spec.boost_psi <= 0 else None
        return select_axis(
            marks, count, floor=floor, ceiling=over, no_fill_above=nfa
        )

    floor = 20.0
    atm = float(spec.atm_kpa)
    over = _overboost_kpa(spec)
    marks = load_landmarks_kpa(spec)
    nfa = atm if spec.boost_psi <= 0 else None
    return select_axis(
        marks, count, floor=floor, ceiling=over, no_fill_above=nfa
    )

def example_axes_for_docs(spec: EngineSpec | None = None) -> dict[str, list[float]]:
    spec = spec or EngineSpec()
    return {
        "rpm_8": generate_rpm_axis(spec, 8),
        "rpm_12": generate_rpm_axis(spec, 12),
        "rpm_16": generate_rpm_axis(spec, 16),
        "load_kpa_8": generate_load_axis(spec, 8, unit="kPa"),
        "load_kpa_12": generate_load_axis(spec, 12, unit="kPa"),
    }
