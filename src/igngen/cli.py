from __future__ import annotations

import argparse
import sys

from . import __version__
from .generate import generate_baseline
from .io_files import load_table, save_table
from .model import EngineSpec, generate_table, validate_power
from .presets import PRESETS, get_preset
from .table import parse_range


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="igngen",
        description="Swicked Racing IgnGen — ignition timing table generator",
    )
    parser.add_argument("--version", action="version", version=f"igngen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Generate a timing table")
    p_new.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="Axis preset (e.g. alphalink-high-cam = 20×16 inHg grid)",
    )
    p_new.add_argument("--rpm", help="RPM start:stop:step (ignored with --preset)")
    p_new.add_argument("--load", help="Load start:stop:step (ignored with --preset)")
    p_new.add_argument(
        "--model",
        choices=("research", "simple"),
        default="research",
        help="research = ChatGPT/Swicked model; simple = idle/cruise/WOT blend",
    )
    p_new.add_argument("--idle", type=float, default=12.0, help="Simple-model light-load °BTDC")
    p_new.add_argument("--cruise", type=float, default=28.0, help="Simple-model cruise °BTDC")
    p_new.add_argument("--wot", type=float, default=18.0, help="Simple-model WOT °BTDC")
    p_new.add_argument("--base-timing", type=float, default=15.0)
    p_new.add_argument("--idle-rpm", type=float, default=1100.0)
    p_new.add_argument("--peak-torque-rpm", type=float, default=4800.0)
    p_new.add_argument("--peak-hp-rpm", type=float, default=7800.0)
    p_new.add_argument("--redline", type=float, default=9300.0)
    p_new.add_argument("--boost-psi", type=float, default=7.0)
    p_new.add_argument("--out", "-o", required=True, help="Output .csv or .json")
    p_new.add_argument("--show", action="store_true", help="Print heatmap after writing")
    p_new.add_argument(
        "--layout",
        choices=("alphalink", "swicked"),
        default="alphalink",
        help="Terminal layout when using --show",
    )

    p_show = sub.add_parser("show", help="Print a timing table heatmap")
    p_show.add_argument("path", help="Input .csv or .json")
    p_show.add_argument("--precision", type=int, default=2)
    p_show.add_argument("--layout", choices=("alphalink", "swicked"), default="alphalink")
    p_show.add_argument("--no-color", action="store_true")

    p_bump = sub.add_parser("bump", help="Add/subtract degrees everywhere")
    p_bump.add_argument("path", help="Input table")
    p_bump.add_argument("--by", type=float, required=True, help="Degrees to add (negative OK)")
    p_bump.add_argument("--out", "-o", required=True, help="Output path")

    p_clamp = sub.add_parser("clamp", help="Clamp all cells to min/max")
    p_clamp.add_argument("path", help="Input table")
    p_clamp.add_argument("--min", dest="minimum", type=float, required=True)
    p_clamp.add_argument("--max", dest="maximum", type=float, required=True)
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
            if args.preset:
                preset = get_preset(args.preset)
                rpm = list(preset.rpm)
                load = list(preset.load)
                load_unit = preset.load_unit
            else:
                if not args.rpm or not args.load:
                    raise ValueError("provide --preset or both --rpm and --load")
                rpm = parse_range(args.rpm)
                load = parse_range(args.load)
                load_unit = "inHg"

            if args.model == "research":
                spec = EngineSpec(
                    base_timing=args.base_timing,
                    idle_rpm=args.idle_rpm,
                    peak_torque_rpm=args.peak_torque_rpm,
                    peak_hp_rpm=args.peak_hp_rpm,
                    redline_rpm=args.redline,
                    boost_psi=args.boost_psi,
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

            save_table(table, args.out)
            print(f"Wrote {args.out} ({table.shape[0]}×{table.shape[1]} {load_unit})")
            if args.show:
                print()
                print(table.format_grid(layout=args.layout, color=True))

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
            table = load_table(args.path).bump(args.by)
            save_table(table, args.out)
            print(f"Wrote {args.out} (bumped {args.by:+g}°)")
        elif args.command == "clamp":
            table = load_table(args.path).clamp(args.minimum, args.maximum)
            save_table(table, args.out)
            print(f"Wrote {args.out} (clamped {args.minimum}…{args.maximum})")
        elif args.command == "convert":
            table = load_table(args.path)
            save_table(table, args.out)
            print(f"Wrote {args.out}")
        else:
            parser.error(f"unknown command {args.command}")
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
