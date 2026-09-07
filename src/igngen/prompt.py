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


def _num_default(v: float, *, as_int: bool = False):
    """Pretty bracket default: ints without .0 when whole."""
    if as_int:
        return int(round(v))
    if abs(v - round(v)) < 1e-9:
        return int(round(v))
    return float(v)


def prompt_engine_spec(
    *,
    layers: LayerName = "mechanical",
    defaults: EngineSpec | None = None,
) -> EngineSpec:
    """Prompt for engine inputs. ``defaults`` (e.g. vehicle profile) fill the [brackets]."""
    d = defaults or EngineSpec()
    title = "IgnGen — engine inputs (Enter keeps the default)"
    if defaults is not None:
        title += " — from vehicle profile"
    print(f"{title}\n")

    displacement_cc = _ask(
        "Displacement (cc)", _num_default(d.displacement_cc, as_int=True), cast=int
    )
    peak_hp = _ask("Peak horsepower", _num_default(d.peak_hp), cast=float)
    peak_hp_rpm = _ask(
        "RPM at peak HP", _num_default(d.peak_hp_rpm, as_int=True), cast=int
    )
    peak_torque_lbft = _ask(
        "Peak torque (lb-ft)", _num_default(d.peak_torque_lbft), cast=float
    )
    peak_torque_rpm = _ask(
        "RPM at peak torque", _num_default(d.peak_torque_rpm, as_int=True), cast=int
    )
    redline_rpm = _ask(
        "Redline / max RPM", _num_default(d.redline_rpm, as_int=True), cast=int
    )
    boost_psi = _ask(
        "Max boost (psi, 0 = NA)", _num_default(d.boost_psi), cast=float
    )
    idle_rpm = _ask(
        "Target idle RPM", _num_default(d.idle_rpm, as_int=True), cast=int
    )
    idle_pocket_width = float(
        _ask(
            "Idle pocket width (±RPM from idle)",
            _num_default(d.idle_pocket_width, as_int=True),
            cast=int,
        )
    )

    print("\n— Mechanical advance —")
    base_timing = _ask(
        "Base / initial timing (°BTDC)",
        _num_default(d.base_timing, as_int=True),
        cast=int,
    )
    mech_at_tq = _ask(
        "Total timing at peak torque (°)",
        _num_default(d.mech_timing_at_peak_torque, as_int=True),
        cast=int,
    )

    vacuum_total_timing = float(d.vacuum_total_timing)
    vacuum_full_map_kpa = float(d.vacuum_full_map_kpa)  # fixed 40 kPa; not prompted
    boost_timing_limit = float(getattr(d, "boost_timing_limit", d.boost_retard_max))
    idle_pocket_bump = float(getattr(d, "idle_pocket_bump", 2))
    idle_map_lo = float(getattr(d, "idle_map_lo", 30))
    idle_map_hi = float(getattr(d, "idle_map_hi", 45))
    boost_retard_per_psi = float(d.boost_retard_per_psi)

    if layers in {"vacuum", "boost", "idle", "full"}:
        print("\n— Vacuum —")
        vacuum_total_timing = float(
            _ask(
                "Total timing",
                _num_default(d.vacuum_total_timing, as_int=True),
                cast=int,
            )
        )

    if layers in {"boost", "idle", "full"}:
        print("\n— Boost —")
        boost_timing_limit = float(
            _ask(
                "Boost timing limit",
                _num_default(boost_timing_limit, as_int=True),
                cast=int,
            )
        )

    if layers in {"idle", "full"}:
        print("\n— Idle pocket (±) —")
        idle_pocket_bump = float(
            _ask(
                "Idle stabilization (±° at pocket RPM edges)",
                _num_default(idle_pocket_bump, as_int=True),
                cast=int,
            )
        )

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
        idle_map_lo=float(idle_map_lo),
        idle_map_hi=float(idle_map_hi),
        idle_pocket_bump=float(idle_pocket_bump),
        vacuum_total_timing=float(vacuum_total_timing),
        vacuum_full_map_kpa=float(vacuum_full_map_kpa),
        vacuum_advance_max=float(vacuum_total_timing),
        boost_timing_limit=float(boost_timing_limit),
        boost_retard_max=float(boost_timing_limit),
        boost_retard_per_psi=float(boost_retard_per_psi),
    )


def prompt_output_path(default: str = "map.csv") -> str:
    return str(_ask("Output file", default, cast=str))


def prompt_preset(default: str = "base") -> str:
    return str(_ask("Axis preset (alpha | base | none)", default, cast=str))
