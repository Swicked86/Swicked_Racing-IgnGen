# Swicked Racing IgnGen

IgnGen is a Python ignition-table generator intended to create explainable **starting calibration maps** from a small set of engine parameters. The model deliberately follows the behavior of a well-developed distributor: an RPM-driven mechanical advance curve, a vacuum-driven advance mechanism, a pressure/boost retard mechanism, a protected idle timing pocket, and a high-RPM soft-limit region.

The project is currently under active development on `scaffold/python-cli`.

> **Calibration warning:** generated tables are starting points for calibration and validation, not engine-safe prescriptions. Final timing must be verified on the actual engine with appropriate instrumentation, knock monitoring, fuel-quality controls, and dyno/road testing.

## Design goals

IgnGen is built around several invariants:

- **100 kPa absolute is always an explicit load breakpoint.** It is the crossover between vacuum advance and boost retard.
- **RPM and load axes are nonlinear.** Resolution belongs where the engine or control strategy changes quickly, not at arbitrary equal intervals.
- **Table dimensions are constraints.** 8x8, 12x12, 12x24, 20x16, and other ECU shapes should use the same engine model with different breakpoint budgets.
- **The idle pocket is protected.** It is a localized RPM x MAP region intended to catch falling RPM and remove torque above target idle.
- **Peak torque is a structural RPM landmark.** The mechanical advance curve is considered fully in by this region and normally holds afterward.
- **Peak horsepower, soft-limit start, redline, and overspeed are separate landmarks.** They must not appear only by coincidence from gap filling.
- **Redline is not the end of the table.** The RPM axis should normally extend about 1000 RPM beyond redline so interpolation remains defined during overshoot.
- **Internal calculation, visual orientation, and export orientation are separate concerns.** The same map may be displayed with load increasing bottom-to-top while being exported in whatever row/column arrangement a target ECU requires.
- **Generated breakpoints should be clean, readable numbers.** Changing engine profile, redline, idle target, or boost pressure should not produce arbitrary-looking scale values without a clear reason.

## Engine inputs

The current `EngineSpec` includes:

- displacement
- peak horsepower and RPM
- peak torque and RPM
- redline RPM
- boost pressure
- target idle RPM
- base / initial ignition timing
- cranking timing
- total atmospheric timing at peak torque
- total timing target at full vacuum
- full-vacuum MAP breakpoint
- full-boost timing target/limit
- idle-pocket RPM width and MAP band
- soft-limit start distance and retard amount

Power inputs are sanity checked using:

```text
HP = Torque(lb-ft) x RPM / 5252
```

An inconsistent horsepower/torque pair should be reported to the user rather than silently treated as authoritative.

## Timing model

### 1. Atmospheric master curve

The 100 kPa column is the master RPM curve.

Conceptually:

```text
cranking -> base/initial timing -> mechanical advance -> full mechanical timing
```

Mechanical advance rises from the low-RPM/base region toward the specified total timing near peak torque, then reaches a stop and remains static through the normal high-RPM region.

### 2. Vacuum advance

Vacuum timing fans away from the 100 kPa master curve toward the configured full-vacuum total timing.

Example:

```text
100 kPa = atmospheric master timing
 40 kPa = full-vacuum timing target
```

The maximum vacuum addition is derived from the difference between full-vacuum total timing and full mechanical timing. Below peak-torque RPM, available vacuum advance is scaled back with the progression of the master RPM curve so the low-RPM area does not receive the entire high-RPM vacuum addition.

The load-side taper must remain deterministic when table size changes. Axis spacing and timing interpolation therefore need to be designed together rather than allowing arbitrary midpoint-generated load values to change the effective pressure slope.

### 3. Boost / pressure retard

Boost retard begins on the pressure side of the explicit 100 kPa crossover and moves toward a configured full-boost timing target.

This side of the map is **not assumed to be physically identical to vacuum advance**. The implementation must preserve the atmospheric master curve while producing a predictable low-RPM/high-load region and a defined timing target at maximum boost.

### 4. Idle timing pocket

The idle pocket is a localized basin around:

```text
target idle RPM +/- pocket RPM width
idle MAP low ... idle MAP high
```

It should not be a broad low-RPM retard band. Light throttle causes MAP to rise rapidly and moves the operating point out of the pocket into normal timing cells.

The intended behavior is:

- below target idle: additional timing/torque to catch RPM
- at target idle: base idle timing
- above target idle: sharply reduced timing/torque so RPM falls into the pocket

The idle pocket has higher semantic priority than generic vacuum/mechanical interpolation inside its defined region.

### 5. High-RPM soft power loss

A configurable soft-limit region begins before redline and progressively removes timing so the engine visibly loses power before the hard RPM limit. The table continues beyond redline to an overspeed endpoint.

## Axis generation

Axis generation is part of the calibration model, not merely formatting.

### RPM landmarks

Candidate landmarks include:

1. cranking RPM
2. idle-pocket lower edge
3. target idle RPM
4. idle-pocket upper edge
5. mechanical-advance transition points
6. peak torque RPM
7. peak horsepower RPM
8. soft-limit start RPM
9. redline RPM
10. overspeed endpoint (`redline + ~1000 RPM`)

When the table has fewer columns than candidate landmarks, the generator should use a **single priority-based allocator**. Remaining columns should then be distributed by region importance and interpolation error.

Resolution should generally be:

- coarse at cranking
- very dense around the idle pocket
- dense through the mechanical/VE rise toward peak torque
- progressively coarser after peak torque where timing becomes comparatively static
- dense again through the soft-limit/redline region
- coarse at the final overspeed endpoint

Generated filler RPM values should use a human-readable snapping ladder appropriate to the region rather than always using one fixed increment.

### Load landmarks

Candidate load landmarks include:

- minimum/deep-vacuum endpoint
- idle MAP boundaries and center
- full-vacuum timing breakpoint
- intermediate vacuum/cruise breakpoints
- **100 kPa atmosphere -- mandatory**
- boost onset/intermediate points
- configured maximum boost MAP
- overboost endpoint

The atmospheric crossover must never be removed to make room for another breakpoint.

Load values should be generated in kPa absolute internally. Unit conversion to inHg or another display/export unit must not change the internal MAP coordinate used to calculate timing.

## Table orientation

Canonical internal representation:

```text
RPM axis:  ascending
Load axis: ascending MAP
Values:    timing[rpm_index][load_index]
```

Preferred Swicked visual layout:

```text
Load increases bottom -> top
RPM increases left -> right
```

Export is independent and may transpose axes, reverse either axis, place RPM/load headers in different locations, and use ECU-specific units.

## Current implementation status

The codebase already contains the major prototype pieces:

- `src/igngen/model.py` -- ignition calculation layers
- `src/igngen/axes.py` -- nonlinear RPM/load breakpoint generation
- `src/igngen/table.py` -- table representation/display
- `src/igngen/io_files.py` -- import/export
- `src/igngen/engines.py` -- engine profile loading
- `src/igngen/prompt.py` -- interactive engine inputs
- `src/igngen/cli.py` -- command-line interface
- `engines/` -- engine profiles
- `presets/` -- table-size/layout presets
- `tests/` -- unit tests for mechanical, vacuum, boost, idle, axes, and IO behavior

### Known design work still required

The current prototype should be treated as a research implementation rather than a finalized calibration engine. The main items to resolve are:

1. Replace separate/ad-hoc RPM and load allocation rules with one explicit **landmark priority + regional resolution** system.
2. Make generated axis values use stable, clean snapping rules across different engine profiles and table dimensions.
3. Add peak-HP and soft-limit landmarks explicitly instead of allowing them to appear only as filler values.
4. Rework the boosted load-axis filler strategy; recursive largest-gap midpoint splitting currently creates arbitrary-looking values at higher boost.
5. Define boost retard independently from the vacuum model instead of assuming a mirrored fan is always correct.
6. Make the idle pocket a protected target/override region rather than a small generic additive correction.
7. Consolidate scalar and row-based timing calculations so a cell has one canonical result regardless of which API generated it.
8. Remove or quarantine legacy calculation paths and aliases once compatibility is no longer needed.
9. Keep kPa coordinates intact through calculation; display/export rounding must not feed back into timing math.
10. Expand tests from individual helper behavior to **invariants across table sizes and engine-profile changes**.

## Development

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Basic generation:

```bash
igngen new --preset base --engine D16Z6 --show
```

Custom engine values can be supplied interactively or through CLI overrides.

## Testing requirements

The test suite should eventually assert behavior such as:

- 100 kPa exists for every supported load-axis size
- cranking, idle target, peak torque, redline, and overspeed survive axis compression according to documented priorities
- output axes contain the requested number of unique, strictly increasing breakpoints
- changing table dimensions changes resolution, not the underlying timing model
- changing display/export units does not change calculated timing
- changing boost pressure moves boost landmarks predictably
- the idle pocket survives every later timing layer
- the soft-limit correction cannot be erased by a later floor/boost clamp
- scalar point evaluation and full-table generation produce identical results at the same RPM/MAP coordinate

## License

The repository currently contains provisional MIT metadata in `pyproject.toml`, but MIT does **not** require attribution to remain visibly present inside a running application. The final license should therefore be selected before release if user-visible attribution is a hard requirement.

See the project discussion/documentation before publishing a release under a final license.
