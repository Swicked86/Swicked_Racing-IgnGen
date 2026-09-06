"""Interactive prompts for engine inputs."""

from __future__ import annotations

from .model import EngineSpec, LayerName


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


def prompt_engine_spec(*, layers: LayerName = "mechanical") -> EngineSpec:
    print("IgnGen — engine inputs (Enter keeps the default)\n")
    displacement_cc = _ask("Displacement (cc)", 1600, cast=int)
    peak_hp = _ask("Peak horsepower", 280, cast=float)
    peak_hp_rpm = _ask("RPM at peak HP", 7800, cast=int)
    peak_torque_lbft = _ask("Peak torque (lb-ft)", 189, cast=float)
    peak_torque_rpm = _ask("RPM at peak torque", 4800, cast=int)
    redline_rpm = _ask("Redline / max RPM", 9300, cast=int)
    boost_psi = _ask("Max boost (psi, 0 = NA)", 7, cast=float)
    idle_rpm = _ask("Target idle RPM", 1100, cast=int)

    print("\n— Mechanical advance —")
    base_timing = _ask("Base / initial timing (°BTDC)", 10, cast=int)
    mech_at_tq = _ask("Total timing at peak torque (°)", 32, cast=int)

    idle_pocket_width = 250.0
    vacuum_advance_per_kpa = 0.35
    vacuum_advance_max = 42.0
    boost_retard_per_psi = 1.5
    boost_retard_max = 10.0

    if layers == "full":
        print("\n— Load / vacuum / boost (full model) —")
        idle_pocket_width = float(_ask("Idle pocket width (±RPM total span)", 250, cast=int))
        vacuum_advance_per_kpa = float(
            _ask("Vacuum advance step (° per kPa below atm)", 0.35, cast=float)
        )
        vacuum_advance_max = float(_ask("Vacuum timing limit (total ° max)", 42, cast=int))
        boost_retard_per_psi = float(_ask("Boost retard step (° per psi)", 1.5, cast=float))
        boost_retard_max = float(_ask("Boost timing limit (total ° min)", 10, cast=int))

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
        mech_timing_at_peak_torque=float(mech_at_tq),
        idle_rpm=float(idle_rpm),
        idle_pocket_width=float(idle_pocket_width),
        vacuum_advance_per_kpa=float(vacuum_advance_per_kpa),
        vacuum_advance_max=float(vacuum_advance_max),
        boost_retard_per_psi=float(boost_retard_per_psi),
        boost_retard_max=float(boost_retard_max),
    )


def prompt_output_path(default: str = "map.csv") -> str:
    return str(_ask("Output file", default, cast=str))


def prompt_preset(default: str = "base") -> str:
    return str(_ask("Axis preset (alpha | base | none)", default, cast=str))
