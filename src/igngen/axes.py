"""Nonlinear, landmark-priority axis generation (audio-scale philosophy).

Not a literal log scale — density follows rate-of-change / control importance.
Ideal landmarks are ranked; the generator keeps the highest priorities that fit
the requested axis length, then fills remaining slots for interpolation.

Examples from research (idle=1100, tq=4800, hp=7800, redline=9300):

8 RPM columns (priorities only):
  300, 850, 1100, 1350, 4800, 7800, 9300, 10300

12 RPM columns (idle denser + transitions):
  300, 700, 850, 1000, 1100, 1200, 1350, 2500, 4800, 7800, 8800, 10300
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
        # useful transitions (lower priority)
        Landmark(max(600.0, idle - half - 150), 50, "idle_approach"),
        Landmark(idle + half + 250, 50, "off_idle"),
        Landmark((idle + spec.peak_torque_rpm) / 2.0, 50, "tq_rise_mid"),
        Landmark((spec.peak_torque_rpm + spec.peak_hp_rpm) / 2.0, 40, "post_tq"),
    ]


def load_landmarks_kpa(spec: EngineSpec) -> list[Landmark]:
    """MAP absolute kPa; atmosphere (100) is mandatory."""
    atm = spec.atm_kpa
    max_boost_kpa = atm + spec.boost_psi * 6.895  # psi → approx kPa gauge
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
    """Alpha-style gauge inHg; ~0 is atmosphere crossover."""
    # Rough: boost_psi * 2.036 ≈ inHg gauge
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
    """Keep highest-priority unique values that fit ``count``, then fill gaps."""
    if count < 2:
        raise ValueError("axis count must be >= 2")

    # Dedupe by rounded value, keep highest priority
    best: dict[float, Landmark] = {}
    for lm in landmarks:
        key = round(lm.value, 4)
        if key not in best or lm.priority > best[key].priority:
            best[key] = lm
    ranked = sorted(best.values(), key=lambda x: (-x.priority, x.value))

    chosen: list[Landmark] = []
    for lm in ranked:
        if len(chosen) >= count:
            break
        # skip if too close to an already chosen point
        if any(abs(lm.value - c.value) < 1e-6 for c in chosen):
            continue
        chosen.append(lm)

    # If still short, add midpoints between largest gaps
    values = sorted(c.value for c in chosen)
    while len(values) < count:
        gaps = [(values[i + 1] - values[i], i) for i in range(len(values) - 1)]
        gaps.sort(reverse=True)
        if not gaps or gaps[0][0] <= 0:
            break
        _, i = gaps[0]
        mid = (values[i] + values[i + 1]) / 2.0
        values.insert(i + 1, round(mid, 4))

    # If overshot somehow, trim lowest-priority extras (shouldn't with loop)
    values = sorted(set(values))
    if len(values) > count:
        # keep mandatory-ish by re-selecting from ranked that exist in values
        keep = []
        for lm in ranked:
            v = round(lm.value, 4)
            if any(abs(v - x) < 1e-6 for x in values) and len(keep) < count:
                keep.append(next(x for x in values if abs(x - v) < 1e-6))
        # fill with evenly spaced from remaining
        for x in values:
            if len(keep) >= count:
                break
            if x not in keep:
                keep.append(x)
        values = sorted(keep)[:count]

    # Final length fix: pad with linear endpoints if still short
    while len(values) < count:
        values.append(values[-1] + (values[-1] - values[-2] if len(values) > 1 else 100))
        values = sorted(values)

    return [float(round(v, 4)) for v in values[:count]]


def generate_rpm_axis(spec: EngineSpec, count: int) -> list[float]:
    return select_axis(rpm_landmarks(spec), count)


def generate_load_axis(spec: EngineSpec, count: int, *, unit: str = "kPa") -> list[float]:
    if unit.lower() in {"inhg", "inhg_gauge"}:
        return select_axis(load_landmarks_inhg(spec), count)
    return select_axis(load_landmarks_kpa(spec), count)


def example_axes_for_docs(spec: EngineSpec | None = None) -> dict[str, list[float]]:
    """Canonical examples from the ChatGPT research thread."""
    spec = spec or EngineSpec()
    return {
        "rpm_8": generate_rpm_axis(spec, 8),
        "rpm_12": generate_rpm_axis(spec, 12),
        "load_kpa_8": generate_load_axis(spec, 8, unit="kPa"),
        "load_kpa_12": generate_load_axis(spec, 12, unit="kPa"),
    }
