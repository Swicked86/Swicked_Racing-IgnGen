from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .generate import generate_baseline
from .io_files import load_table, save_table
from .preset_ini import find_preset_ini
from .presets import PRESETS, get_preset
from .prompt_v2 import (
    prompt_engine_choice_v2,
    prompt_export_v2,
    prompt_layout_v2,
    prompt_output_path_v2,
    prompt_preset_v2,
    prompt_review_engine_v2,
)
from .table import parse_range
from .v2_engine import (
    EngineParameters,
    build_table,
    describe_spec,
    generate_load_axis,
    generate_rpm_axis,
    list_engine_profiles,
    load_engine_profile,
)

_LAYOUTS = ("default", "alpha")
_EXPORTS = ("default", "alpha")
_DEFAULT_PRESET = "base"


def _ask_table_size() -> tuple[int, int]:
    print("\n— Select table size —")
    print("Examples: 8x8, 12x12, 16x20 (load rows × RPM columns)")
    while True:
        raw = input("Size [12x12]: ").strip() or "12x12"
        raw = raw.lower().replace(" ", "")
        if "x" not in raw:
            print("  use rowsxcols, for example 16x20")
            continue
        a, b = raw.split("x", 1)
        try:
            rows, cols = int(a), int(b)
        except ValueError:
            print("  enter integer dimensions")
            continue
        if rows < 2 or cols < 2:
            print("  need at least 2x2")
            continue
        return rows, cols


def _apply_v2_overrides(spec: EngineParameters, args: argparse.Namespace) -> EngineParameters:
    mapping = {
        "displacement_cc": args.displacement,
        "peak_hp": args.peak_hp,
        "peak_hp_rpm": args.peak_hp_rpm,
        "peak_torque_lbft": args.peak_torque,
        "peak_torque_rpm": args.peak_torque_rpm,
        "redline_rpm": args.redline,
        "boost_psi": args.boost_psi,
        "base_timing": args.base_timing,
        "mech_timing_at_peak_torque": args.mech_at_peak_torque,
        "idle_rpm": args.idle_rpm,
        "idle_pocket_width": args.idle_pocket_width,
        "idle_pocket_lower_share": args.idle_pocket_lower_share,
        "idle_pocket_upper_share": args.idle_pocket_upper_share,
        "idle_timing_target": args.idle_timing_target,
        "idle_timing_delta": args.idle_timing_delta,
        "idle_map_lo": args.idle_map_lo,
        "idle_map_hi": args.idle_map_hi,
        "cranking_rpm": args.cranking_rpm,
        "cranking_timing": args.cranking_timing,
        "vacuum_total_timing": args.vacuum_total,
        "vacuum_full_map_kpa": args.vacuum_full_map,
        "boost_timing_limit": args.boost_limit,
        "boost_retard_gain": args.boost_retard_gain,
        "soft_limit_rpm_before_redline": args.soft_limit_before_redline,
        "soft_limit_retard": args.soft_limit_retard,
        "overspeed_rpm_after_redline": args.overspeed_after_redline,
    }
    return spec.with_overrides(**mapping)


def _validate_v2(spec: EngineParameters) -> None:
    if spec.idle_map_hi <= spec.idle_map_lo:
        raise ValueError("idle_map_hi must be greater than idle_map_lo")
    if spec.idle_pocket_width <= 0:
        raise ValueError("idle pocket width must be greater than zero")
    if spec.redline_rpm <= spec.idle_rpm:
        raise ValueError("redline RPM must be greater than idle RPM")
    if spec.boost_retard_gain < 0:
        raise ValueError("boost retard gain must be >= 0")
    if spec.vacuum_full_map_kpa >= spec.atm_kpa:
        raise ValueError("full-vacuum MAP must be below atmospheric MAP")


def main(argv: list[str] | None = None) -> int:
    # Bare `igngen` is the normal interactive workflow, equivalent to
    # `igngen new`. Explicit subcommands and global options keep their normal
    # argparse behavior.
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        argv = ["new"]

    parser = argparse.ArgumentParser(
        prog="igngen",
        description="Swicked Racing IgnGen — ignition timing table generator",
    )
    parser.add_argument("--version", action="version", version=f"igngen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Generate a timing table")
    p_new.add_argument(
        "--preset",
        choices=sorted({p.name for p in PRESETS.values()}) + ["none"],
        default=None,
        help="Axis/table preset. Interactive mode asks when omitted.",
    )
    p_new.add_argument("--engine", default=None, help="Engine profile, e.g. D16Z6")
    p_new.add_argument("--rpm", help="Manual RPM axis start:stop:step")
    p_new.add_argument("--load", help="Manual MAP axis start:stop:step (kPa absolute)")
    p_new.add_argument("--model", choices=("research", "simple"), default="research")
    p_new.add_argument("--idle", type=float, default=12.0)
    p_new.add_argument("--cruise", type=float, default=28.0)
    p_new.add_argument("--wot", type=float, default=18.0)

    # V2 engine/calibration overrides. In interactive mode these are also
    # available in the Review / edit engine defaults step.
    p_new.add_argument("--displacement", type=float)
    p_new.add_argument("--peak-hp", type=float)
    p_new.add_argument("--peak-hp-rpm", type=float)
    p_new.add_argument("--peak-torque", type=float)
    p_new.add_argument("--peak-torque-rpm", type=float)
    p_new.add_argument("--redline", type=float)
    p_new.add_argument("--boost-psi", type=float)
    p_new.add_argument("--base-timing", type=float)
    p_new.add_argument("--mech-at-peak-torque", type=float)
    p_new.add_argument("--idle-rpm", type=float)
    p_new.add_argument("--idle-pocket-width", type=float)
    p_new.add_argument("--idle-pocket-lower-share", type=float)
    p_new.add_argument("--idle-pocket-upper-share", type=float)
    p_new.add_argument("--idle-timing-target", type=float)
    p_new.add_argument("--idle-timing-delta", type=float)
    p_new.add_argument("--idle-map-lo", type=float)
    p_new.add_argument("--idle-map-hi", type=float)
    p_new.add_argument("--cranking-rpm", type=float)
    p_new.add_argument("--cranking-timing", type=float)
    p_new.add_argument("--vacuum-total", type=float)
    p_new.add_argument("--vacuum-full-map", type=float)
    p_new.add_argument("--boost-limit", type=float, help="Absolute total boost timing limit")
    p_new.add_argument("--boost-retard-gain", type=float)
    p_new.add_argument("--soft-limit-before-redline", type=float)
    p_new.add_argument("--soft-limit-retard", type=float)
    p_new.add_argument("--overspeed-after-redline", type=float)

    p_new.add_argument("--out", "-o", default=None)
    p_new.add_argument("--show", action="store_true")
    p_new.add_argument("--no-prompt", action="store_true")
    p_new.add_argument("--layout", choices=_LAYOUTS, default=None)
    p_new.add_argument("--export", choices=_EXPORTS, default=None)
    p_new.add_argument("--size", help="Table size without preset, rowsxcols, e.g. 16x20")

    p_show = sub.add_parser("show", help="Print a timing table heatmap")
    p_show.add_argument("path")
    p_show.add_argument("--precision", type=int, default=0)
    p_show.add_argument("--layout", choices=_LAYOUTS, default="default")
    p_show.add_argument("--no-color", action="store_true")

    p_bump = sub.add_parser("bump", help="Add/subtract whole degrees everywhere")
    p_bump.add_argument("path")
    p_bump.add_argument("--by", type=int, required=True)
    p_bump.add_argument("--out", "-o", required=True)
    p_bump.add_argument("--export", choices=_EXPORTS, default="default")

    p_clamp = sub.add_parser("clamp", help="Clamp all cells to min/max")
    p_clamp.add_argument("path")
    p_clamp.add_argument("--min", dest="minimum", type=int, required=True)
    p_clamp.add_argument("--max", dest="maximum", type=int, required=True)
    p_clamp.add_argument("--out", "-o", required=True)
    p_clamp.add_argument("--export", choices=_EXPORTS, default="default")

    p_conv = sub.add_parser("convert", help="Convert CSV ↔ JSON")
    p_conv.add_argument("path")
    p_conv.add_argument("--out", "-o", required=True)
    p_conv.add_argument("--export", choices=_EXPORTS, default="default")

    sub.add_parser("presets", help="List axis presets")
    sub.add_parser("engines", help="List engine profiles")
    sub.add_parser("vehicles", help="Alias for engines")

    args = parser.parse_args(argv)

    try:
        if args.command == "presets":
            seen: set[str] = set()
            for preset in PRESETS.values():
                if preset.name in seen:
                    continue
                seen.add(preset.name)
                print(f"{preset.name}: {preset.description}")
                print(f"  nominal shape: {len(preset.load)} load × {len(preset.rpm)} RPM")
            return 0

        if args.command in {"engines", "vehicles"}:
            for path in list_engine_profiles():
                spec = load_engine_profile(path)
                print(describe_spec(spec))
                print(f"  file: {path}\n")
            return 0

        if args.command == "new":
            interactive = not args.no_prompt and sys.stdin.isatty()

            if args.model == "simple":
                preset_name = args.preset or _DEFAULT_PRESET
                preset = get_preset(preset_name) if preset_name != "none" else None
                if args.rpm and args.load:
                    rpm = parse_range(args.rpm)
                    load = parse_range(args.load)
                elif preset:
                    rpm, load = list(preset.rpm), list(preset.load)
                else:
                    rows, cols = _ask_table_size() if interactive else (12, 12)
                    rpm = [float(i * 500) for i in range(cols)]
                    load = [float(i * 10) for i in range(rows)]
                table = generate_baseline(rpm, load, idle=args.idle, cruise=args.cruise, wot=args.wot)
                out_path = args.out or "map.csv"
                save_table(table, out_path, export=args.export or "default")
                print(f"Wrote {out_path}")
                if args.show or interactive:
                    print(table.format_grid(layout=args.layout or "default", color=True))
                return 0

            # 1. Select engine.
            if args.engine:
                spec = load_engine_profile(args.engine)
                print(describe_spec(spec))
                print()
            elif interactive:
                spec = prompt_engine_choice_v2()
            else:
                spec = EngineParameters()

            # 2. Review/edit every V2 engine/calibration default.
            if interactive:
                spec = prompt_review_engine_v2(spec)
            spec = _apply_v2_overrides(spec, args)
            _validate_v2(spec)

            # 3. Select table/preset.
            if args.preset is not None:
                preset_name = args.preset
            elif interactive:
                preset_name = prompt_preset_v2(_DEFAULT_PRESET)
            else:
                preset_name = _DEFAULT_PRESET
            if preset_name not in {"none", *[p.name for p in PRESETS.values()]}:
                raise ValueError(f"unknown preset {preset_name!r}")

            preset = get_preset(preset_name) if preset_name != "none" else None
            ini = None
            if preset:
                ini = find_preset_ini(
                    preset.name,
                    search_dirs=[Path.cwd()/"presets", Path(__file__).resolve().parents[2]/"presets"],
                )

            default_layout = ini.layout if ini else (preset.default_layout if preset else "default")
            default_export = ini.export if ini else (preset.default_export if preset else "default")

            # 4. Select display layout.
            if args.layout:
                layout = args.layout
            elif interactive:
                layout = prompt_layout_v2(default_layout)
            else:
                layout = default_layout

            # 5. Select export format.
            if args.export:
                export = args.export
            elif interactive:
                export = prompt_export_v2(default_export)
            else:
                export = default_export

            # Generate V2 axes. Presets define cell counts/layout conventions;
            # engine calibration defines where the breakpoints actually belong.
            if args.rpm and args.load:
                rpm = parse_range(args.rpm)
                load = parse_range(args.load)
                if not any(abs(v-spec.atm_kpa)<0.51 for v in load):
                    raise ValueError(f"manual load axis must contain atmosphere ({spec.atm_kpa:g} kPa)")
            else:
                if args.size:
                    a,b=args.size.lower().replace(" ","").split("x",1)
                    rows,cols=int(a),int(b)
                elif preset:
                    rows,cols=len(preset.load),len(preset.rpm)
                elif interactive:
                    rows,cols=_ask_table_size()
                else:
                    rows,cols=12,12
                rpm=generate_rpm_axis(spec,cols)
                load=generate_load_axis(spec,rows)

            print("\nV2 generated axes:")
            print(f"  RPM:  {[int(x) for x in rpm]}")
            print(f"  Load: {[int(x) for x in load]} kPa abs")

            # 6. Select output filename.
            default_out = f"map-{spec.name.lower()}.csv" if spec.name != "other" else "map.csv"
            if args.out:
                out_path=args.out
            elif interactive:
                out_path=prompt_output_path_v2(default_out)
            else:
                out_path=default_out

            # 7. Generate with the V2 timing model.
            table=build_table(rpm,load,spec)
            save_table(table,out_path,export=export)
            print(f"\nWrote {out_path} ({len(load)} load × {len(rpm)} RPM, V2 timing, export={export}, view={layout})")

            # 8. Show table (always in interactive mode).
            if args.show or interactive:
                print()
                print(table.format_grid(layout=layout,color=True,precision=0))
            return 0

        if args.command == "show":
            table=load_table(args.path)
            print(table.format_grid(precision=args.precision,layout=args.layout,color=not args.no_color))
            return 0

        if args.command == "bump":
            table=load_table(args.path).bump(float(args.by))
            save_table(table,args.out,export=args.export)
            print(f"Wrote {args.out} (bumped {args.by:+d}°)")
            return 0

        if args.command == "clamp":
            table=load_table(args.path).clamp(float(args.minimum),float(args.maximum))
            save_table(table,args.out,export=args.export)
            print(f"Wrote {args.out} (clamped {args.minimum}…{args.maximum})")
            return 0

        if args.command == "convert":
            table=load_table(args.path)
            save_table(table,args.out,export=args.export)
            print(f"Wrote {args.out}")
            return 0

        parser.error(f"unknown command {args.command}")
    except (OSError, ValueError, KeyError, EOFError) as exc:
        print(f"error: {exc}",file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())