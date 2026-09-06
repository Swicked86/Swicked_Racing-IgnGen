from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .generate import generate_baseline
from .io_files import load_table, save_table
from .table import parse_range


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="igngen",
        description="Swicked Racing IgnGen — ignition timing table generator",
    )
    parser.add_argument("--version", action="version", version=f"igngen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Generate a baseline timing table")
    p_new.add_argument("--rpm", default="500:8000:500", help="RPM start:stop:step")
    p_new.add_argument("--load", default="20:100:10", help="Load start:stop:step")
    p_new.add_argument("--idle", type=float, default=12.0, help="Light-load timing °BTDC")
    p_new.add_argument("--cruise", type=float, default=28.0, help="Cruise timing °BTDC")
    p_new.add_argument("--wot", type=float, default=18.0, help="WOT timing °BTDC")
    p_new.add_argument("--rpm-base", type=float, default=1000.0, help="RPM where advance curve starts")
    p_new.add_argument(
        "--rpm-slope",
        type=float,
        default=1.5,
        help="Extra degrees per 1000 RPM above rpm-base",
    )
    p_new.add_argument("--min", dest="minimum", type=float, default=0.0)
    p_new.add_argument("--max", dest="maximum", type=float, default=45.0)
    p_new.add_argument("--out", "-o", required=True, help="Output .csv or .json")
    p_new.add_argument("--show", action="store_true", help="Print table after writing")

    p_show = sub.add_parser("show", help="Print a timing table")
    p_show.add_argument("path", help="Input .csv or .json")
    p_show.add_argument("--precision", type=int, default=1)

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

    args = parser.parse_args(argv)

    try:
        if args.command == "new":
            table = generate_baseline(
                parse_range(args.rpm),
                parse_range(args.load),
                idle=args.idle,
                cruise=args.cruise,
                wot=args.wot,
                rpm_base=args.rpm_base,
                rpm_slope=args.rpm_slope,
                minimum=args.minimum,
                maximum=args.maximum,
            )
            save_table(table, args.out)
            print(f"Wrote {args.out} ({table.shape[0]}×{table.shape[1]})")
            if args.show:
                print()
                print(table.format_grid())
        elif args.command == "show":
            table = load_table(args.path)
            print(table.format_grid(precision=args.precision))
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
