"""Nonlinear RPM/load axis generation.

RPM columns: after low anchors (cranking, idle, pocket upper), remaining
slots are split **2:1** by zone:
  2 — (above idle pocket → peak torque]  (mechanical climb)
  1 — (peak torque → overspeed]          (hold / soft later)

Mechanical advance starts at idle (linear); the pocket is not a freeze on the RPM curve.
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


def _unique_sorted(values: list[float], *, min_gap: float = 1.0) -> list[float]:
    out: list[float] = []
    for v in sorted(_as_int(x) for x in values):
        if not out or abs(out[-1] - v) >= min_gap:
            out.append(v)
    return out


def _even_inclusive_end(lo: float, hi: float, n: int) -> list[float]:
    """n points in (lo, hi], always including hi when n >= 1."""
    lo_i, hi_i = _as_int(lo), _as_int(hi)
    if n <= 0:
        return []
    if n == 1:
        return [hi_i]
    if hi_i <= lo_i + 1:
        return [hi_i]
    points: list[float] = []
    for i in range(1, n):
        raw = lo_i + (hi_i - lo_i) * i / n
        v = _as_int(raw)
        if v <= lo_i:
            v = lo_i + i
        if v >= hi_i:
            v = hi_i - (n - i)
        points.append(float(v))
    points.append(hi_i)
    return _unique_sorted([p for p in points if p > lo_i], min_gap=50.0)[:n]


def generate_rpm_axis(spec: EngineSpec, count: int) -> list[float]:
    if count < 2:
        raise ValueError("axis count must be >= 2")

    idle = float(spec.idle_rpm)
    half = max(spec.idle_pocket_width / 2.0, 0.0)
    pocket_hi = idle + half
    tq = float(spec.peak_torque_rpm)
    redline = float(spec.redline_rpm)
    overspeed = redline + 1000.0
    cranking = 300.0

    if pocket_hi <= idle:
        pocket_hi = idle + 100.0
    if tq <= pocket_hi + 100:
        pocket_hi = idle + max(50.0, (tq - idle) * 0.1)

    low = _unique_sorted([cranking, idle, pocket_hi], min_gap=50.0)

    if len(low) >= count:
        return _unique_sorted([cranking, idle, tq, overspeed], min_gap=50.0)[:count]

    remaining = count - len(low)
    dense_n = max(1, (remaining * 2) // 3)  # (pocket_hi, tq]
    sparse_n = max(1, remaining - dense_n)  # (tq, overspeed]
    if dense_n + sparse_n > remaining:
        sparse_n = remaining - dense_n

    dense = _even_inclusive_end(pocket_hi, tq, dense_n)

    sparse_compulsory = [v for v in _unique_sorted([redline, overspeed], min_gap=50.0) if v > tq]
    if len(sparse_compulsory) >= sparse_n:
        sparse = [v for v in _unique_sorted([redline, overspeed], min_gap=50.0) if v > tq][
            -sparse_n:
        ]
    else:
        fill = sparse_n - len(sparse_compulsory)
        mids: list[float] = []
        if fill > 0:
            top = redline if redline > tq + 50 else overspeed
            extra = 1 if top not in sparse_compulsory else 0
            mids = _even_inclusive_end(tq, top, fill + extra)
            mids = [v for v in mids if v not in sparse_compulsory and v > tq][:fill]
        sparse = _unique_sorted(mids + sparse_compulsory, min_gap=75.0)
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
                sparse.append(sparse[-1] + 100 if sparse else tq + 100)
            else:
                mid = _as_int((seq[best] + seq[best + 1]) / 2.0)
                if mid > tq:
                    sparse.append(mid)
            sparse = _unique_sorted([v for v in sparse if v > tq], min_gap=75.0)

    axis = _unique_sorted(low + dense + sparse, min_gap=50.0)

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
            axis.append(axis[-1] + 100)
        else:
            mid = _as_int((axis[best_i] + axis[best_i + 1]) / 2.0)
            axis.insert(best_i + 1, mid)
        axis = _unique_sorted(axis, min_gap=50.0)

    if len(axis) > count:
        protected = {
            _as_int(cranking),
            _as_int(idle),
            _as_int(pocket_hi),
            _as_int(tq),
            _as_int(redline),
            _as_int(overspeed),
        }
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
    idle = spec.idle_rpm
    half = spec.idle_pocket_width / 2.0
    pocket_hi = idle + half
    tq = spec.peak_torque_rpm
    dense = sum(1 for x in axis if pocket_hi < x <= tq)
    sparse = sum(1 for x in axis if x > tq)
    return (
        f"RPM axis {len(axis)} cols — climb (above pocket→peak TQ): {dense}, "
        f"after peak TQ: {sparse} (budget 2:1)"
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
