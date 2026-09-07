from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

BAR_TO_PSI = 14.5037738


@dataclass
class EngineParameters:
    name: str = "custom"
    description: str = "Custom engine"

    displacement_cc: float = 1600.0
    peak_hp: float = 0.0
    peak_hp_rpm: float = 0.0
    peak_torque_lbft: float = 0.0
    peak_torque_rpm: float = 3500.0
    redline_rpm: float = 6000.0
    boost_psi: float = 0.0

    idle_rpm: float = 750.0
    # Total RPM span of the idle pocket, not +/- RPM.
    idle_pocket_width: float = 100.0
    idle_pocket_lower_share: float = 0.25
    idle_pocket_upper_share: float = 0.75
    idle_map_lo: float = 30.0
    idle_map_hi: float = 45.0
    # Default pocket authority around the idle timing target.
    idle_pocket_bump: float = 6.0

    cranking_rpm: float = 500.0
    cranking_timing: float = 10.0
    base_timing: float = 15.0
    mech_timing_at_peak_torque: float = 36.0

    vacuum_total_timing: float = 50.0
    vacuum_full_map_kpa: float = 40.0

    boost_timing_limit: float = 20.0
    boost_retard_deg_per_psi: float = 2.0

    soft_limit_rpm_before_redline: float = 500.0
    soft_limit_retard: float = 10.0
    overspeed_rpm_after_redline: float = 1000.0

    atm_kpa: float = 100.0
    map_floor_kpa: float = 20.0

    # Optional explicit idle-pocket targets. If omitted, V2 defaults to
    # 10 deg BTDC at target idle, +6 deg on the catch side, -6 deg on the
    # upper/retard side. Engine profiles may override any of these.
    idle_timing_low: float | None = None
    idle_timing_target: float | None = None
    idle_timing_high: float | None = None

    def _idle_pocket_shares(self) -> tuple[float, float]:
        lower = max(0.0, float(self.idle_pocket_lower_share))
        upper = max(0.0, float(self.idle_pocket_upper_share))
        total = lower + upper
        if total <= 0.0:
            return 0.25, 0.75
        return lower / total, upper / total

    @property
    def idle_pocket_lo_rpm(self) -> float:
        lower, _ = self._idle_pocket_shares()
        return max(
            self.cranking_rpm,
            self.idle_rpm - self.idle_pocket_width * lower,
        )

    @property
    def idle_pocket_hi_rpm(self) -> float:
        _, upper = self._idle_pocket_shares()
        return self.idle_rpm + self.idle_pocket_width * upper

    @property
    def soft_limit_start_rpm(self) -> float:
        return self.redline_rpm - self.soft_limit_rpm_before_redline

    @property
    def overspeed_rpm(self) -> float:
        return self.redline_rpm + self.overspeed_rpm_after_redline

    @property
    def max_boost_map_kpa(self) -> float:
        return self.atm_kpa + max(0.0, self.boost_psi) * 6.895

    def derived_idle_targets(self) -> tuple[float, float, float]:
        target = self.idle_timing_target
        if target is None:
            target = 10.0

        low = self.idle_timing_low
        high = self.idle_timing_high
        if low is None:
            low = target + self.idle_pocket_bump
        if high is None:
            high = target - self.idle_pocket_bump
        return float(low), float(target), float(high)


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

    def optional_number(section, key: str) -> float | None:
        if key not in section:
            return None
        return float(section.get(key))

    # V2 intentionally does not inherit V1's [engine] idle_pocket_width or
    # [idle] idle_pocket_bump fields. Those fields used the old symmetric
    # pocket semantics. V2 uses the explicit fields below and otherwise the
    # new 100-RPM, 25/75, 10 +/- 6 defaults.
    pocket_width = number(idle, "idle_pocket_width", defaults.idle_pocket_width)
    pocket_lower_share = number(
        idle,
        "idle_pocket_lower_share",
        defaults.idle_pocket_lower_share,
    )
    pocket_upper_share = number(
        idle,
        "idle_pocket_upper_share",
        defaults.idle_pocket_upper_share,
    )
    pocket_bump = number(idle, "idle_timing_delta", defaults.idle_pocket_bump)

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
        idle_pocket_width=pocket_width,
        idle_pocket_lower_share=pocket_lower_share,
        idle_pocket_upper_share=pocket_upper_share,
        idle_map_lo=number(idle, "idle_map_lo", defaults.idle_map_lo),
        idle_map_hi=number(idle, "idle_map_hi", defaults.idle_map_hi),
        idle_pocket_bump=pocket_bump,
        cranking_rpm=number(mechanical, "cranking_rpm", defaults.cranking_rpm),
        cranking_timing=number(mechanical, "cranking_timing", defaults.cranking_timing),
        base_timing=number(mechanical, "base_timing", defaults.base_timing),
        mech_timing_at_peak_torque=mech_peak,
        vacuum_total_timing=number(vacuum, "vacuum_total_timing", defaults.vacuum_total_timing),
        vacuum_full_map_kpa=number(vacuum, "vacuum_full_map_kpa", defaults.vacuum_full_map_kpa),
        boost_timing_limit=float(explicit_boost_limit),
        boost_retard_deg_per_psi=retard_rate,
        soft_limit_rpm_before_redline=number(
            limiter,
            "soft_limit_rpm_before_redline",
            defaults.soft_limit_rpm_before_redline,
        ),
        soft_limit_retard=number(limiter, "soft_limit_retard", defaults.soft_limit_retard),
        overspeed_rpm_after_redline=number(
            limiter,
            "overspeed_rpm_after_redline",
            defaults.overspeed_rpm_after_redline,
        ),
        atm_kpa=number(engine, "atm_kpa", defaults.atm_kpa),
        map_floor_kpa=number(engine, "map_floor_kpa", defaults.map_floor_kpa),
        idle_timing_low=optional_number(idle, "idle_timing_low"),
        idle_timing_target=optional_number(idle, "idle_timing_target"),
        idle_timing_high=optional_number(idle, "idle_timing_high"),
    )
