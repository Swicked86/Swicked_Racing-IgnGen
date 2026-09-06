from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .axes import generate_load_axis, generate_rpm_axis
from .generate import generate_baseline
from .io_files import load_table, save_table
from .model import (
    EngineSpec,
    describe_mechanical_curve,
    generate_table,
    validate_power,
)
from .preset_ini import find_preset_ini
from .presets import PRESETS, get_preset
from .prompt import prompt_engine_spec, prompt_output_path, prompt_preset
from .table import parse_range

_LAYOUTS = ("swicked", "alpha")
_EXPORTS = ("swicked", "alpha")
_DEFAULT_PRESET = "base"
_DEFAULT_LAYERS = "mechanical"


def _ask_table_size() -> tuple[int, int]:
    print("Table size (no preset) — examples: 8x8, 12x12, 12x24")
    while True:
        raw = input("Size [rows x cols, default 12x12]: ").strip() or "12x12"
        raw = raw.lower().replace(" ", "")
        if "x" not in raw:
            print("  use like 12x12")
            continue
        a, b = raw.split("x", 1)
        try:
            rows, cols = int(a), int(b)
        except ValueError:
            print("  enter integers")
            continue
        if rows < 2 or cols < 2:
            print("  need at least 2x2")
            continue
        return rows, cols


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
        choices=sorted({p.name for p in PRESETS.values()}) + ["none"],
        default=_DEFAULT_PRESET,
        help=f"Preset name (default: {_DEFAULT_PRESET}), or 'none' to choose table size",
    )
    p_new.add_argument(
        "--layers",
        choices=("mechanical", "full"),
        default=_DEFAULT_LAYERS,
        help="Timing layers to apply (default: mechanical only — review before full)",
    )
    p_new.add_argument("--rpm", help="RPM start:stop:step (overrides generated/fixed axes)")
    p_new.add_argument("--load", help="Load start:stop:step (overrides generated/fixed axes)")
    p_new.add_argument("--model", choices=("research", "simple"), default="research")
    p_new.add_argument("--idle", type=float, default=12.0)
    p_new.add_argument("--cruise", type=float, default=28.0)
    p_new.add_argument("--wot", type=float, default=18.0)
    p_new.add_argument("--base-timing", type=int, default=None)
    p_new.add_argument("--mech-at-peak-torque", type=int, default=None)
    p_new.add_argument("--idle-rpm", type=int, default=None)
    p_new.add_argument("--peak-torque-rpm", type=int, default=None)
    p_new.add_argument("--peak-hp", type=float, default=None)
    p_new.add_argument("--peak-hp-rpm", type=int, default=None)
    p_new.add_argument("--peak-torque", type=float, default=None)
    p_new.add_argument("--displacement", type=int, default=None)
    p_new.add_argument("--redline", type=int, default=None)
    p_new.add_argument("--boost-psi", type=float, default=None)
    p_new.add_argument("--out", "-o", default=None)
    p_new.add_argument("--show", action="store_true")
    p_new.add_argument("--no-prompt", action="store_true")
    p_new.add_argument("--layout", choices=_LAYOUTS, default=None)
    p_new.add_argument("--export", choices=_EXPORTS, default=None)
    p_new.add_argument("--size", help="Table size when no preset, e.g. 12x12 (rows x cols)")

    p_show = sub.add_parser("show", help="Print a timing table heatmap")
    p_show.add_argument("path")
    p_show.add_argument("--precision", type=int, default=0)
    p_show.add_argument("--layout", choices=_LAYOUTS, default="swicked")
    p_show.add_argument("--no-color", action="store_true")

    p_bump = sub.add_parser("bump", help="Add/subtract whole degrees everywhere")
    p_bump.add_argument("path")
    p_bump.add_argument("--by", type=int, required=True)
    p_bump.add_argument("--out", "-o", required=True)
    p_bump.add_argument("--export", choices=_EXPORTS, default="swicked")

    p_clamp = sub.add_parser("clamp", help="Clamp all cells to min/max")
    p_clamp.add_argument("path")
    p_clamp.add_argument("--min", dest="minimum", type=int, required=True)
    p_clamp.add_argument("--max", dest="maximum", type=int, required=True)
    p_clamp.add_argument("--out", "-o", required=True)
    p_clamp.add_argument("--export", choices=_EXPORTS, default="swicked")

    p_conv = sub.add_parser("convert", help="Convert CSV ↔ JSON")
    p_conv.add_argument("path")
    p_conv.add_argument("--out", "-o", required=True)
    p_conv.add_argument("--export", choices=_EXPORTS, default="swicked")

    sub.add_parser("presets", help="List axis presets")

    args = parser.parse_args(argv)

    try:
        if args.command == "presets":
            seen: set[str] = set()
            for preset in PRESETS.values():
                if preset.name in seen:
                    continue
                seen.add(preset.name)
                ini = find_preset_ini(preset.name, search_dirs=[Path.cwd() / "presets"])
                ini_note = f"  ini={ini.path}" if ini else "  ini=(missing)"
                print(f"{preset.name}: {preset.description}")
                print(
                    f"  shape: {len(preset.rpm)}×{len(preset.load)}  "
                    f"load_unit={preset.load_unit}  origin={preset.origin}{ini_note}"
                )
            return 0

        if args.command == "new":
            interactive = not args.no_prompt and args.model == "research"
            layers = args.layers

            if args.preset == "none":
                preset_name = None
            elif args.preset:
                preset_name = args.preset
            elif interactive and sys.stdin.isatty():
                preset_name = prompt_preset(_DEFAULT_PRESET)
                if preset_name.strip().lower() in {"none", "no", "-"}:
                    preset_name = None
            else:
                preset_name = _DEFAULT_PRESET if not (args.rpm and args.load) else None

            preset = None
            ini = None
            if preset_name:
                preset = get_preset(preset_name)
                ini = find_preset_ini(
                    preset_name,
                    search_dirs=[
                        Path.cwd() / "presets",
                        Path(__file__).resolve().parents[2] / "presets",
                    ],
                )

            if ini:
                layout = args.layout or ini.layout
                export = args.export or ini.export
                load_unit = ini.load_unit
            elif preset:
                layout = args.layout or preset.default_layout
                export = args.export or preset.default_export
                load_unit = preset.load_unit
            else:
                layout = args.layout or "swicked"
                export = args.export or "swicked"
                load_unit = "kPa"

            if args.model == "research":
                if interactive and sys.stdin.isatty():
                    spec = prompt_engine_spec(layers=layers)
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
                    if args.mech_at_peak_torque is not None:
                        spec.mech_timing_at_peak_torque = float(args.mech_at_peak_torque)
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
                        base_timing=float(args.base_timing or 10),
                        mech_timing_at_peak_torque=float(args.mech_at_peak_torque or 32),
                        idle_rpm=float(args.idle_rpm or 1100),
                    )
                for warning in validate_power(spec):
                    print(f"warning: {warning}", file=sys.stderr)
                    if "Peak HP implies more torque" in warning:
                        tq_needed = (spec.peak_hp * 5252.0) / max(spec.peak_hp_rpm, 1.0)
                        print(
                            f"note: using estimated peak torque {tq_needed:.0f} lb-ft "
                            f"at {spec.peak_hp_rpm:.0f} RPM for consistency",
                            file=sys.stderr,
                        )
                        spec.peak_torque_lbft = tq_needed
            else:
                spec = EngineSpec()

            if args.rpm and args.load:
                rpm = parse_range(args.rpm)
                load = parse_range(args.load)
            elif preset and (not ini or ini.axes == "fixed"):
                rpm = list(preset.rpm)
                load = list(preset.load)
                load_unit = preset.load_unit
            elif preset and ini and ini.axes == "generated":
                rpm_n = ini.rpm_count or len(preset.rpm)
                load_n = ini.load_count or len(preset.load)
                rpm = generate_rpm_axis(spec, rpm_n)
                load = generate_load_axis(spec, load_n, unit=load_unit)
            else:
                if args.size:
                    a, b = args.size.lower().replace(" ", "").split("x", 1)
                    rows, cols = int(a), int(b)
                elif interactive and sys.stdin.isatty():
                    rows, cols = _ask_table_size()
                else:
                    rows, cols = 12, 12
                rpm = generate_rpm_axis(spec, cols)
                load = generate_load_axis(spec, rows, unit=load_unit)
                print(f"Generated axes: {cols} RPM × {rows} load ({load_unit})")
                print(f"  RPM:  {rpm}")
                print(f"  Load: {load}")

            out_path = args.out
            if not out_path:
                if interactive and sys.stdin.isatty():
                    out_path = prompt_output_path("map.csv")
                else:
                    raise ValueError("provide --out / -o")

            if args.model == "research":
                table = generate_table(
                    rpm, load, spec=spec, load_unit=load_unit, layers=layers
                )
            else:
                table = generate_baseline(
                    rpm, load, idle=args.idle, cruise=args.cruise, wot=args.wot
                )
                table.load_unit = load_unit

            save_table(table, out_path, export=export)
            origin = (
                ini.origin
                if ini
                else (preset.origin if preset else "bottom_left")
            )
            print(describe_mechanical_curve(spec))
            if layers == "mechanical":
                print(
                    "(load axis is unused for timing in this layer — "
                    "every load row matches the RPM curve)"
                )
            print(
                f"Wrote {out_path} ({table.shape[0]}×{table.shape[1]} {table.load_unit}, "
                f"whole °, layers={layers}, origin={origin}, export={export}, view={layout})"
            )
            if args.show or (interactive and sys.stdin.isatty()):
                print()
                print(table.format_grid(layout=layout, color=True, precision=0))

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
            save_table(table, args.out, export=args.export)
            print(f"Wrote {args.out} (bumped {args.by:+d}°)")
        elif args.command == "clamp":
            table = load_table(args.path).clamp(float(args.minimum), float(args.maximum))
            save_table(table, args.out, export=args.export)
            print(f"Wrote {args.out} (clamped {args.minimum}…{args.maximum})")
        elif args.command == "convert":
            table = load_table(args.path)
            save_table(table, args.out, export=args.export)
            print(f"Wrote {args.out}")
        else:
            parser.error(f"unknown command {args.command}")
    except (OSError, ValueError, KeyError, EOFError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
