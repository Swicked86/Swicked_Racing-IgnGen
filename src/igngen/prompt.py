"""Interactive prompts for engine inputs."""

from __future__ import annotations

from .model import EngineSpec, LayerName
from .engines import EngineProfile, describe_engine, find_engine, list_engines


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
    """Prompt for engine inputs. ``defaults`` (e.g. engine profile) fill the [brackets]."""
    d = defaults or EngineSpec()
    title = "IgnGen — engine inputs (Enter keeps the default)"
    if defaults is not None:
        title += " — from engine profile"
    print(f"{title}\n")

    print("— Engine settings —")
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

    print("\n— Idle settings —")
    idle_rpm = _ask(
        "Target idle RPM", _num_default(d.idle_rpm, as_int=True), cast=int
    )
    idle_pocket_width = float(
        _ask(
            "Idle pocket ±RPM",
            _num_default(d.idle_pocket_width, as_int=True),
            cast=int,
        )
    )
    idle_pocket_bump = float(getattr(d, "idle_pocket_bump", 2))
    idle_map_lo = float(getattr(d, "idle_map_lo", 30))
    idle_map_hi = float(getattr(d, "idle_map_hi", 45))
    if layers in {"idle", "full"}:
        idle_pocket_bump = float(
            _ask(
                "Idle stabilization ±°",
                _num_default(idle_pocket_bump, as_int=True),
                cast=int,
            )
        )

    print("\n— Mechanical advance —")
    cranking_rpm = float(getattr(d, "cranking_rpm", 500))
    cranking_timing = float(
        _ask(
            "Cranking timing (°BTDC @ 500 RPM)",
            _num_default(getattr(d, "cranking_timing", 10), as_int=True),
            cast=int,
        )
    )
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
    boost_retard_per_psi = float(d.boost_retard_per_psi)
    boost_psi = float(d.boost_psi)

    if layers in {"vacuum", "boost", "idle", "full"}:
        print("\n— Vacuum —")
        vacuum_total_timing = float(
            _ask(
                "Total timing advance limit",
                _num_default(d.vacuum_total_timing, as_int=True),
                cast=int,
            )
        )

    # Max boost always asked (shapes load axis); retard limit with boost layers
    print("\n— Boost —")
    boost_psi = _ask(
        "Max boost (psi, 0 = NA)", _num_default(d.boost_psi), cast=float
    )
    # NA: boost retard is ignored in the model — don't ask for a limit
    if layers in {"boost", "idle", "full"} and float(boost_psi) > 0.0:
        boost_timing_limit = float(
            _ask(
                "Boost timing retard limit",
                _num_default(boost_timing_limit, as_int=True),
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
        cranking_rpm=float(cranking_rpm),
        cranking_timing=float(cranking_timing),
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




def prompt_engine_choice() -> EngineProfile | None:
    """Ask which engine profile to use, or start a new blank one.

    Returns the selected ``EngineProfile``, or ``None`` to generate from scratch.
    """
    paths = list_engines()
    profiles: list[EngineProfile] = []
    for path in paths:
        v = find_engine(path.stem)
        if v is not None:
            profiles.append(v)

    print("— Engine —")
    if not profiles:
        print("  (no profiles under engines/)")
        print("  Enter a name to look up, or press Enter / type new for blank specs.\n")
    else:
        print("  Select a profile, or new to enter specs from scratch:\n")
        for i, v in enumerate(profiles, start=1):
            print(f"  {i}) {v.name} — {v.description}")
        print("  0) new — generate without a profile\n")

    while True:
        raw = input("Engine [new]: ").strip()
        if not raw or raw.lower() in {"new", "n", "none", "0", "-"}:
            print()
            return None
        # numeric pick
        if raw.isdigit():
            idx = int(raw)
            if idx == 0:
                print()
                return None
            if 1 <= idx <= len(profiles):
                chosen = profiles[idx - 1]
                print(describe_engine(chosen))
                print()
                return chosen
            print(f"  pick 0–{len(profiles)}")
            continue
        # name lookup
        found = find_engine(raw)
        if found is not None:
            print(describe_engine(found))
            print()
            return found
        known = ", ".join(v.name for v in profiles) or "(none)"
        print(f"  unknown {raw!r}; known: {known} (or new)")


def prompt_output_path(default: str = "map.csv") -> str:
    return str(_ask("Output file", default, cast=str))


def prompt_preset(default: str = "base") -> str:
    return str(_ask("Axis preset (alpha | base | none)", default, cast=str))
