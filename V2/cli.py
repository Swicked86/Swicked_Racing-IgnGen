from __future__ import annotations

import argparse
from dataclasses import fields

from .axes import generate_load_axis, generate_rpm_axis
from .profiles import (
    EngineParameters,
    list_engine_profiles,
    load_engine_profile,
    save_engine_profile,
)
from .render import build_table
from .timing import suggested_boost_limit_from_rate


def _csv_axis(value: str | None) -> list[float] | None:
    if not value:
        return None
    points = [float(part.strip()) for part in value.split(",") if part.strip()]
    if len(points) < 2:
        raise ValueError("manual axis requires at least two comma-separated values")
    if points != sorted(points) or len(points) != len(set(points)):
        raise ValueError("manual axis values must be unique and strictly increasing")
    return points


def _override_dict(args: argparse.Namespace) -> dict[str, float | str | None]:
    names = {field.name for field in fields(EngineParameters)}
    return {
        name: getattr(args, name)
        for name in names
        if hasattr(args, name) and getattr(args, name) is not None
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "IgnGen V2 research CLI. Engine INI values are defaults; CLI edits are "
            "temporary unless --save-engine is used."
        )
    )
    parser.add_argument(
        "--engine",
        default="other",
        help="Engine profile from engines/*.ini, or 'other' for generic defaults",
    )
    parser.add_argument("--rpm-cells", type=int, default=16)
    parser.add_argument("--load-cells", type=int, default=12)
    parser.add_argument("--rpm-values", help="Manual comma-separated RPM axis")
    parser.add_argument("--load-values", help="Manual comma-separated kPa-absolute load axis")
    parser.add_argument("--layout", choices=("default", "alpha"), default="default")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--list-engines", action="store_true")

    # Temporary engine/calibration overrides. These do not touch the selected
    # engine INI unless the user explicitly requests --save-engine.
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument("--displacement-cc", dest="displacement_cc", type=float)
    parser.add_argument("--peak-hp", dest="peak_hp", type=float)
    parser.add_argument("--peak-hp-rpm", dest="peak_hp_rpm", type=float)
    parser.add_argument("--peak-torque-lbft", dest="peak_torque_lbft", type=float)
    parser.add_argument("--peak-torque-rpm", dest="peak_torque_rpm", type=float)
    parser.add_argument("--redline-rpm", dest="redline_rpm", type=float)
    parser.add_argument("--boost-psi", dest="boost_psi", type=float)

    parser.add_argument("--idle-rpm", dest="idle_rpm", type=float)
    parser.add_argument("--idle-pocket-width", dest="idle_pocket_width", type=float)
    parser.add_argument(
        "--idle-pocket-lower-share", dest="idle_pocket_lower_share", type=float
    )
    parser.add_argument(
        "--idle-pocket-upper-share", dest="idle_pocket_upper_share", type=float
    )
    parser.add_argument("--idle-timing-target", dest="idle_timing_target", type=float)
    parser.add_argument("--idle-timing-delta", dest="idle_timing_delta", type=float)
    parser.add_argument(
        "--idle-map-lo",
        dest="idle_map_lo",
        type=float,
        help="Temporary warm-idle MAP lower bound, kPa absolute",
    )
    parser.add_argument(
        "--idle-map-hi",
        dest="idle_map_hi",
        type=float,
        help="Temporary warm-idle MAP upper bound, kPa absolute",
    )

    parser.add_argument("--cranking-rpm", dest="cranking_rpm", type=float)
    parser.add_argument("--cranking-timing", dest="cranking_timing", type=float)
    parser.add_argument("--base-timing", dest="base_timing", type=float)
    parser.add_argument(
        "--mech-at-peak-torque", dest="mech_timing_at_peak_torque", type=float
    )
    parser.add_argument("--vacuum-total", dest="vacuum_total_timing", type=float)
    parser.add_argument(
        "--vacuum-full-map", dest="vacuum_full_map_kpa", type=float
    )
    parser.add_argument("--boost-timing-limit", dest="boost_timing_limit", type=float)
    parser.add_argument(
        "--boost-retard-deg-per-psi", dest="boost_retard_deg_per_psi", type=float
    )
    parser.add_argument("--atm-kpa", dest="atm_kpa", type=float)
    parser.add_argument("--map-floor-kpa", dest="map_floor_kpa", type=float)
    parser.add_argument(
        "--soft-limit-rpm-before-redline",
        dest="soft_limit_rpm_before_redline",
        type=float,
    )
    parser.add_argument("--soft-limit-retard", dest="soft_limit_retard", type=float)
    parser.add_argument(
        "--overspeed-rpm-after-redline",
        dest="overspeed_rpm_after_redline",
        type=float,
    )

    parser.add_argument(
        "--save-engine",
        metavar="NAME_OR_PATH",
        help=(
            "Save the current selected profile plus temporary overrides as a new "
            "engine INI. A bare name is written under engines/."
        ),
    )
    parser.add_argument(
        "--overwrite-engine",
        action="store_true",
        help="Allow --save-engine to replace an existing local INI",
    )

    args = parser.parse_args(argv)

    if args.list_engines:
        for path in list_engine_profiles():
            print(path.stem)
        print("other")
        return 0

    spec = load_engine_profile(args.engine)
    spec = spec.with_overrides(**_override_dict(args))

    if spec.idle_map_hi <= spec.idle_map_lo:
        raise ValueError("idle_map_hi must be greater than idle_map_lo")
    if spec.idle_pocket_width <= 0:
        raise ValueError("idle_pocket_width must be greater than zero")
    if spec.redline_rpm <= spec.idle_rpm:
        raise ValueError("redline_rpm must be greater than idle_rpm")

    manual_rpm = _csv_axis(args.rpm_values)
    manual_load = _csv_axis(args.load_values)
    rpm_axis = manual_rpm or generate_rpm_axis(spec, args.rpm_cells)
    load_axis = manual_load or generate_load_axis(spec, args.load_cells)

    # Manual load axes still obey the mandatory atmosphere invariant.
    if manual_load is not None and not any(abs(v - spec.atm_kpa) < 1e-9 for v in load_axis):
        raise ValueError(
            f"manual load axis must include atmosphere crossover ({spec.atm_kpa:g} kPa)"
        )

    table = build_table(rpm_axis, load_axis, spec)

    catch_timing, target_timing, upper_timing = spec.derived_idle_targets()
    print(f"{spec.name}: {spec.description}")
    print(f"RPM:  {[int(v) if float(v).is_integer() else v for v in rpm_axis]}")
    print(f"Load: {[int(v) if float(v).is_integer() else v for v in load_axis]} kPa abs")
    print(
        "Idle pocket: "
        f"{spec.idle_pocket_lo_rpm:g}/{spec.idle_rpm:g}/{spec.idle_pocket_hi_rpm:g} RPM, "
        f"{catch_timing:g}/{target_timing:g}/{upper_timing:g} deg, "
        f"MAP {spec.idle_map_lo:g}-{spec.idle_map_hi:g} kPa abs"
    )
    print(
        "Timing anchors: "
        f"base={spec.base_timing:.0f}°, "
        f"peak-mech={spec.mech_timing_at_peak_torque:.0f}°, "
        f"vac-total={spec.vacuum_total_timing:.0f}° @ <= {spec.vacuum_full_map_kpa:.0f} kPa, "
        f"boost-target={spec.boost_timing_limit:.0f}°"
    )
    if spec.boost_psi > 0:
        print(
            f"{spec.boost_retard_deg_per_psi:g}°/psi heuristic would suggest "
            f"~{suggested_boost_limit_from_rate(spec):.1f}° at {spec.boost_psi:.1f} psi; "
            "profile target remains authoritative."
        )

    if args.save_engine:
        saved = save_engine_profile(
            spec,
            args.save_engine,
            overwrite=args.overwrite_engine,
        )
        print(f"Saved engine profile: {saved}")

    if args.show:
        print()
        print(table.format_grid(layout=args.layout, color=True, precision=0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
