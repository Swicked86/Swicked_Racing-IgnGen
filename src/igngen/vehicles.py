"""Vehicle profiles — pre-fill EngineSpec for known motors."""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

from .model import EngineSpec

BAR_TO_PSI = 14.5037738


@dataclass
class VehicleProfile:
    name: str
    description: str
    spec: EngineSpec
    path: str | None = None
    boost_bar_abs: float | None = None


def _vehicle_dirs(search_dirs: list[Path] | None = None) -> list[Path]:
    dirs: list[Path] = []
    for d in search_dirs or []:
        dirs.append(Path(d))
    dirs.append(Path.cwd() / "vehicles")
    dirs.append(Path(__file__).resolve().parents[2] / "vehicles")
    return dirs


def list_vehicles(search_dirs: list[Path] | None = None) -> list[Path]:
    found: dict[str, Path] = {}
    for d in _vehicle_dirs(search_dirs):
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.ini")):
            key = path.stem.lower()
            if key not in found:
                found[key] = path
    return list(found.values())


def find_vehicle(name: str, search_dirs: list[Path] | None = None) -> VehicleProfile | None:
    key = name.strip().lower().replace(" ", "")
    for d in _vehicle_dirs(search_dirs):
        for candidate in (d / f"{key}.ini", d / f"{key.upper()}.ini", d / f"{name}.ini"):
            if candidate.is_file():
                return load_vehicle(candidate)
        if d.is_dir():
            for path in d.glob("*.ini"):
                if path.stem.lower() == key:
                    return load_vehicle(path)
    return None


def load_vehicle(path: Path) -> VehicleProfile:
    cp = configparser.ConfigParser()
    cp.read(path)
    veh = cp["vehicle"] if cp.has_section("vehicle") else {}
    eng = cp["engine"] if cp.has_section("engine") else {}
    mech = cp["mechanical"] if cp.has_section("mechanical") else {}
    vac = cp["vacuum"] if cp.has_section("vacuum") else {}

    def f(section, key, default: float) -> float:
        if key not in section:
            return float(default)
        return float(section.get(key))

    boost_bar_abs = None
    if "boost_bar_abs" in eng:
        boost_bar_abs = float(eng.get("boost_bar_abs"))

    if "boost_psi" in eng:
        boost_psi = float(eng.get("boost_psi"))
    elif boost_bar_abs is not None:
        boost_psi = max(0.0, (boost_bar_abs - 1.0) * BAR_TO_PSI)
    else:
        boost_psi = 0.0

    spec = EngineSpec(
        displacement_cc=f(eng, "displacement_cc", 1600),
        peak_hp=f(eng, "peak_hp", 280),
        peak_hp_rpm=f(eng, "peak_hp_rpm", 7800),
        peak_torque_lbft=f(eng, "peak_torque_lbft", 189),
        peak_torque_rpm=f(eng, "peak_torque_rpm", 4800),
        redline_rpm=f(eng, "redline_rpm", 9300),
        boost_psi=boost_psi,
        idle_rpm=f(eng, "idle_rpm", 1100),
        idle_pocket_width=f(eng, "idle_pocket_width", 250),
        base_timing=f(mech, "base_timing", 10),
        mech_timing_at_peak_torque=f(mech, "mech_timing_at_peak_torque", 32),
        vacuum_total_timing=(
            f(vac, "vacuum_total_timing", 50)
            if "vacuum_total_timing" in vac
            else (
                f(mech, "mech_timing_at_peak_torque", 32) + f(vac, "vacuum_advance", 18)
                if "vacuum_advance" in vac
                else 50.0
            )
        ),
        vacuum_full_map_kpa=40.0,
        vacuum_advance_max=f(vac, "vacuum_total_timing", 50),
        boost_timing_limit=(
            f(cp["boost"], "boost_timing_limit", 20)
            if cp.has_section("boost") and "boost_timing_limit" in cp["boost"]
            else f(cp["boost"], "boost_retard_max", 20)
            if cp.has_section("boost")
            else 20.0
        ),
        boost_retard_max=(
            f(cp["boost"], "boost_timing_limit", 20)
            if cp.has_section("boost") and "boost_timing_limit" in cp["boost"]
            else f(cp["boost"], "boost_retard_max", 20)
            if cp.has_section("boost")
            else 20.0
        ),
    )
    return VehicleProfile(
        name=veh.get("name", path.stem),
        description=veh.get("description", path.stem),
        spec=spec,
        path=str(path),
        boost_bar_abs=boost_bar_abs,
    )


def describe_vehicle(v: VehicleProfile) -> str:
    s = v.spec
    boost_note = f"{s.boost_psi:.1f} psi"
    if v.boost_bar_abs is not None:
        boost_note = f"{v.boost_bar_abs:.2f} bar abs (~{s.boost_psi:.1f} psi gauge)"
    half = s.idle_pocket_width / 2.0
    return (
        f"{v.name}: {v.description}\n"
        f"  {s.displacement_cc:.0f} cc | {s.peak_hp:.0f} hp @{s.peak_hp_rpm:.0f} | "
        f"{s.peak_torque_lbft:.0f} lb-ft @{s.peak_torque_rpm:.0f} | "
        f"redline {s.redline_rpm:.0f}\n"
        f"  idle {s.idle_rpm:.0f} ±{half:.0f} (pocket width {s.idle_pocket_width:.0f}) | "
        f"base {s.base_timing:.0f}° → peak mech {s.mech_timing_at_peak_torque:.0f}° | "
        f"vac total {s.vacuum_total_timing:.0f}° | boost limit {s.boost_timing_limit:.0f}° | "
        f"boost {boost_note}"
    )
