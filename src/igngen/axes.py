"""Nonlinear RPM/load axis generation.

RPM columns use an explicit budget: after mandatory anchors, remaining
slots are split **2:1** between
  (above idle pocket → peak torque)  :  (peak torque → overspeed).

Mechanical advance starts at idle (not after the pocket); the dense zone
is where that climb is visible on the map.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import EngineSpec


@dataclass(frozen=True)
class Landmark:
    value: float
    priority: int
    label: str


def _as_int(v: float) -> float:
    return float(int(round(v)))


def _unique_sorted(values: list[float]) -> list[float]:
    out: list[float] = []
    for v in sorted(_as_int(x) for x in values):
        if not out or abs(out[-1] - v) >= 1:
            out.append(v)
    return out


def _even_interior(lo: float, hi: float, n: int) -> list[float]:
    """n distinct integer points strictly between lo and hi."""
    lo_i, hi_i = _as_int(lo), _as_int(hi)
    if n <= 0 or hi_i - lo_i <= 1:
        return []
    points: list[float] = []
    for i in range(1, n + 1):
        raw = lo_i + (hi_i - lo_i) * i / (n + 1)
        v = _as_int(raw)
        if v <= lo_i:
            v = lo_i + i
        if v >= hi_i:
            v = hi_i - (n + 1 - i)
        points.append(float(v))
    return _unique_sorted([p for p in points if lo_i < p < hi_i])


def generate_rpm_axis(spec: EngineSpec, count: int) -> list[float]:
    """Build RPM breakpoints with a 2:1 dense:sparse budget.

    Dense zone: above idle-pocket upper → peak torque (mech climb).
    Sparse zone: peak torque → overspeed (hold / soft later).
    Anchors always try to keep: cranking, idle, pocket upper, peak torque,
    redline, overspeed.
    """
    if count < 2:
        raise ValueError("axis count must be >= 2")

    idle = float(spec.idle_rpm)
    half = max(spec.idle_pocket_width / 2.0, 0.0)
    pocket_hi = idle + half
    tq = float(spec.peak_torque_rpm)
    redline = float(spec.redline_rpm)
    overspeed = redline + 1000.0
    cranking = 300.0

    # Ensure pocket_hi is past idle so "out of idle" is a real edge
    if pocket_hi <= idle:
        pocket_hi = idle + 100.0
    if tq <= pocket_hi + 50:
        # degenerate engine numbers — fall back to idle→tq dense
        pocket_hi = idle + max(50.0, (tq - idle) * 0.1)

    anchors = _unique_sorted([cranking, idle, pocket_hi, tq, redline, overspeed])

    # If too many anchors for the table, keep the essentials first
    if len(anchors) >= count:
        essential = _unique_sorted([cranking, idle, tq, redline, overspeed])
        if len(essential) >= count:
            # extreme small tables
            pick = [cranking, idle, tq, overspeed]
            return _unique_sorted(pick)[:count]
        # drop pocket_hi / extras until we fit
        while len(anchors) > count:
            # drop the least critical interior anchor (pocket_hi first if present)
            drop_candidates = [v for v in anchors if v not in {cranking, idle, tq, redline, overspeed}]
            if not drop_candidates:
                anchors = essential[:count]
                break
            anchors.remove(max(drop_candidates))  # drop highest non-essential (usually overspeed neighbor)
            # actually drop pocket_hi preferentially
            if pocket_hi in anchors and len(anchors) > count:
                anchors = [v for v in anchors if v != _as_int(pocket_hi)]
                anchors = _unique_sorted(anchors)
        return anchors[:count]

    remaining = count - len(anchors)
    # 2:1 — dense (pocket_hi → tq) : sparse (tq → overspeed)
    dense_slots = (remaining * 2) // 3
    sparse_slots = remaining - dense_slots

    dense = _even_interior(pocket_hi, tq, dense_slots)
    sparse = _even_interior(tq, overspeed, sparse_slots)

    axis = _unique_sorted(anchors + dense + sparse)

    # Top up if dedupe ate slots — prefer dense zone
    guard = 0
    while len(axis) < count and guard < 50:
        guard += 1
        # find largest gap in dense zone first
        best_i = None
        best_score = -1.0
        for i in range(len(axis) - 1):
            lo, hi = axis[i], axis[i + 1]
            span = hi - lo
            if span < 2:
                continue
            mid = (lo + hi) / 2.0
            if pocket_hi <= mid <= tq:
                score = span * 3.0
            elif mid > tq:
                score = span * 1.0
            else:
                score = span * 0.25
            if score > best_score:
                best_score = score
                best_i = i
        if best_i is None:
            axis.append(axis[-1] + 100)
        else:
            mid = _as_int((axis[best_i] + axis[best_i + 1]) / 2.0)
            if mid <= axis[best_i] or mid >= axis[best_i + 1]:
                axis.append(axis[-1] + 100)
            else:
                axis.insert(best_i + 1, mid)
        axis = _unique_sorted(axis)

    return axis[:count]


def describe_rpm_axis(spec: EngineSpec, axis: list[float]) -> str:
    idle = spec.idle_rpm
    half = spec.idle_pocket_width / 2.0
    pocket_hi = idle + half
    tq = spec.peak_torque_rpm
    dense = sum(1 for x in axis if pocket_hi < x < tq)
    sparse = sum(1 for x in axis if x > tq)
    return (
        f"RPM axis {len(axis)} cols — dense above pocket→peak TQ: {dense} interiors, "
        f"after peak TQ: {sparse} (target ~2:1 interiors)"
    )


def load_landmarks_kpa(spec: EngineSpec) -> list[Landmark]:
    atm = spec.atm_kpa
    max_boost_kpa = atm + spec.boost_psi * 6.895
    idle_map = 45.0
    return [
        Landmark(20, 80, "deep_vacuum"),
        Landmark(30, 70, "high_vacuum"),
        Landmark(idle_map, 90, "idle_map"),
        Landmark(60, 50, "part_throttle"),
        Landmark(80, 50, "high_part"),
        Landmark(atm, 100, "atmosphere"),
        Landmark(min(atm + 20, max_boost_kpa), 70, "light_boost"),
        Landmark(max_boost_kpa if spec.boost_psi > 0 else atm + 10, 90, "max_boost"),
        Landmark(35, 60, "idle_map_low"),
        Landmark(55, 60, "idle_map_high"),
    ]


def load_landmarks_inhg(spec: EngineSpec) -> list[Landmark]:
    max_boost = spec.boost_psi * 2.036 if spec.boost_psi > 0 else 10.0
    return [
        Landmark(-90.0, 80, "deep_vacuum"),
        Landmark(-55.0, 60, "high_vacuum"),
        Landmark(-31.0, 50, "mod_vacuum"),
        Landmark(-20.0, 70, "idle_ish"),
        Landmark(-10.0, 50, "light_vacuum"),
        Landmark(-2.5, 70, "near_atm_vac"),
        Landmark(0.0, 100, "atmosphere"),
        Landmark(2.5, 70, "near_atm_boost"),
        Landmark(13.5, 60, "light_boost"),
        Landmark(max_boost, 90, "max_boost"),
        Landmark(max_boost * 0.5, 50, "mid_boost"),
    ]


def select_axis(landmarks: list[Landmark], count: int) -> list[float]:
    """Legacy priority picker — used for load axes."""
    if count < 2:
        raise ValueError("axis count must be >= 2")

    best: dict[float, Landmark] = {}
    for lm in landmarks:
        key = _as_int(lm.value)
        if key not in best or lm.priority > best[key].priority:
            best[key] = Landmark(key, lm.priority, lm.label)
    ranked = sorted(best.values(), key=lambda x: (-x.priority, x.value))

    chosen: list[Landmark] = []
    for lm in ranked:
        if len(chosen) >= count:
            break
        if any(abs(lm.value - c.value) < 1e-6 for c in chosen):
            continue
        chosen.append(lm)

    values = sorted(c.value for c in chosen)
    while len(values) < count:
        gaps = [(values[i + 1] - values[i], i) for i in range(len(values) - 1)]
        gaps.sort(reverse=True)
        if not gaps or gaps[0][0] <= 1:
            break
        _, i = gaps[0]
        mid = _as_int((values[i] + values[i + 1]) / 2.0)
        if mid <= values[i] or mid >= values[i + 1] or mid in values:
            mid = values[i] + 1
            if mid >= values[i + 1]:
                break
        values.insert(i + 1, mid)
        values = _unique_sorted(values)

    while len(values) < count:
        values.append(values[-1] + 100)
        values = _unique_sorted(values)

    return values[:count]


def generate_load_axis(spec: EngineSpec, count: int, *, unit: str = "kPa") -> list[float]:
    if unit.lower() in {"inhg", "inhg_gauge"}:
        return select_axis(load_landmarks_inhg(spec), count)
    return select_axis(load_landmarks_kpa(spec), count)


def example_axes_for_docs(spec: EngineSpec | None = None) -> dict[str, list[float]]:
    spec = spec or EngineSpec()
    return {
        "rpm_8": generate_rpm_axis(spec, 8),
        "rpm_12": generate_rpm_axis(spec, 12),
        "rpm_16": generate_rpm_axis(spec, 16),
        "load_kpa_8": generate_load_axis(spec, 8, unit="kPa"),
        "load_kpa_12": generate_load_axis(spec, 12, unit="kPa"),
    }
