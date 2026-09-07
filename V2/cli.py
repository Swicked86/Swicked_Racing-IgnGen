from __future__ import annotations

import argparse

from .axes import generate_load_axis, generate_rpm_axis
from .profiles import list_engine_profiles, load_engine_profile
from .render import build_table
from .timing import suggested_boost_limit_from_rate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IgnGen V2 research CLI")
    parser.add_argument("--engine", help="Engine profile name from engines/*.ini")
    parser.add_argument("--rpm-cells", type=int, default=16)
    parser.add_argument("--load-cells", type=int, default=12)
    parser.add_argument("--layout", choices=("default", "alpha"), default="default")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--list-engines", action="store_true")
    args = parser.parse_args(argv)

    if args.list_engines:
        for path in list_engine_profiles():
            print(path.stem)
        return 0

    if not args.engine:
        parser.error("--engine is required unless --list-engines is used")

    spec = load_engine_profile(args.engine)
    rpm_axis = generate_rpm_axis(spec, args.rpm_cells)
    load_axis = generate_load_axis(spec, args.load_cells)
    table = build_table(rpm_axis, load_axis, spec)

    print(f"{spec.name}: {spec.description}")
    print(f"RPM:  {[int(v) for v in rpm_axis]}")
    print(f"Load: {[int(v) for v in load_axis]} kPa abs")
    print(
        "Timing anchors: "
        f"base={spec.base_timing:.0f}°, "
        f"peak-mech={spec.mech_timing_at_peak_torque:.0f}°, "
        f"vac-total={spec.vacuum_total_timing:.0f}° @ <= {spec.vacuum_full_map_kpa:.0f} kPa, "
        f"boost-target={spec.boost_timing_limit:.0f}°"
    )
    if spec.boost_psi > 0:
        print(
            f"2°/psi heuristic would suggest ~{suggested_boost_limit_from_rate(spec):.1f}° "
            f"at {spec.boost_psi:.1f} psi; profile target remains authoritative."
        )

    if args.show:
        print()
        print(table.format_grid(layout=args.layout, color=True, precision=0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
