"""Interactive prompts for engine inputs."""

from __future__ import annotations

from .model import EngineSpec


def _ask(prompt: str, default: float | int | str | None = None, *, cast=float):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw:
            if default is None:
                print("  (required)")
                continue
            if cast is str:
                return str(default)
            return cast(default)
        try:
            if cast is int:
                return int(float(raw))
            if cast is str:
                return raw
            return cast(raw)
        except ValueError:
            print("  enter a number")


def prompt_engine_spec() -> EngineSpec:
    print("IgnGen — engine inputs (Enter keeps the default)\n")
    displacement_cc = _ask("Displacement (cc)", 1600, cast=int)
    peak_hp = _ask("Peak horsepower", 280, cast=float)
    peak_hp_rpm = _ask("RPM at peak HP", 7800, cast=int)
    peak_torque_lbft = _ask("Peak torque (lb-ft)", 189, cast=float)
    peak_torque_rpm = _ask("RPM at peak torque", 4800, cast=int)
    redline_rpm = _ask("Redline / max RPM", 9300, cast=int)
    boost_psi = _ask("Max boost (psi, 0 = NA)", 7, cast=float)
    base_timing = _ask("Base / idle timing (°BTDC)", 15, cast=int)
    idle_rpm = _ask("Target idle RPM", 1100, cast=int)
    print()
    return EngineSpec(
        displacement_cc=float(displacement_cc),
        peak_hp=float(peak_hp),
        peak_hp_rpm=float(peak_hp_rpm),
        peak_torque_lbft=float(peak_torque_lbft),
        peak_torque_rpm=float(peak_torque_rpm),
        redline_rpm=float(redline_rpm),
        boost_psi=float(boost_psi),
        base_timing=float(base_timing),
        idle_rpm=float(idle_rpm),
    )


def prompt_output_path(default: str = "map.csv") -> str:
    return str(_ask("Output file", default, cast=str))


def prompt_preset(default: str = "alpha") -> str:
    return str(_ask("Axis preset (alpha | base)", default, cast=str))
