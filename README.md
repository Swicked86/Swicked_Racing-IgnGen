# Swicked Racing — IgnGen

Python CLI that generates **ignition timing tables** for tuners — aimed first at **ALPHAlink-style Honda ECU grids** (RPM × Load in inHg, heatmap-friendly values).

High vs low cam tables are the same shape for now; we can specialize later.

## Install

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## ALPHAlink quickstart (20×16 High Cam grid)

```bash
igngen presets
igngen new --preset alphalink-high-cam --out high_cam_ignition.csv --show
```

That uses the exact RPM / Load(inHg) breakpoints from an ALPHAlink High Cam Ignition table:

- **20 RPM rows** (0 … 9000)
- **16 Load columns** (−90.1 … 77.7 inHg, vacuum → boost)
- CSV layout matches ALPHAlink: `rpm` in the first column, load across the top

`--show` prints a **heatmap** (red/pink = more advance, blue = low/zero) in the ALPHAlink row/column orientation.

## Research timing model

Default `--model research` builds the map from engine landmarks (base timing, idle pocket, peak-torque anchor, vacuum advance, boost retard, soft redline retard) — the Swicked Racing / ChatGPT research direction — not a single idle/cruise/WOT blend.

```bash
igngen new --preset alphalink-high-cam \
  --base-timing 15 --idle-rpm 1100 \
  --peak-torque-rpm 4800 --peak-hp-rpm 7800 \
  --redline 9300 --boost-psi 7 \
  --out map.csv --show
```

Use `--model simple` for the older idle/cruise/WOT blend.

## Commands

| Command | What it does |
|---------|----------------|
| `igngen presets` | List axis presets |
| `igngen new` | Generate a table (preset or custom axes) |
| `igngen show` | Heatmap print (`--layout alphalink\|swicked`) |
| `igngen bump` / `clamp` / `convert` | Edit / convert tables |

## Orientation layers

Internal storage is always **RPM ascending × load ascending**.

- **Display `alphalink`**: RPM top→bottom, load left→right (matches the ALPHAlink UI)
- **Display `swicked`**: load high→low rows, RPM left→right (preferred reading layout from research notes)
- **CSV export**: ALPHAlink-friendly by default (rpm rows, load columns)

## Tests

```bash
pytest
```

## Notes / safety

Generated maps are **starting points for calibration**, not safe-for-engine prescriptions. Validate on a dyno with knock monitoring. Proprietary `.bin` writers are out of scope for v1 — CSV/JSON bridge into tools like ALPHAlink first.
