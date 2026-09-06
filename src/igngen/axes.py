"""Nonlinear, landmark-priority axis generation (audio-scale philosophy)."""

from __future__ import annotations

from dataclasses import dataclass

from .model import EngineSpec


@dataclass(frozen=True)
class Landmark:
    value: float
    priority: int
    label: str


def rpm_landmarks(spec: EngineSpec) -> list[Landmark]:
    idle = spec.idle_rpm
    half = spec.idle_pocket_width / 2.0
    soft = spec.redline_rpm - spec.soft_limit_rpm_before_redline
    overspeed = spec.redline_rpm + 1000.0
    return [
        Landmark(300, 100, "cranking"),
        Landmark(max(400.0, idle - half), 90, "idle_lower"),
        Landmark(idle, 100, "idle_target"),
        Landmark(idle + half, 90, "idle_upper"),
        Landmark(spec.peak_torque_rpm, 100, "peak_torque"),
        Landmark(spec.peak_hp_rpm, 85, "peak_hp"),
        Landmark(soft, 85, "soft_limit"),
        Landmark(spec.redline_rpm, 100, "redline"),
        Landmark(overspeed, 100, "overspeed"),
        Landmark(max(600.0, idle - half - 150), 50, "idle_approach"),
        Landmark(idle + half + 250, 50, "off_idle"),
        Landmark((idle + spec.peak_torque_rpm) / 2.0, 50, "tq_rise_mid"),
        Landmark((spec.peak_torque_rpm + spec.peak_hp_rpm) / 2.0, 40, "post_tq"),
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


def select_axis(landmarks: list[Landmark], count: int) -> list[float]:
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
        chosen.append(lm)

    values = sorted(c.value for c in chosen)
    while len(values) < count:
        gaps = [(values[i + 1] - values[i], i) for i in range(len(values) - 1)]
        gaps.sort(reverse=True)
        if not gaps or gaps[0][0] <= 0:
            break
        _, i = gaps[0]
        mid = float(int(round((values[i] + values[i + 1]) / 2.0)))
        if mid in values or mid <= values[i] or mid >= values[i + 1]:
            # force a distinct integer midpoint
            mid = values[i] + 1
            if mid >= values[i + 1]:
                break
        values.insert(i + 1, mid)

    values = sorted(set(float(int(round(v))) for v in values))
    while len(values) < count:
        values.append(values[-1] + max(100, int(values[-1] - values[-2]) if len(values) > 1 else 100))
        values = sorted(set(values))

    return [float(v) for v in values[:count]]


def generate_rpm_axis(spec: EngineSpec, count: int) -> list[float]:
    return select_axis(rpm_landmarks(spec), count)


def generate_load_axis(spec: EngineSpec, count: int, *, unit: str = "kPa") -> list[float]:
    if unit.lower() in {"inhg", "inhg_gauge"}:
        return select_axis(load_landmarks_inhg(spec), count)
    return select_axis(load_landmarks_kpa(spec), count)


def example_axes_for_docs(spec: EngineSpec | None = None) -> dict[str, list[float]]:
    spec = spec or EngineSpec()
    return {
        "rpm_8": generate_rpm_axis(spec, 8),
        "rpm_12": generate_rpm_axis(spec, 12),
        "load_kpa_8": generate_load_axis(spec, 8, unit="kPa"),
        "load_kpa_12": generate_load_axis(spec, 12, unit="kPa"),
    }
