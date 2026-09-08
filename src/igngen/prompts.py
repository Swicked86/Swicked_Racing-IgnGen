from __future__ import annotations

from .calibration import EngineParameters, describe_spec, find_engine_profile, list_engine_profiles, load_engine_profile, validate_recurve


def _ask(prompt: str, default=None, *, cast=float):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw:
            if default is None:
                print("  (required)")
                continue
            return str(default) if cast is str else cast(default)
        try:
            if cast is int:
                return int(float(raw))
            if cast is str:
                return raw
            return cast(raw)
        except ValueError:
            print("  enter a valid value")


def _num(v: float):
    return int(round(v)) if abs(v-round(v)) < 1e-9 else float(v)


def prompt_engine_choice() -> EngineParameters:
    paths = list_engine_profiles()
    print("— Select engine —")
    for i, path in enumerate(paths, start=1):
        spec = load_engine_profile(path)
        print(f"  {i}) {spec.name} — {spec.description}")
    print("  0) new — start from generic defaults\n")

    while True:
        raw = input("Engine [new]: ").strip()
        if not raw or raw.lower() in {"new","n","none","0","-"}:
            print()
            return EngineParameters()
        if raw.isdigit():
            idx=int(raw)
            if 1 <= idx <= len(paths):
                print()
                return load_engine_profile(paths[idx-1])
            print(f"  pick 0-{len(paths)}")
            continue
        found=find_engine_profile(raw)
        if found is not None:
            print()
            return load_engine_profile(found)
        print(f"  unknown engine {raw!r}")


def prompt_review_engine(spec: EngineParameters) -> EngineParameters:
    """Review every calibration input used by the generator."""
    print("— Review / edit engine defaults —")
    print("Enter keeps the value from the selected engine profile.\n")

    name=_ask("Profile/name", spec.name, cast=str)
    displacement=_ask("Displacement (cc)", _num(spec.displacement_cc), cast=float)
    peak_hp=_ask("Peak horsepower", _num(spec.peak_hp), cast=float)
    peak_hp_rpm=_ask("RPM at peak horsepower", _num(spec.peak_hp_rpm), cast=float)
    peak_torque=_ask("Peak torque (lb-ft)", _num(spec.peak_torque_lbft), cast=float)
    peak_torque_rpm=_ask("RPM at peak torque", _num(spec.peak_torque_rpm), cast=float)
    redline=_ask("Redline RPM", _num(spec.redline_rpm), cast=float)

    print("\n  Idle pocket")
    idle_rpm=_ask("Target idle RPM", _num(spec.idle_rpm), cast=float)
    idle_width=_ask("Idle pocket TOTAL width (RPM)", _num(spec.idle_pocket_width), cast=float)
    lower_share=_ask("Idle pocket lower share", _num(spec.idle_pocket_lower_share), cast=float)
    upper_share=_ask("Idle pocket upper share", _num(spec.idle_pocket_upper_share), cast=float)
    idle_target=_ask("Idle timing target (deg BTDC)", _num(spec.idle_timing_target), cast=float)
    idle_delta=_ask("Idle timing delta (+catch / -high RPM)", _num(spec.idle_timing_delta), cast=float)
    idle_map_lo=_ask("Lowest normal warm-idle MAP (kPa abs)", _num(spec.idle_map_lo), cast=float)
    idle_map_hi=_ask("Highest normal warm-idle MAP (kPa abs)", _num(spec.idle_map_hi), cast=float)

    print("\n  Mechanical timing")
    cranking_rpm=_ask("Cranking handoff RPM", _num(spec.cranking_rpm), cast=float)
    cranking_timing=_ask("Cranking timing (deg BTDC)", _num(spec.cranking_timing), cast=float)
    base_timing=_ask("Base / initial timing (deg BTDC)", _num(spec.base_timing), cast=float)
    mech=_ask("Mechanical timing at peak torque (deg BTDC)", _num(spec.mech_timing_at_peak_torque), cast=float)

    p1, p2, p3 = spec.recurve_points
    print("\n  Recurve")
    recurve_rpm_1=_ask("Recurve point 1 RPM", _num(p1[0]), cast=float)
    recurve_timing_1=_ask("Recurve point 1 timing (deg BTDC)", _num(p1[1]), cast=float)
    recurve_rpm_2=_ask("Recurve point 2 RPM", _num(p2[0]), cast=float)
    recurve_timing_2=_ask("Recurve point 2 timing (deg BTDC)", _num(p2[1]), cast=float)
    recurve_rpm_3=_ask("Recurve point 3 RPM", _num(p3[0]), cast=float)
    recurve_timing_3=_ask("Recurve point 3 timing (deg BTDC)", _num(p3[1]), cast=float)

    print("\n  Vacuum")
    vac_map=_ask("Full-vacuum MAP endpoint (kPa abs)", _num(spec.vacuum_full_map_kpa), cast=float)
    vac_total=_ask("Full-vacuum TOTAL timing (deg BTDC)", _num(spec.vacuum_total_timing), cast=float)

    print("\n  Boost")
    boost_psi=_ask("Maximum boost (psi gauge, 0 = NA)", _num(spec.boost_psi), cast=float)
    boost_limit=_ask("Boost TOTAL timing limit (deg BTDC)", _num(spec.boost_timing_limit), cast=float)
    boost_gain=_ask("Boost retard gain (0.60 default)", _num(spec.boost_retard_gain), cast=float)

    print("\n  Limiter / overspeed")
    soft_before=_ask("Soft-limit start before redline (RPM)", _num(spec.soft_limit_rpm_before_redline), cast=float)
    soft_retard=_ask("Soft-limit maximum retard (deg)", _num(spec.soft_limit_retard), cast=float)
    overspeed=_ask("Overspeed axis above redline (RPM)", _num(spec.overspeed_rpm_after_redline), cast=float)

    out=spec.with_overrides(
        name=name,
        displacement_cc=displacement,
        peak_hp=peak_hp,
        peak_hp_rpm=peak_hp_rpm,
        peak_torque_lbft=peak_torque,
        peak_torque_rpm=peak_torque_rpm,
        redline_rpm=redline,
        idle_rpm=idle_rpm,
        idle_pocket_width=idle_width,
        idle_pocket_lower_share=lower_share,
        idle_pocket_upper_share=upper_share,
        idle_timing_target=idle_target,
        idle_timing_delta=idle_delta,
        idle_map_lo=idle_map_lo,
        idle_map_hi=idle_map_hi,
        cranking_rpm=cranking_rpm,
        cranking_timing=cranking_timing,
        base_timing=base_timing,
        mech_timing_at_peak_torque=mech,
        recurve_rpm_1=recurve_rpm_1,
        recurve_timing_1=recurve_timing_1,
        recurve_rpm_2=recurve_rpm_2,
        recurve_timing_2=recurve_timing_2,
        recurve_rpm_3=recurve_rpm_3,
        recurve_timing_3=recurve_timing_3,
        vacuum_full_map_kpa=vac_map,
        vacuum_total_timing=vac_total,
        boost_psi=boost_psi,
        boost_timing_limit=boost_limit,
        boost_retard_gain=boost_gain,
        soft_limit_rpm_before_redline=soft_before,
        soft_limit_retard=soft_retard,
        overspeed_rpm_after_redline=overspeed,
    )
    if out.idle_map_hi <= out.idle_map_lo:
        raise ValueError("idle_map_hi must be greater than idle_map_lo")
    if out.redline_rpm <= out.idle_rpm:
        raise ValueError("redline must be greater than idle RPM")
    if out.boost_retard_gain < 0:
        raise ValueError("boost retard gain must be >= 0")
    validate_recurve(out)
    print("\nFinal calibration:")
    print(describe_spec(out))
    print()
    return out


def prompt_preset(default: str="base") -> str:
    print("— Select table / preset —")
    print("  base  — generated axes using preset cell counts")
    print("  alpha — generated axes using Alpha-oriented cell counts/layout defaults")
    print("  none  — choose rows × columns manually")
    return str(_ask("Preset", default, cast=str)).lower()


def prompt_layout(default: str="default") -> str:
    print("\n— Select display layout —")
    print("  default — load bottom→top, RPM left→right")
    print("  alpha   — RPM down rows, load across columns")
    while True:
        v=str(_ask("Display layout", default, cast=str)).lower()
        if v in {"default","alpha"}: return v
        print("  choose default or alpha")


def prompt_export(default: str="default") -> str:
    print("\n— Select export format —")
    print("  default — load rows, RPM columns")
    print("  alpha   — RPM rows, load columns")
    while True:
        v=str(_ask("Export format", default, cast=str)).lower()
        if v in {"default","alpha"}: return v
        print("  choose default or alpha")


def prompt_output_path(default: str="map.csv") -> str:
    print("\n— Select output filename —")
    return str(_ask("Output file", default, cast=str))
