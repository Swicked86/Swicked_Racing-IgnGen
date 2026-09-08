from __future__ import annotations

import configparser
import math
from dataclasses import dataclass, replace
from pathlib import Path

from .table import TimingTable

BAR_TO_PSI = 14.5037738
KPA_PER_PSI = 6.895
RPM_STEPS = (50, 100, 250, 500, 1000)
MAP_STEPS = (5, 10, 20, 25, 50)
RECURVE_DEFAULT_FRACTIONS = (0.25, 0.50, 0.75)


@dataclass
class EngineParameters:
    name: str = "other"
    description: str = "Custom engine"
    displacement_cc: float = 1600.0
    peak_hp: float = 0.0
    peak_hp_rpm: float = 0.0
    peak_torque_lbft: float = 0.0
    peak_torque_rpm: float = 3500.0
    redline_rpm: float = 6000.0
    boost_psi: float = 0.0
    idle_rpm: float = 750.0
    idle_pocket_width: float = 100.0
    idle_pocket_lower_share: float = 0.25
    idle_pocket_upper_share: float = 0.75
    idle_timing_target: float = 10.0
    idle_timing_delta: float = 6.0
    idle_map_lo: float = 30.0
    idle_map_hi: float = 45.0
    cranking_rpm: float = 500.0
    cranking_timing: float = 10.0
    base_timing: float = 15.0
    mech_timing_at_peak_torque: float = 36.0
    recurve_rpm_1: float | None = None
    recurve_timing_1: float | None = None
    recurve_rpm_2: float | None = None
    recurve_timing_2: float | None = None
    recurve_rpm_3: float | None = None
    recurve_timing_3: float | None = None
    vacuum_total_timing: float = 50.0
    vacuum_full_map_kpa: float = 40.0
    boost_timing_limit: float = 20.0
    boost_retard_gain: float = 0.60
    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    overspeed_rpm_after_redline: float = 1000.0
    atm_kpa: float = 100.0
    map_floor_kpa: float = 20.0

    @property
    def normalized_idle_shares(self) -> tuple[float, float]:
        lo = max(0.0, float(self.idle_pocket_lower_share))
        hi = max(0.0, float(self.idle_pocket_upper_share))
        total = lo + hi
        return (0.25, 0.75) if total <= 0 else (lo / total, hi / total)

    @property
    def idle_pocket_lo_rpm(self) -> float:
        lo, _ = self.normalized_idle_shares
        return max(self.cranking_rpm, self.idle_rpm - self.idle_pocket_width * lo)

    @property
    def idle_pocket_hi_rpm(self) -> float:
        _, hi = self.normalized_idle_shares
        return self.idle_rpm + self.idle_pocket_width * hi

    @property
    def soft_limit_start_rpm(self) -> float:
        return self.redline_rpm - self.soft_limit_rpm_before_redline

    @property
    def overspeed_rpm(self) -> float:
        return self.redline_rpm + self.overspeed_rpm_after_redline

    @property
    def max_boost_map_kpa(self) -> float:
        return self.atm_kpa + max(0.0, self.boost_psi) * KPA_PER_PSI

    @property
    def recurve_points(self) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        """Return the three user-facing mechanical recurve knots.

        Missing profile values resolve to collinear 25/50/75% points, which
        preserves the original straight-line mechanical advance curve.
        """
        rpm_span = max(self.peak_torque_rpm - self.idle_rpm, 1.0)
        timing_span = self.mech_timing_at_peak_torque - self.base_timing
        raw = (
            (self.recurve_rpm_1, self.recurve_timing_1),
            (self.recurve_rpm_2, self.recurve_timing_2),
            (self.recurve_rpm_3, self.recurve_timing_3),
        )
        points: list[tuple[float, float]] = []
        for fraction, (rpm, timing) in zip(RECURVE_DEFAULT_FRACTIONS, raw):
            resolved_rpm = self.idle_rpm + rpm_span * fraction if rpm is None else float(rpm)
            resolved_timing = self.base_timing + timing_span * fraction if timing is None else float(timing)
            points.append((resolved_rpm, resolved_timing))
        return points[0], points[1], points[2]

    def derived_idle_targets(self) -> tuple[float, float, float]:
        target = float(self.idle_timing_target)
        delta = max(0.0, float(self.idle_timing_delta))
        return target + delta, target, target - delta

    def with_overrides(self, **changes: float | str | None) -> "EngineParameters":
        usable = {k: v for k, v in changes.items() if v is not None}
        unknown = set(usable) - set(self.__dataclass_fields__)
        if unknown:
            raise KeyError(f"unknown engine override(s): {', '.join(sorted(unknown))}")
        return replace(self, **usable)


def _engine_dirs() -> list[Path]:
    project_root = Path(__file__).resolve().parents[2]
    return [Path.cwd() / "engines", project_root / "engines"]


def find_engine_profile(name: str) -> Path | None:
    wanted = name.strip().lower().replace(" ", "")
    for directory in _engine_dirs():
        if not directory.is_dir():
            continue
        for path in directory.glob("*.ini"):
            if path.stem.lower().replace(" ", "") == wanted:
                return path
    return None


def list_engine_profiles() -> list[Path]:
    found: dict[str, Path] = {}
    for directory in _engine_dirs():
        if directory.is_dir():
            for path in sorted(directory.glob("*.ini")):
                found.setdefault(path.stem.lower(), path)
    return list(found.values())


def load_engine_profile(path_or_name: str | Path) -> EngineParameters:
    if str(path_or_name).strip().lower() in {"other", "custom", "new"}:
        return EngineParameters()
    path = Path(path_or_name)
    if not path.is_file():
        found = find_engine_profile(str(path_or_name))
        if found is None:
            raise FileNotFoundError(f"engine profile not found: {path_or_name}")
        path = found

    parser = configparser.ConfigParser()
    parser.read(path)
    profile = parser["profile"] if parser.has_section("profile") else {}
    engine = parser["engine"] if parser.has_section("engine") else {}
    mechanical = parser["mechanical"] if parser.has_section("mechanical") else {}
    recurve = parser["recurve"] if parser.has_section("recurve") else {}
    vacuum = parser["vacuum"] if parser.has_section("vacuum") else {}
    boost = parser["boost"] if parser.has_section("boost") else {}
    idle = parser["idle"] if parser.has_section("idle") else {}
    limiter = parser["limiter"] if parser.has_section("limiter") else {}
    d = EngineParameters()

    def num(section, key: str, default: float) -> float:
        return float(section.get(key)) if key in section else float(default)

    def optional_num(section, key: str) -> float | None:
        return float(section.get(key)) if key in section else None

    if "boost_psi" in engine:
        boost_psi = float(engine.get("boost_psi"))
    elif "boost_bar_abs" in engine:
        boost_psi = max(0.0, (float(engine.get("boost_bar_abs")) - 1.0) * BAR_TO_PSI)
    else:
        boost_psi = d.boost_psi

    boost_limit = (
        float(boost.get("boost_timing_limit"))
        if "boost_timing_limit" in boost
        else float(boost.get("boost_retard_max"))
        if "boost_retard_max" in boost
        else d.boost_timing_limit
    )

    spec = EngineParameters(
        name=str(profile.get("name", path.stem)),
        description=str(profile.get("description", path.stem)),
        displacement_cc=num(engine, "displacement_cc", d.displacement_cc),
        peak_hp=num(engine, "peak_hp", d.peak_hp),
        peak_hp_rpm=num(engine, "peak_hp_rpm", d.peak_hp_rpm),
        peak_torque_lbft=num(engine, "peak_torque_lbft", d.peak_torque_lbft),
        peak_torque_rpm=num(engine, "peak_torque_rpm", d.peak_torque_rpm),
        redline_rpm=num(engine, "redline_rpm", d.redline_rpm),
        boost_psi=boost_psi,
        idle_rpm=num(engine, "idle_rpm", d.idle_rpm),
        idle_pocket_width=num(idle, "idle_pocket_width", d.idle_pocket_width),
        idle_pocket_lower_share=num(idle, "idle_pocket_lower_share", d.idle_pocket_lower_share),
        idle_pocket_upper_share=num(idle, "idle_pocket_upper_share", d.idle_pocket_upper_share),
        idle_timing_target=num(idle, "idle_timing_target", d.idle_timing_target),
        idle_timing_delta=num(idle, "idle_timing_delta", d.idle_timing_delta),
        idle_map_lo=num(idle, "idle_map_lo", d.idle_map_lo),
        idle_map_hi=num(idle, "idle_map_hi", d.idle_map_hi),
        cranking_rpm=num(mechanical, "cranking_rpm", d.cranking_rpm),
        cranking_timing=num(mechanical, "cranking_timing", d.cranking_timing),
        base_timing=num(mechanical, "base_timing", d.base_timing),
        mech_timing_at_peak_torque=num(mechanical, "mech_timing_at_peak_torque", d.mech_timing_at_peak_torque),
        recurve_rpm_1=optional_num(recurve, "point1_rpm"),
        recurve_timing_1=optional_num(recurve, "point1_timing"),
        recurve_rpm_2=optional_num(recurve, "point2_rpm"),
        recurve_timing_2=optional_num(recurve, "point2_timing"),
        recurve_rpm_3=optional_num(recurve, "point3_rpm"),
        recurve_timing_3=optional_num(recurve, "point3_timing"),
        vacuum_total_timing=num(vacuum, "vacuum_total_timing", d.vacuum_total_timing),
        vacuum_full_map_kpa=num(vacuum, "vacuum_full_map_kpa", d.vacuum_full_map_kpa),
        boost_timing_limit=boost_limit,
        boost_retard_gain=num(boost, "boost_retard_gain", d.boost_retard_gain),
        soft_limit_rpm_before_redline=num(limiter, "soft_limit_rpm_before_redline", d.soft_limit_rpm_before_redline),
        soft_limit_retard=num(limiter, "soft_limit_retard", d.soft_limit_retard),
        overspeed_rpm_after_redline=num(limiter, "overspeed_rpm_after_redline", d.overspeed_rpm_after_redline),
        atm_kpa=num(engine, "atm_kpa", d.atm_kpa),
        map_floor_kpa=num(engine, "map_floor_kpa", d.map_floor_kpa),
    )
    validate_recurve(spec)
    return spec


def clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def validate_recurve(spec: EngineParameters) -> None:
    points = spec.recurve_points
    rpms = [p[0] for p in points]
    timings = [p[1] for p in points]
    if not (spec.idle_rpm < rpms[0] < rpms[1] < rpms[2] < spec.peak_torque_rpm):
        raise ValueError("recurve RPM points must increase strictly between idle RPM and peak torque RPM")
    if not all(math.isfinite(v) for v in (*rpms, *timings)):
        raise ValueError("recurve points must be finite numbers")


def _pchip_slopes(xs: list[float], ys: list[float]) -> list[float]:
    """Shape-preserving cubic slopes (Fritsch-Carlson/PCHIP style)."""
    n = len(xs)
    if n == 2:
        slope = (ys[1] - ys[0]) / (xs[1] - xs[0])
        return [slope, slope]

    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    delta = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    d = [0.0] * n

    for i in range(1, n - 1):
        if delta[i - 1] == 0.0 or delta[i] == 0.0 or delta[i - 1] * delta[i] <= 0.0:
            d[i] = 0.0
        else:
            w1 = 2.0 * h[i] + h[i - 1]
            w2 = h[i] + 2.0 * h[i - 1]
            d[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])

    d0 = ((2.0 * h[0] + h[1]) * delta[0] - h[0] * delta[1]) / (h[0] + h[1])
    if d0 * delta[0] <= 0.0:
        d0 = 0.0
    elif delta[0] * delta[1] < 0.0 and abs(d0) > abs(3.0 * delta[0]):
        d0 = 3.0 * delta[0]
    d[0] = d0

    dn = ((2.0 * h[-1] + h[-2]) * delta[-1] - h[-1] * delta[-2]) / (h[-1] + h[-2])
    if dn * delta[-1] <= 0.0:
        dn = 0.0
    elif delta[-1] * delta[-2] < 0.0 and abs(dn) > abs(3.0 * delta[-1]):
        dn = 3.0 * delta[-1]
    d[-1] = dn
    return d


def _pchip_interpolate(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    slopes = _pchip_slopes(xs, ys)
    i = 0
    while i + 1 < len(xs) and x > xs[i + 1]:
        i += 1
    h = xs[i + 1] - xs[i]
    t = (x - xs[i]) / h
    h00 = 2.0 * t**3 - 3.0 * t**2 + 1.0
    h10 = t**3 - 2.0 * t**2 + t
    h01 = -2.0 * t**3 + 3.0 * t**2
    h11 = t**3 - t**2
    return h00 * ys[i] + h10 * h * slopes[i] + h01 * ys[i + 1] + h11 * h * slopes[i + 1]


def mechanical_curve_points(spec: EngineParameters) -> list[tuple[float, float]]:
    validate_recurve(spec)
    return [
        (float(spec.idle_rpm), float(spec.base_timing)),
        *[(float(r), float(t)) for r, t in spec.recurve_points],
        (float(spec.peak_torque_rpm), float(spec.mech_timing_at_peak_torque)),
    ]


def mechanical_timing(rpm: float, spec: EngineParameters) -> float:
    if rpm <= spec.cranking_rpm:
        return float(spec.cranking_timing)
    if rpm <= spec.idle_rpm:
        return float(spec.base_timing)
    if rpm >= spec.peak_torque_rpm:
        return float(spec.mech_timing_at_peak_torque)
    points = mechanical_curve_points(spec)
    return _pchip_interpolate(rpm, [p[0] for p in points], [p[1] for p in points])


def mechanical_progress(rpm: float, spec: EngineParameters) -> float:
    if rpm <= spec.idle_rpm:
        return 0.0
    if rpm >= spec.peak_torque_rpm:
        return 1.0
    span = spec.mech_timing_at_peak_torque - spec.base_timing
    if abs(span) < 1e-9:
        return clamp01((rpm - spec.idle_rpm) / max(spec.peak_torque_rpm - spec.idle_rpm, 1.0))
    return clamp01((mechanical_timing(rpm, spec) - spec.base_timing) / span)


def pressure_span_kpa(spec: EngineParameters) -> float:
    return max(spec.atm_kpa - spec.vacuum_full_map_kpa, 1.0)


def vacuum_map_fraction(map_kpa: float, spec: EngineParameters) -> float:
    if map_kpa >= spec.atm_kpa:
        return 0.0
    return clamp01((spec.atm_kpa - map_kpa) / pressure_span_kpa(spec))


def vacuum_add_at(rpm: float, map_kpa: float, spec: EngineParameters) -> float:
    full_add = max(0.0, spec.vacuum_total_timing - spec.mech_timing_at_peak_torque)
    return full_add * mechanical_progress(rpm, spec) * vacuum_map_fraction(map_kpa, spec)


def boost_map_fraction(map_kpa: float, spec: EngineParameters) -> float:
    if spec.boost_psi <= 0.0 or map_kpa <= spec.atm_kpa:
        return 0.0
    return clamp01(((map_kpa - spec.atm_kpa) / pressure_span_kpa(spec)) * max(0.0, spec.boost_retard_gain))


def full_boost_target_at_rpm(rpm: float, spec: EngineParameters) -> float:
    p = mechanical_progress(rpm, spec)
    return spec.base_timing + (spec.boost_timing_limit - spec.base_timing) * p


def pressure_timing(rpm: float, map_kpa: float, spec: EngineParameters) -> float:
    master = mechanical_timing(rpm, spec)
    if map_kpa < spec.atm_kpa:
        return master + vacuum_add_at(rpm, map_kpa, spec)
    if map_kpa > spec.atm_kpa and spec.boost_psi > 0:
        f = boost_map_fraction(map_kpa, spec)
        target = full_boost_target_at_rpm(rpm, spec)
        return master + (target - master) * f
    return master


def idle_pocket_target(rpm: float, spec: EngineParameters) -> float:
    low_t, target_t, high_t = spec.derived_idle_targets()
    lo, center, hi = spec.idle_pocket_lo_rpm, spec.idle_rpm, spec.idle_pocket_hi_rpm
    if rpm <= center:
        t = clamp01((rpm - lo) / max(center - lo, 1.0))
        return low_t + (target_t - low_t) * t
    t = clamp01((rpm - center) / max(hi - center, 1.0))
    return target_t + (high_t - target_t) * t


def soft_limit_correction(rpm: float, spec: EngineParameters) -> float:
    start = spec.soft_limit_start_rpm
    if rpm <= start:
        return 0.0
    if rpm >= spec.redline_rpm:
        return -float(spec.soft_limit_retard)
    t = clamp01((rpm - start) / max(spec.redline_rpm - start, 1.0))
    return -float(spec.soft_limit_retard) * (t * t * (3.0 - 2.0 * t))


def timing_at(rpm: float, map_kpa: float, spec: EngineParameters) -> float:
    value = pressure_timing(rpm, map_kpa, spec)
    if spec.idle_pocket_lo_rpm <= rpm <= spec.idle_pocket_hi_rpm and spec.idle_map_lo <= map_kpa <= spec.idle_map_hi:
        value = idle_pocket_target(rpm, spec)
    value += soft_limit_correction(rpm, spec)
    return value


def _unique(values: list[float]) -> list[float]:
    return sorted({float(round(v)) for v in values})


def _nearest_step(raw: float, choices: tuple[int, ...]) -> int:
    eligible = [s for s in choices if s <= raw]
    return eligible[-1] if eligible else choices[0]


def _fill_interval(lo: float, hi: float, count: int, protected: set[float]) -> list[float]:
    if count <= 0 or hi <= lo:
        return []
    spacing = (hi - lo) / (count + 1)
    step = _nearest_step(spacing, RPM_STEPS)
    ladder = [float(v) for v in range(int(math.ceil((lo + 1) / step) * step), int(hi), step) if float(v) not in protected]
    for finer in reversed([s for s in RPM_STEPS if s < step]):
        if len(ladder) >= count:
            break
        ladder = [float(v) for v in range(int(math.ceil((lo + 1) / finer) * finer), int(hi), finer) if float(v) not in protected]
    if len(ladder) <= count:
        return ladder
    ideals = [lo + (hi - lo) * i / (count + 1) for i in range(1, count + 1)]
    available = set(ladder)
    out = []
    for ideal in ideals:
        c = min(available, key=lambda x: (abs(x - ideal), x))
        out.append(c)
        available.remove(c)
    return sorted(out)


def generate_rpm_axis(spec: EngineParameters, count: int) -> list[float]:
    recurve_rpms = [p[0] for p in spec.recurve_points]
    anchors = _unique([
        spec.cranking_rpm,
        spec.idle_pocket_lo_rpm,
        spec.idle_rpm,
        spec.idle_pocket_hi_rpm,
        *recurve_rpms,
        spec.peak_torque_rpm,
        spec.soft_limit_start_rpm,
        spec.redline_rpm,
        spec.overspeed_rpm,
    ])
    if count < 2:
        raise ValueError("RPM axis requires at least 2 cells")
    if len(anchors) > count:
        priority = [
            spec.cranking_rpm,
            spec.idle_rpm,
            *recurve_rpms,
            spec.peak_torque_rpm,
            spec.soft_limit_start_rpm,
            spec.redline_rpm,
            spec.overspeed_rpm,
            spec.idle_pocket_hi_rpm,
            spec.idle_pocket_lo_rpm,
        ]
        return sorted(_unique(priority)[:count])
    result = list(anchors)
    protected = set(result)
    remaining = count - len(result)
    hp = float(round(spec.peak_hp_rpm))
    if remaining > 0 and spec.peak_torque_rpm < hp < spec.overspeed_rpm and hp not in protected:
        result.append(hp)
        protected.add(hp)
        remaining -= 1
    pre_n = int(round(remaining * 2 / 3))
    post_n = remaining - pre_n
    pre = _fill_interval(spec.idle_pocket_hi_rpm, spec.peak_torque_rpm, pre_n, protected)
    result.extend(pre)
    protected.update(pre)
    result.extend(_fill_interval(spec.peak_torque_rpm, spec.overspeed_rpm, post_n, protected))
    result = _unique(result)
    while len(result) < count:
        gaps = sorted(((result[i + 1] - result[i], i) for i in range(len(result) - 1)), reverse=True)
        placed = False
        for _, i in gaps:
            c = _fill_interval(result[i], result[i + 1], 1, set(result))
            if c:
                result.append(c[0])
                result = _unique(result)
                placed = True
                break
        if not placed:
            break
    if len(result) != count:
        raise ValueError(f"could not create {count} unique RPM cells; generated {len(result)}")
    return result


def _decel_anchor(spec: EngineParameters) -> float:
    step = 10 if spec.idle_map_lo >= 30 else 5
    return float(max(5.0, math.floor((spec.idle_map_lo - step) / step) * step))


def _nice_map_step(span: float, count: int) -> int:
    return _nearest_step(max(span, 1.0) / max(count - 1, 1), MAP_STEPS)


def _ladder(lo: float, hi: float, step: int) -> list[float]:
    start = int(math.ceil(lo / step) * step)
    end = int(math.floor(hi / step) * step)
    return [] if end < start else [float(v) for v in range(start, end + 1, step)]


def _select_evenly(candidates: list[float], count: int) -> list[float]:
    values = sorted(set(candidates))
    if count <= 0:
        return []
    if len(values) <= count:
        return values
    if count == 1:
        return [values[len(values) // 2]]
    out = []
    avail = set(values)
    for ideal in [i * (len(values) - 1) / (count - 1) for i in range(count)]:
        target = values[int(round(ideal))]
        c = min(avail, key=lambda x: (abs(x - target), x))
        out.append(c)
        avail.remove(c)
    return sorted(out)


def generate_load_axis(spec: EngineParameters, count: int) -> list[float]:
    if count < 2:
        raise ValueError("load axis requires at least 2 cells")
    atm = float(round(spec.atm_kpa))
    lo = float(round(spec.idle_map_lo))
    hi = float(round(spec.idle_map_hi))
    if hi < lo:
        lo, hi = hi, lo
    mid = float(round((lo + hi) / 2))
    decel = _decel_anchor(spec)
    boosted = spec.boost_psi > 0
    if boosted:
        span = max(spec.max_boost_map_kpa - atm, 1)
        step = _nice_map_step(span, max(3, count // 3))
        maxb = float(int(round(spec.max_boost_map_kpa / step) * step))
        maxb = max(maxb, atm + step)
        over = maxb + step
    else:
        step = 5
        maxb = atm
        over = atm + 5
    result = []
    for v in [decel, lo, mid, hi, atm] + ([maxb, over] if boosted else [over]):
        v = float(round(v))
        if v not in result:
            result.append(v)
        if len(result) == count:
            return sorted(result)
    result = _unique(result)
    remaining = count - len(result)
    upper = max(hi, decel)
    na_span = max(atm - upper, 1)
    if remaining > 0:
        if boosted:
            bspan = max(maxb - atm, 1)
            na_n = max(0, min(remaining, int(round(remaining * na_span / (na_span + 0.65 * bspan)))))
            b_n = remaining - na_n
        else:
            na_n = remaining
            b_n = 0
        na_step = _nice_map_step(na_span, max(na_n + 2, 2))
        c = [v for v in _ladder(upper, atm, na_step) if upper < v < atm and v not in result]
        result.extend(_select_evenly(c, na_n))
        if boosted and b_n > 0:
            c = [v for v in _ladder(atm, maxb, step) if atm < v < maxb and v not in result]
            result.extend(_select_evenly(c, b_n))
    result = _unique(result)
    for refine in (5, 2, 1):
        if len(result) >= count:
            break
        c = [v for v in _ladder(hi, over, refine) if v not in result and hi < v < over]
        while len(result) < count and c:
            scored = []
            for x in c:
                lower = max((v for v in result if v < x), default=result[0])
                upper2 = min((v for v in result if v > x), default=result[-1])
                scored.append((upper2 - lower, x))
            _, x = max(scored, key=lambda z: (z[0], -z[1]))
            result.append(x)
            result = _unique(result)
            c.remove(x)
    if len(result) != count:
        raise ValueError(f"could not create {count} unique load cells; generated {len(result)}")
    if atm not in result:
        raise AssertionError("atmosphere crossover was lost from load axis")
    return result


def build_table(rpm: list[float], load: list[float], spec: EngineParameters) -> TimingTable:
    values = [[float(round(timing_at(r, m, spec))) for m in load] for r in rpm]
    return TimingTable(
        rpm=[float(round(x)) for x in rpm],
        load=[float(round(x)) for x in load],
        values=values,
        load_unit="kPa",
    )


def describe_spec(spec: EngineParameters) -> str:
    catch, target, upper = spec.derived_idle_targets()
    span = pressure_span_kpa(spec)
    boost_note = "off"
    if spec.boost_psi > 0:
        full = spec.atm_kpa + span / spec.boost_retard_gain if spec.boost_retard_gain > 0 else float("inf")
        boost_note = f"{spec.boost_psi:g} psi, limit {spec.boost_timing_limit:g}°, gain {spec.boost_retard_gain:g}, full limit ~{full:.0f} kPa"
    recurve_note = ", ".join(f"{rpm:g}@{timing:g}°" for rpm, timing in spec.recurve_points)
    return (
        f"Engine: {spec.name} — {spec.description}\n"
        f"  {spec.displacement_cc:g} cc; peak HP {spec.peak_hp:g}@{spec.peak_hp_rpm:g}; peak torque {spec.peak_torque_lbft:g}@{spec.peak_torque_rpm:g}; redline {spec.redline_rpm:g}\n"
        f"  Idle: {spec.idle_rpm:g} RPM; pocket {spec.idle_pocket_lo_rpm:g}/{spec.idle_rpm:g}/{spec.idle_pocket_hi_rpm:g} RPM = {catch:g}/{target:g}/{upper:g}°; MAP {spec.idle_map_lo:g}-{spec.idle_map_hi:g} kPa\n"
        f"  Mechanical: crank {spec.cranking_timing:g}°@{spec.cranking_rpm:g}; base {spec.base_timing:g}°; full {spec.mech_timing_at_peak_torque:g}°@{spec.peak_torque_rpm:g}\n"
        f"  Recurve: {recurve_note}\n"
        f"  Vacuum: total {spec.vacuum_total_timing:g}° at <= {spec.vacuum_full_map_kpa:g} kPa\n"
        f"  Boost: {boost_note}\n"
        f"  Limiter: soft starts {spec.soft_limit_start_rpm:g}; retard {spec.soft_limit_retard:g}°; overspeed axis {spec.overspeed_rpm:g} RPM"
    )