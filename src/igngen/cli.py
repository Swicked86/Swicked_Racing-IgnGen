from __future__ import annotations

import argparse
import sys

from . import __version__
from .generate import generate_baseline
from .io_files import load_table, save_table
from .model import EngineSpec, generate_table, validate_power
from .presets import PRESETS, get_preset
from .prompt import prompt_engine_spec, prompt_output_path, prompt_preset
from .table import parse_range


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="igngen",
        description="Swicked Racing IgnGen — ignition timing table generator",
    )
    parser.add_argument("--version", action="version", version=f"igngen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Generate a timing table (prompts for engine inputs)")
    p_new.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Axis preset (default: prompted, usually alphalink-high-cam)",
    )
    p_new.add_argument("--rpm", help="RPM start:stop:step (ignored with --preset)")
    p_new.add_argument("--load", help="Load start:stop:step (ignored with --preset)")
    p_new.add_argument(
        "--model",
        choices=("research", "simple"),
        default="research",
        help="research = interactive engine model; simple = idle/cruise/WOT blend",
    )
    p_new.add_argument("--idle", type=float, default=12.0, help="Simple-model light-load °BTDC")
    p_new.add_argument("--cruise", type=float, default=28.0, help="Simple-model cruise °BTDC")
    p_new.add_argument("--wot", type=float, default=18.0, help="Simple-model WOT °BTDC")
    p_new.add_argument("--base-timing", type=int, default=None)
    p_new.add_argument("--idle-rpm", type=int, default=None)
    p_new.add_argument("--peak-torque-rpm", type=int, default=None)
    p_new.add_argument("--peak-hp", type=float, default=None)
    p_new.add_argument("--peak-hp-rpm", type=int, default=None)
    p_new.add_argument("--peak-torque", type=float, default=None)
    p_new.add_argument("--displacement", type=int, default=None)
    p_new.add_argument("--redline", type=int, default=None)
    p_new.add_argument("--boost-psi", type=float, default=None)
    p_new.add_argument("--out", "-o", default=None, help="Output .csv or .json")
    p_new.add_argument("--show", action="store_true", help="Print heatmap after writing")
    p_new.add_argument(
        "--no-prompt",
        action="store_true",
        help="Skip questions; use flags/defaults only",
    )
    p_new.add_argument(
        "--layout",
        choices=("alphalink", "swicked"),
        default="alphalink",
        help="Terminal layout when using --show",
    )

    p_show = sub.add_parser("show", help="Print a timing table heatmap")
    p_show.add_argument("path", help="Input .csv or .json")
    p_show.add_argument("--precision", type=int, default=0)
    p_show.add_argument("--layout", choices=("alphalink", "swicked"), default="alphalink")
    p_show.add_argument("--no-color", action="store_true")

    p_bump = sub.add_parser("bump", help="Add/subtract whole degrees everywhere")
    p_bump.add_argument("path", help="Input table")
    p_bump.add_argument("--by", type=int, required=True, help="Degrees to add (negative OK)")
    p_bump.add_argument("--out", "-o", required=True, help="Output path")

    p_clamp = sub.add_parser("clamp", help="Clamp all cells to min/max")
    p_clamp.add_argument("path", help="Input table")
    p_clamp.add_argument("--min", dest="minimum", type=int, required=True)
    p_clamp.add_argument("--max", dest="maximum", type=int, required=True)
    p_clamp.add_argument("--out", "-o", required=True, help="Output path")

    p_conv = sub.add_parser("convert", help="Convert CSV ↔ JSON")
    p_conv.add_argument("path", help="Input table")
    p_conv.add_argument("--out", "-o", required=True, help="Output path")

    p_presets = sub.add_parser("presets", help="List axis presets")

    args = parser.parse_args(argv)

    try:
        if args.command == "presets":
            for name, preset in sorted(PRESETS.items()):
                print(f"{name}: {preset.description}")
                print(f"  shape: {len(preset.rpm)}×{len(preset.load)}  load_unit={preset.load_unit}")
            return 0

        if args.command == "new":
            interactive = not args.no_prompt and args.model == "research"

            if args.preset:
                preset_name = args.preset
            elif interactive and sys.stdin.isatty():
                preset_name = prompt_preset("alphalink-high-cam")
            else:
                preset_name = "alphalink-high-cam" if not (args.rpm and args.load) else None

            if preset_name:
                preset = get_preset(preset_name)
                rpm = list(preset.rpm)
                load = list(preset.load)
                load_unit = preset.load_unit
            else:
                if not args.rpm or not args.load:
                    raise ValueError("provide --preset or both --rpm and --load")
                rpm = parse_range(args.rpm)
                load = parse_range(args.load)
                load_unit = "inHg"

            out_path = args.out
            if not out_path:
                if interactive and sys.stdin.isatty():
                    out_path = prompt_output_path("map.csv")
                else:
                    raise ValueError("provide --out / -o (or run interactively in a terminal)")

            if args.model == "research":
                if interactive and sys.stdin.isatty():
                    spec = prompt_engine_spec()
                    # CLI flags override answers when explicitly passed
                    if args.displacement is not None:
                        spec.displacement_cc = float(args.displacement)
                    if args.peak_hp is not None:
                        spec.peak_hp = float(args.peak_hp)
                    if args.peak_hp_rpm is not None:
                        spec.peak_hp_rpm = float(args.peak_hp_rpm)
                    if args.peak_torque is not None:
                        spec.peak_torque_lbft = float(args.peak_torque)
                    if args.peak_torque_rpm is not None:
                        spec.peak_torque_rpm = float(args.peak_torque_rpm)
                    if args.redline is not None:
                        spec.redline_rpm = float(args.redline)
                    if args.boost_psi is not None:
                        spec.boost_psi = float(args.boost_psi)
                    if args.base_timing is not None:
                        spec.base_timing = float(args.base_timing)
                    if args.idle_rpm is not None:
                        spec.idle_rpm = float(args.idle_rpm)
                else:
                    spec = EngineSpec(
                        displacement_cc=float(args.displacement or 1600),
                        peak_hp=float(args.peak_hp or 280),
                        peak_hp_rpm=float(args.peak_hp_rpm or 7800),
                        peak_torque_lbft=float(args.peak_torque or 189),
                        peak_torque_rpm=float(args.peak_torque_rpm or 4800),
                        redline_rpm=float(args.redline or 9300),
                        boost_psi=float(args.boost_psi if args.boost_psi is not None else 7),
                        base_timing=float(args.base_timing or 15),
                        idle_rpm=float(args.idle_rpm or 1100),
                    )
                for warning in validate_power(spec):
                    print(f"warning: {warning}", file=sys.stderr)
                table = generate_table(rpm, load, spec=spec, load_unit=load_unit)
                table.load_unit = load_unit
            else:
                table = generate_baseline(
                    rpm,
                    load,
                    idle=args.idle,
                    cruise=args.cruise,
                    wot=args.wot,
                )
                table.load_unit = load_unit

            save_table(table, out_path)
            print(f"Wrote {out_path} ({table.shape[0]}×{table.shape[1]} {load_unit}, whole °)")
            if args.show or (interactive and sys.stdin.isatty()):
                print()
                print(table.format_grid(layout=args.layout, color=True, precision=0))

        elif args.command == "show":
            table = load_table(args.path)
            print(
                table.format_grid(
                    precision=args.precision,
                    layout=args.layout,
                    color=not args.no_color,
                )
            )
        elif args.command == "bump":
            table = load_table(args.path).bump(float(args.by))
            # re-round to whole degrees
            table.values = [[float(int(round(c))) for c in row] for row in table.values]
            save_table(table, args.out)
            print(f"Wrote {args.out} (bumped {args.by:+d}°)")
        elif args.command == "clamp":
            table = load_table(args.path).clamp(float(args.minimum), float(args.maximum))
            table.values = [[float(int(round(c))) for c in row] for row in table.values]
            save_table(table, args.out)
            print(f"Wrote {args.out} (clamped {args.minimum}…{args.maximum})")
        elif args.command == "convert":
            table = load_table(args.path)
            save_table(table, args.out)
            print(f"Wrote {args.out}")
        else:
            parser.error(f"unknown command {args.command}")
    except (OSError, ValueError, KeyError, EOFError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
