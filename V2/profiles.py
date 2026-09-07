from __future__ import annotations

import configparser
import re
from dataclasses import dataclass, replace
from pathlib import Path

BAR_TO_PSI = 14.5037738
KPA_PER_PSI = 6.895


@dataclass
class EngineParameters:
    """Canonical V2 engine/calibration inputs.

    Engine INI files provide defaults. The application can create a temporary
    copy with ``with_overrides`` for one table generation without modifying the
    profile. ``save_engine_profile`` is the explicit persistence path.
    """

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

    # TOTAL pocket span. Default 100 RPM: 25 RPM below / 75 RPM above idle.
    idle_pocket_width: float = 100.0
    idle_pocket_lower_share: float = 0.25
    idle_pocket_upper_share: float = 0.75

    # Pocket timing is independent of distributor/base timing.
    idle_timing_target: float = 10.0
    idle_timing_delta: float = 6.0

    # Warm-idle MAP operating band. These are calibration values; a camshaft,
    # intake, exhaust, or idle-speed change can move them substantially.
    idle_map_lo: float = 30.0
    idle_map_hi: float = 45.0

    cranking_rpm: float = 500.0
    cranking_timing: float = 10.0
    base_timing: float = 15.0
    mech_timing_at_peak_torque: float = 36.0

    vacuum_total_timing: float = 50.0
    vacuum_full_map_kpa: float = 40.0

    # Absolute total-timing limit under boost. User enters the timing target,
    # not a retard amount. Gain scales the mirrored vacuum kPa curve:
    # >1 = retard arrives sooner, <1 = retard arrives later.
    boost_timing_limit: float = 20.0
    boost_retard_gain: float = 1.0

    # Legacy/reference-only field retained for older INIs and comparison output.
    # It is not used by the V2 boost timing calculation.
    boost_retard_deg_per_psi: float = 2.0

    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    overspeed_rpm_after_redline: float = 1000.0

    atm_kpa: float = 100.0
    map_floor_kpa: float = 20.0

    @property
    def normalized_idle_shares(self) -> tuple[float, float]:
        lower = max(0.0, float(self.idle_pocket_lower_share))
        upper = max(0.0, float(self.idle_pocket_upper_share))
        total = lower + upper
        if total <= 0.0:
            return 0.25, 0.75
        return lower / total, upper / total

    @property
    def idle_pocket_lo_rpm(self) -> float:
        lower, _ = self.normalized_idle_shares
        return max(
            self.cranking_rpm,
            self.idle_rpm - self.idle_pocket_width * lower,
        )

    @property
    def idle_pocket_hi_rpm(self) -> float:
        _, upper = self.normalized_idle_shares
        return self.idle_rpm + self.idle_pocket_width * upper

    @property
    def soft_limit_start_rpm(self) -> float:
        return self.redline_rpm - self.soft_limit_rpm_before_redline

    @property
    def overspeed_rpm(self) -> float:
        return self.redline_rpm + self.overspeed_rpm_after_redline

    @property
    def max_boost_map_kpa(self) -> float:
        return self.atm_kpa + max(0.0, self.boost_psi) * KPA_PER_PSI

    def derived_idle_targets(self) -> tuple[float, float, float]:
        """Return catch / target / upper-pocket timing targets."""
        target = float(self.idle_timing_target)
        delta = max(0.0, float(self.idle_timing_delta))
        return target + delta, target, target - delta

    def with_overrides(self, **changes: float | str | None) -> "EngineParameters":
        """Return a temporary profile copy; ``None`` values are ignored."""
        usable = {key: value for key, value in changes.items() if value is not None}
        unknown = set(usable) - set(self.__dataclass_fields__)
        if unknown:
            raise KeyError(f"unknown engine override(s): {', '.join(sorted(unknown))}")
        return replace(self, **usable)


def _engine_dirs(search_dirs: list[Path] | None = None) -> list[Path]:
    result: list[Path] = []
    for path in search_dirs or []:
        result.append(Path(path))
    project_root = Path(__file__).resolve().parents[1]
    result.append(Path.cwd() / "engines")
    result.append(project_root / "engines")
    return result


def find_engine_profile(name: str, search_dirs: list[Path] | None = None) -> Path | None:
    wanted = name.strip().lower().replace(" ", "")
    for directory in _engine_dirs(search_dirs):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.ini"):
            if path.stem.lower().replace(" ", "") == wanted:
                return path
    return None


def list_engine_profiles(search_dirs: list[Path] | None = None) -> list[Path]:
    found: dict[str, Path] = {}
    for directory in _engine_dirs(search_dirs):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.ini")):
            found.setdefault(path.stem.lower(), path)
    return list(found.values())


def load_engine_profile(path_or_name: str | Path, search_dirs: list[Path] | None = None) -> EngineParameters:
    """Load an engine profile or return generic defaults for ``other``."""
    if str(path_or_name).strip().lower() in {"other", "custom", "new"}:
        return EngineParameters()

    path = Path(path_or_name)
    if not path.is_file():
        found = find_engine_profile(str(path_or_name), search_dirs=search_dirs)
        if found is None:
            raise FileNotFoundError(f"engine profile not found: {path_or_name}")
        path = found

    parser = configparser.ConfigParser()
    parser.read(path)

    profile = parser["profile"] if parser.has_section("profile") else {}
    engine = parser["engine"] if parser.has_section("engine") else {}
    mechanical = parser["mechanical"] if parser.has_section("mechanical") else {}
    vacuum = parser["vacuum"] if parser.has_section("vacuum") else {}
    boost = parser["boost"] if parser.has_section("boost") else {}
    idle = parser["idle"] if parser.has_section("idle") else {}
    limiter = parser["limiter"] if parser.has_section("limiter") else {}

    defaults = EngineParameters()

    def number(section, key: str, default: float) -> float:
        if key not in section:
            return float(default)
        return float(section.get(key))

    boost_bar_abs = float(engine.get("boost_bar_abs")) if "boost_bar_abs" in engine else None
    if "boost_psi" in engine:
        boost_psi = float(engine.get("boost_psi"))
    elif boost_bar_abs is not None:
        boost_psi = max(0.0, (boost_bar_abs - 1.0) * BAR_TO_PSI)
    else:
        boost_psi = defaults.boost_psi

    explicit_boost_limit = None
    if "boost_timing_limit" in boost:
        explicit_boost_limit = float(boost.get("boost_timing_limit"))
    elif "boost_retard_max" in boost:
        explicit_boost_limit = float(boost.get("boost_retard_max"))

    mech_peak = number(
        mechanical,
        "mech_timing_at_peak_torque",
        defaults.mech_timing_at_peak_torque,
    )
    retard_rate = number(
        boost,
        "boost_retard_deg_per_psi",
        defaults.boost_retard_deg_per_psi,
    )
    if explicit_boost_limit is None:
        explicit_boost_limit = mech_peak - boost_psi * retard_rate

    return EngineParameters(
        name=str(profile.get("name", path.stem)),
        description=str(profile.get("description", path.stem)),
        displacement_cc=number(engine, "displacement_cc", defaults.displacement_cc),
        peak_hp=number(engine, "peak_hp", defaults.peak_hp),
        peak_hp_rpm=number(engine, "peak_hp_rpm", defaults.peak_hp_rpm),
        peak_torque_lbft=number(engine, "peak_torque_lbft", defaults.peak_torque_lbft),
        peak_torque_rpm=number(engine, "peak_torque_rpm", defaults.peak_torque_rpm),
        redline_rpm=number(engine, "redline_rpm", defaults.redline_rpm),
        boost_psi=boost_psi,
        idle_rpm=number(engine, "idle_rpm", defaults.idle_rpm),
        idle_pocket_width=number(idle, "idle_pocket_width", defaults.idle_pocket_width),
        idle_pocket_lower_share=number(idle, "idle_pocket_lower_share", defaults.idle_pocket_lower_share),
        idle_pocket_upper_share=number(idle, "idle_pocket_upper_share", defaults.idle_pocket_upper_share),
        idle_timing_target=number(idle, "idle_timing_target", defaults.idle_timing_target),
        idle_timing_delta=number(idle, "idle_timing_delta", defaults.idle_timing_delta),
        idle_map_lo=number(idle, "idle_map_lo", defaults.idle_map_lo),
        idle_map_hi=number(idle, "idle_map_hi", defaults.idle_map_hi),
        cranking_rpm=number(mechanical, "cranking_rpm", defaults.cranking_rpm),
        cranking_timing=number(mechanical, "cranking_timing", defaults.cranking_timing),
        base_timing=number(mechanical, "base_timing", defaults.base_timing),
        mech_timing_at_peak_torque=mech_peak,
        vacuum_total_timing=number(vacuum, "vacuum_total_timing", defaults.vacuum_total_timing),
        vacuum_full_map_kpa=number(vacuum, "vacuum_full_map_kpa", defaults.vacuum_full_map_kpa),
        boost_timing_limit=float(explicit_boost_limit),
        boost_retard_gain=number(boost, "boost_retard_gain", defaults.boost_retard_gain),
        boost_retard_deg_per_psi=retard_rate,
        soft_limit_rpm_before_redline=number(limiter, "soft_limit_rpm_before_redline", defaults.soft_limit_rpm_before_redline),
        soft_limit_retard=number(limiter, "soft_limit_retard", defaults.soft_limit_retard),
        overspeed_rpm_after_redline=number(limiter, "overspeed_rpm_after_redline", defaults.overspeed_rpm_after_redline),
        atm_kpa=number(engine, "atm_kpa", defaults.atm_kpa),
        map_floor_kpa=number(engine, "map_floor_kpa", defaults.map_floor_kpa),
    )


def _slug(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", name.strip())
    return value.strip("._") or "custom"


def save_engine_profile(
    spec: EngineParameters,
    path_or_name: str | Path,
    *,
    engine_dir: str | Path = "engines",
    overwrite: bool = False,
) -> Path:
    """Persist the current parameters as a tuner-readable engine INI."""
    destination = Path(path_or_name)
    if destination.suffix.lower() != ".ini" and destination.parent == Path("."):
        destination = Path(engine_dir) / f"{_slug(str(path_or_name))}.ini"
    elif destination.suffix.lower() != ".ini":
        destination = destination.with_suffix(".ini")

    if destination.exists() and not overwrite:
        raise FileExistsError(f"engine profile already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    lower_share, upper_share = spec.normalized_idle_shares
    text = f"""; IgnGen V2 engine profile: {spec.name}
; Values in this file are defaults. The application may temporarily override
; them for one generated table without changing this profile.

[profile]
name = {spec.name}
description = {spec.description}

[engine]
displacement_cc = {spec.displacement_cc:g}
peak_hp = {spec.peak_hp:g}
peak_hp_rpm = {spec.peak_hp_rpm:g}
peak_torque_lbft = {spec.peak_torque_lbft:g}
peak_torque_rpm = {spec.peak_torque_rpm:g}
redline_rpm = {spec.redline_rpm:g}
boost_psi = {spec.boost_psi:g}
idle_rpm = {spec.idle_rpm:g}
atm_kpa = {spec.atm_kpa:g}
map_floor_kpa = {spec.map_floor_kpa:g}

[mechanical]
cranking_rpm = {spec.cranking_rpm:g}
cranking_timing = {spec.cranking_timing:g}
base_timing = {spec.base_timing:g}
mech_timing_at_peak_torque = {spec.mech_timing_at_peak_torque:g}

[vacuum]
; Full-vacuum advance is reached at/below this absolute MAP value.
vacuum_full_map_kpa = {spec.vacuum_full_map_kpa:g}
vacuum_total_timing = {spec.vacuum_total_timing:g}

[boost]
; Absolute total timing limit. IgnGen calculates the required retard.
boost_timing_limit = {spec.boost_timing_limit:g}
; Pressure-domain gain applied to the mirrored vacuum kPa curve.
; 1.0 = same kPa rate as vacuum; >1 sooner; <1 slower.
boost_retard_gain = {spec.boost_retard_gain:g}
; Legacy/reference-only heuristic; V2 does not use it for timing generation.
boost_retard_deg_per_psi = {spec.boost_retard_deg_per_psi:g}

[idle]
idle_pocket_width = {spec.idle_pocket_width:g}
idle_pocket_lower_share = {lower_share:g}
idle_pocket_upper_share = {upper_share:g}
idle_timing_target = {spec.idle_timing_target:g}
idle_timing_delta = {spec.idle_timing_delta:g}
idle_map_lo = {spec.idle_map_lo:g}
idle_map_hi = {spec.idle_map_hi:g}

[limiter]
soft_limit_rpm_before_redline = {spec.soft_limit_rpm_before_redline:g}
soft_limit_retard = {spec.soft_limit_retard:g}
overspeed_rpm_after_redline = {spec.overspeed_rpm_after_redline:g}
"""
    destination.write_text(text, encoding="utf-8")
    return destination
