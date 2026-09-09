# Swicked Racing IgnGen

IgnGen is an ignition timing table generator for creating **explainable starting calibration maps** from a small set of engine and calibration parameters.

It is designed around the behavior of a well-developed distributor-style ignition system:

- an RPM-driven mechanical advance curve with user-adjustable **Recurve** control points
- vacuum advance below atmospheric pressure
- boost retard above atmospheric pressure
- a protected idle timing pocket
- a configurable high-RPM soft-limit / overspeed region
- nonlinear RPM and load-axis generation that preserves important engine landmarks

IgnGen includes both a command-line interface and a compact browser/desktop GUI intended to work standalone or as a generator embedded into another tuning application.

## GUI Preview

![IgnGen generated ignition table](docs/images/igngen-gui.png)

*IgnGen showing the main engine/profile controls and generated ignition timing surface.*

### Advanced calibration options

![IgnGen advanced calibration options](docs/images/igngen-advanced-settings.png)

*Advanced controls contain engine landmarks, mechanical timing, Recurve, vacuum/boost, idle pocket, and limiter/overspeed settings.*

> **Calibration warning**
>
> IgnGen generates starting calibration tables, not guaranteed engine-safe prescriptions. Final ignition timing must be verified on the actual engine with appropriate instrumentation, fuel-quality controls, knock monitoring, and dyno/road testing. The user is responsible for the resulting calibration and engine operation.

---

## Quick start

### Requirements

- Python 3.10 or newer
- Linux, Windows, WSL, or another platform capable of running Python

Clone the repository and install it in editable mode:

```bash
git clone https://github.com/Swicked86/Swicked_Racing-IgnGen.git
cd Swicked_Racing-IgnGen
python -m pip install -e .
```

For development and testing:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

---

## GUI

### Browser mode

```bash
igngen-gui --browser
```

IgnGen starts a localhost HTTP service and opens the interface in the default browser.

### Desktop-window mode

```bash
python -m pip install -e ".[gui]"
igngen-gui
```

IgnGen uses `pywebview` when available and falls back to browser mode if it is not installed.

### GUI workflow

1. Select an engine profile.
2. Select load-cell and RPM-cell counts.
3. Select the display view.
4. Select the export format.
5. Expand **Advanced calibration options** when calibration changes are required.
6. Click **Generate Table**.

The generated ignition table appears directly below the configuration panel.

### Mechanical Recurve editor

The mechanical advance curve is no longer limited to a straight line from idle to peak torque. Under:

```text
Advanced calibration options
    → Mechanical Recurve
```

IgnGen provides three user-set RPM/timing control points:

```text
Point 1 RPM / timing
Point 2 RPM / timing
Point 3 RPM / timing
```

The GUI also provides a draggable graph. Dragging a point updates the numeric fields; editing the numeric fields redraws the graph.

Point 1 may be positioned at **target idle RPM**, allowing timing to rise immediately as the engine leaves the protected idle MAP region. The idle pocket still has priority inside its configured RPM × MAP rectangle.

For example:

```text
idle target:       1100 RPM
idle pocket MAP:   30–45 kPa
Recurve Point 1:   1100 RPM / 18°
```

At idle MAP, the protected idle timing remains in control. At the same RPM above the idle-pocket MAP range, the Recurve-defined mechanical timing may apply. The target ECU's normal table interpolation blends the surrounding cells.

The Recurve graph begins at the **lower RPM edge of the idle pocket**, not at target idle RPM. With a 1100 RPM idle, 100 RPM pocket width, and 25/75 lower/upper shares, the graph begins at 1075 RPM while Point 1 may sit at 1100 RPM.

Profiles without explicit Recurve values receive collinear 25%, 50%, and 75% defaults, preserving the original straight-line behavior.

### Display views

**Default**:

```text
Load increases bottom -> top
RPM increases left -> right
Load unit: kPa absolute
```

**Alpha** transposes the displayed table into RPM rows / load columns and converts the displayed load axis to gauge-style inHg:

```text
vacuum: negative inHg
atmosphere: approximately 0 inHg
boost: positive inHg
```

The internal timing calculation always remains in **kPa absolute**.

---

## Command-line usage

Running IgnGen with no arguments launches the interactive generation workflow:

```bash
igngen
```

Equivalent to:

```bash
igngen new
```

Useful commands:

```bash
igngen engines
igngen presets
igngen show map.csv
igngen bump
igngen clamp
igngen convert
igngen --version
```

Generate non-interactively:

```bash
igngen new \
  --engine D16Z6 \
  --preset base \
  --show
```

Generate and export CSV:

```bash
igngen new \
  --engine D16Z6 \
  --preset base \
  --export default \
  --out d16z6-ignition.csv
```

Alpha-oriented CSV:

```bash
igngen new \
  --engine 4age \
  --preset alpha \
  --export alpha \
  --out 4age-alpha-ignition.csv
```

Boosted example:

```bash
igngen new \
  --engine 4age \
  --boost-psi 12 \
  --boost-retard-gain 0.60 \
  --out 4age-12psi.csv \
  --show
```

Recurve values can also be overridden from the CLI:

```bash
igngen new \
  --engine 4age \
  --recurve1-rpm 1100 \
  --recurve1-timing 18 \
  --recurve2-rpm 2400 \
  --recurve2-timing 25 \
  --recurve3-rpm 3500 \
  --recurve3-timing 32 \
  --show
```

Use `--help` for the complete option list:

```bash
igngen --help
igngen new --help
```

---

## Engine profiles

Engine defaults are stored as human-readable INI files in:

```text
engines/
```

Profiles contain engine landmarks and starting calibration values that can be reviewed and overridden for a specific engine.

### Engine landmarks

- displacement
- peak horsepower and RPM
- peak torque and RPM
- redline RPM
- maximum boost pressure
- target idle RPM

### Mechanical timing

- cranking RPM
- cranking timing
- base / initial timing
- full mechanical timing at peak torque

### Recurve

Optional profile section:

```ini
[recurve]
point1_rpm = 1750
point1_timing = 17
point2_rpm = 2400
point2_timing = 23
point3_rpm = 3500
point3_timing = 31
```

Point 1 may equal target idle RPM. Points 2 and 3 must increase strictly, and Point 3 must remain below peak torque RPM.

The timing values themselves do not have to increase monotonically, so a deliberate intermediate taper can be represented.

### Vacuum timing

- full-vacuum MAP endpoint
- absolute total timing at full vacuum

### Boost timing

- absolute boost timing limit
- boost-retard gain

The tuner specifies the **absolute total timing limit**, not a degrees-per-psi retard amount.

The default boost-retard gain is:

```text
0.60
```

It is stored even in naturally aspirated profiles so that changing only the configured maximum boost pressure immediately produces a usable boosted starting table.

### Idle pocket

- total RPM width
- lower / upper share
- target timing
- timing delta
- idle MAP low / high limits

### Limiter / overspeed

- soft-limit distance before redline
- soft-limit retard
- overspeed distance above redline

---

## Timing model

### 100 kPa atmospheric master curve

**100 kPa absolute is always the pressure crossover and master timing curve.**

At 100 kPa:

```text
pressure correction = 0
commanded timing = mechanical Recurve
```

The mechanical curve is defined by the Recurve control points and the full-mechanical endpoint near peak torque.

IgnGen uses shape-preserving cubic interpolation through the control points so the curve passes through the requested timing values without generic-spline overshoot.

### Vacuum advance

Below 100 kPa, timing advances toward the configured full-vacuum total timing.

Example:

```text
100 kPa -> mechanical timing
 40 kPa -> configured full-vacuum total timing
```

Vacuum correction retains its own RPM progression. Recurving the mechanical master curve does **not** automatically accelerate the vacuum-advance progression.

### Boost retard

Above 100 kPa, the vacuum pressure scale is mirrored into boost and scaled by the configured boost-retard gain.

With a full-vacuum endpoint of 40 kPa:

```text
100 - 40 = 60 kPa vacuum span
```

At gain `1.0`:

```text
100 -> 160 kPa
```

At the default gain `0.60`:

```text
100 + (60 / 0.60) = 200 kPa absolute
```

The boost timing limit remains an **absolute total timing endpoint**. IgnGen calculates the required retard internally.

The model deliberately uses indicated MAP directly. It does not convert MAP into an oxygen-equivalent or compressor-efficiency-adjusted load before generating the base timing surface.

### Idle timing pocket

The idle pocket is a protected local RPM × MAP region around the configured idle point.

Its purpose is to use ignition torque for idle stabilization:

```text
below target idle -> catch timing
at target idle    -> target idle timing
above target idle -> torque-reduction timing
```

The pocket has priority over the generic pressure surface and the Recurve inside its configured region.

This priority is what allows Point 1 to be placed at idle RPM without destroying the protected idle behavior.

### High-RPM soft limit

IgnGen can progressively remove timing before redline so the engine develops a noticeable torque reduction before the hard limit.

The generated RPM axis continues beyond redline into an overspeed region so interpolation remains defined during RPM overshoot.

---

## Axis generation

IgnGen treats axis generation as part of the calibration model rather than simple formatting.

### RPM axis landmarks

Important candidates include:

- cranking RPM
- idle-pocket lower edge
- target idle RPM
- idle-pocket upper edge
- Recurve Points 1–3
- peak torque RPM
- peak horsepower RPM
- soft-limit start
- redline
- overspeed endpoint

Recurve RPM values are protected as table breakpoints whenever the requested table size permits.

### Load axis landmarks

Important candidates include:

- one structural deceleration row below the normal idle MAP region
- idle MAP landmarks
- vacuum/cruise regions
- **100 kPa atmosphere — mandatory**
- boost-pressure landmarks
- maximum configured boost
- overboost/headroom region

Load is calculated internally in kPa absolute.

See [`docs/axis-generation.md`](docs/axis-generation.md) for the detailed allocation rules and Recurve/idle-pocket behavior.

---

## Internal table representation

The canonical representation is:

```text
RPM axis:  ascending
Load axis: ascending kPa absolute
Values:    timing[rpm_index][load_index]
```

Display orientation and export orientation are separate from this representation.

---

## Application integration

IgnGen exposes a Python integration boundary for host applications:

```python
from igngen.gui_app import generate_payload

result = generate_payload({
    "engine": "d16z6",
    "boost_psi": 12,
    "boost_retard_gain": 0.60,
    "load_cells": 16,
    "rpm_cells": 20,
    "view": "default",
    "export": "default",
})
```

The response contains canonical axes and the timing surface:

```python
{
    "schema": "igngen.table.v1",
    "rpm": [...],
    "load_kpa": [...],
    "load_inhg_gauge": [...],
    "timing": [...],
    "recurve": [...],
    "export_table": {...},
    "attribution": {...},
}
```

Canonical timing array:

```text
timing[rpm_index][load_index]
```

HTTP integration:

```text
GET  /api/engines
GET  /api/engine/{profile}
POST /api/generate
```

See [`docs/ALPHALINK_INTEGRATION.md`](docs/ALPHALINK_INTEGRATION.md) for integration notes.

---

## Project layout

```text
src/igngen/
├── calibration.py     # timing model, Recurve, axes, engine profile handling
├── cli.py             # command-line application
├── prompts.py         # interactive calibration workflow
├── gui_app.py         # GUI launcher + integration API
├── gui/               # HTML/CSS/JavaScript GUI and Recurve editor
├── table.py           # timing-table representation
├── io_files.py        # import/export helpers
└── units.py           # kPa / inHg conversion helpers

engines/               # engine profile INI files
presets/               # table-size/layout presets
tests/                 # automated tests
docs/                  # integration and design documentation
```

---

## Development

Linux / WSL / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,gui]"
pytest -q
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,gui]"
pytest -q
```

The stable/public branch is `main`. Active development can be done on `dev`:

```bash
git fetch origin
git switch dev
git pull origin dev
```

Before submitting changes, verify:

```bash
pytest -q
igngen
igngen-gui --browser
```

---

## Release status

IgnGen is under active development. The timing backend, interactive CLI, engine profiles, draggable mechanical Recurve editor, GUI, default/Alpha table views, unit conversion, export orientation, integration payload, and automated tests are present and usable for evaluation.

Before treating a generated table as a final calibration, validate it on the target engine.

---

## License and attribution

IgnGen is released under the **Swicked Racing Attribution License 1.0** contained in [`LICENSE`](LICENSE).

The license permits use, modification, redistribution, commercial use, binary integration, and incorporation into larger applications, subject to its attribution requirements.

Applications incorporating IgnGen or a material portion of its ignition-table generation logic must make the following attribution reasonably accessible in the normal user interface:

```text
Ignition table generation by Swicked Racing IgnGen
https://github.com/Swicked86/Swicked_Racing-IgnGen
```

The attribution does not need to be continuously displayed or more prominent than comparable third-party technology credits. See `LICENSE` and `NOTICE` for the complete terms and required notice.

---

## Attribution

**Swicked Racing IgnGen**  
Ignition table generation by Swicked Racing IgnGen  
https://github.com/Swicked86/Swicked_Racing-IgnGen
