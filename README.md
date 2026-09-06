# Swicked Racing — IgnGen

Python CLI for generating and editing **ignition timing tables** (spark advance maps).

IgnGen works with portable **CSV / JSON** tables (RPM × load grids of degrees BTDC). ECU-specific binary exporters can come later — v1 stays tuner-friendly and format-agnostic.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Quickstart

Generate a baseline map and write CSV:

```bash
igngen new --rpm 500:8000:500 --load 20:100:10 \
  --idle 12 --cruise 28 --wot 18 \
  --out timing.csv

igngen show timing.csv
igngen bump timing.csv --by 1.5 --out timing_plus.csv
igngen clamp timing.csv --min 0 --max 40 --out timing_clamped.csv
```

## Timing model (v1 assumptions)

Baseline maps blend three targets across the load axis:

| Region | Load (default interpretation) | Target |
|--------|-------------------------------|--------|
| Idle / light | low load | `--idle` °BTDC |
| Cruise | mid load | `--cruise` °BTDC |
| WOT | high load | `--wot` °BTDC |

An optional RPM advance curve adds degrees as RPM rises (`--rpm-slope` ° per 1000 RPM above `--rpm-base`). Values are then clamped to `--min` / `--max`.

These are **starting points for tuning**, not safe-for-engine prescriptions. Always validate on a dyno / with proper knock monitoring.

## Commands

| Command | What it does |
|---------|----------------|
| `igngen new` | Create a baseline table and export CSV/JSON |
| `igngen show` | Print a table as a terminal grid |
| `igngen bump` | Add/subtract degrees (global) |
| `igngen clamp` | Clamp all cells to a min/max |
| `igngen convert` | Convert between CSV and JSON |

Run `igngen --help` or `igngen <command> --help` for flags.

## CSV layout

- First column header: `rpm`
- Remaining headers: load breakpoints (numbers)
- Each row: RPM, then timing cells

Example:

```csv
rpm,20,30,40,50,60,70,80,90,100
500,12.0,14.0,...
1000,13.0,15.0,...
```

## Tests

```bash
pytest
```

## Roadmap ideas

- Region-based bump (RPM/load window)
- ECU-specific exporters (Haltech, Holley, MegaSquirt, …)
- Import from common tune formats
