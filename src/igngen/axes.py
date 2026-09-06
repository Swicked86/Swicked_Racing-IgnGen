"""Nonlinear, landmark-priority axis generation (audio-scale philosophy).

Density follows rate-of-change of the timing model — especially the
mechanical advance ramp (idle → peak torque) — not raw RPM span.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import EngineSpec


@dataclass(frozen=True)
class Landmark:
    value: float
    priority: int
    label: str


def rpm_landmarks(spec: EngineSpec) -> list[Landmark]:
    """RPM breakpoints ranked for selection into a fixed column count.

    Mechanical advance is flat at idle and flat after peak torque, so those
    zones get fewer slots. The idle→peak-torque ramp gets the densest set.
    Idle-pocket edges stay medium priority until the pocket layer is active.
    """
    idle = spec.idle_rpm
    tq = spec.peak_torque_rpm
    half = spec.idle_pocket_width / 2.0
    soft = spec.redline_rpm - spec.soft_limit_rpm_before_redline
    overspeed = spec.redline_rpm + 1000.0
    span = max(tq - idle, 1.0)

    return [
        # Mandatory anchors
        Landmark(300, 100, "cranking"),
        Landmark(idle, 100, "idle_target"),
        Landmark(tq, 100, "peak_torque"),
        Landmark(spec.redline_rpm, 95, "redline"),
        Landmark(overspeed, 90, "overspeed"),
        # Mechanical ramp — high priority so they survive on 12/16 tables
        Landmark(idle + 0.20 * span, 92, "mech_ramp_20"),
        Landmark(idle + 0.40 * span, 92, "mech_ramp_40"),
        Landmark(idle + 0.60 * span, 92, "mech_ramp_60"),
        Landmark(idle + 0.80 * span, 92, "mech_ramp_80"),
        Landmark(idle + min(200.0, 0.08 * span), 75, "off_idle"),
        # Idle pocket edges — useful later; don't steal ramp slots on small tables
        Landmark(max(400.0, idle - half), 55, "idle_lower"),
        Landmark(idle + half, 55, "idle_upper"),
        # Post-peak / soft — sparse; timing holds flat on mechanical layer
        Landmark(spec.peak_hp_rpm, 45, "peak_hp"),
        Landmark(soft, 40, "soft_limit"),
        Landmark((tq + soft) / 2.0, 30, "post_tq_mid"),
    ]


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


def _rpm_gap_score(lo: float, hi: float, spec: EngineSpec) -> float:
    """Prefer splitting gaps where mechanical timing is changing."""
    span = hi - lo
    if span <= 0:
        return 0.0
    mid = (lo + hi) / 2.0
    idle = spec.idle_rpm
    tq = spec.peak_torque_rpm
    soft = spec.redline_rpm - spec.soft_limit_rpm_before_redline

    if mid <= idle:
        weight = 0.35  # below idle — mostly flat base
    elif mid < tq:
        weight = 3.0  # mechanical ramp — highest density
    elif mid < soft:
        weight = 0.35  # post-peak hold — sparse
    else:
        weight = 0.7  # soft / overspeed — some resolution
    return span * weight


def _load_gap_score(lo: float, hi: float, spec: EngineSpec) -> float:
    span = hi - lo
    if span <= 0:
        return 0.0
    mid = (lo + hi) / 2.0
    atm = spec.atm_kpa
    # denser near atmosphere crossover and idle MAP band
    if abs(mid - atm) <= 25:
        weight = 2.0
    elif mid < 70:
        weight = 1.4
    else:
        weight = 1.0
    return span * weight


def select_axis(
    landmarks: list[Landmark],
    count: int,
    *,
    gap_score=None,
    spec: EngineSpec | None = None,
) -> list[float]:
    if count < 2:
        raise ValueError("axis count must be >= 2")

    best: dict[float, Landmark] = {}
    for lm in landmarks:
        key = float(int(round(lm.value)))
        if key not in best or lm.priority > best[key].priority:
            best[key] = Landmark(key, lm.priority, lm.label)
    ranked = sorted(best.values(), key=lambda x: (-x.priority, x.value))

    chosen: list[Landmark] = []
    for lm in ranked:
        if len(chosen) >= count:
            break
        if any(abs(lm.value - c.value) < 1e-6 for c in chosen):
            continue
        # Skip near-duplicates (within 2% of neighbor span or 75 RPM)
        if any(abs(lm.value - c.value) < 75 for c in chosen):
            # allow if both are very high priority anchors
            if lm.priority < 95:
                continue
        chosen.append(lm)

    values = sorted(c.value for c in chosen)

    def _score(lo: float, hi: float) -> float:
        if gap_score is not None and spec is not None:
            return float(gap_score(lo, hi, spec))
        return hi - lo

    while len(values) < count:
        gaps = [(_score(values[i], values[i + 1]), i) for i in range(len(values) - 1)]
        gaps.sort(reverse=True)
        if not gaps or gaps[0][0] <= 0:
            break
        _, i = gaps[0]
        mid = float(int(round((values[i] + values[i + 1]) / 2.0)))
        if mid in values or mid <= values[i] or mid >= values[i + 1]:
            mid = values[i] + 1
            if mid >= values[i + 1]:
                break
        values.insert(i + 1, mid)

    values = sorted(set(float(int(round(v))) for v in values))
    while len(values) < count:
        # Prefer filling the highest-scoring remaining gap
        if len(values) >= 2:
            gaps = [(_score(values[i], values[i + 1]), i) for i in range(len(values) - 1)]
            gaps.sort(reverse=True)
            _, i = gaps[0]
            mid = float(int(round((values[i] + values[i + 1]) / 2.0)))
            if mid <= values[i] or mid >= values[i + 1] or mid in values:
                values.append(values[-1] + 100)
            else:
                values.insert(i + 1, mid)
            values = sorted(set(values))
        else:
            values.append(values[-1] + 100)

    return [float(v) for v in values[:count]]


def generate_rpm_axis(spec: EngineSpec, count: int) -> list[float]:
    return select_axis(
        rpm_landmarks(spec),
        count,
        gap_score=_rpm_gap_score,
        spec=spec,
    )


def generate_load_axis(spec: EngineSpec, count: int, *, unit: str = "kPa") -> list[float]:
    if unit.lower() in {"inhg", "inhg_gauge"}:
        return select_axis(load_landmarks_inhg(spec), count)
    return select_axis(
        load_landmarks_kpa(spec),
        count,
        gap_score=_load_gap_score,
        spec=spec,
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
