# IgnGen V2

V2 is a clean refactor of the ignition-table generator while reusing proven project pieces where they make sense, especially the existing table representation, terminal coloring, layouts, and export behavior.

The goals are:

- use `engines/*.ini` as the normal source of engine/calibration defaults;
- let the application temporarily override any selected profile without modifying its INI;
- let an `other`/custom engine be entered and optionally saved as a new INI;
- use one canonical timing function for point queries and full tables;
- separate axis placement from ignition-timing math;
- preserve mandatory landmarks before applying spacing ratios;
- apply the 2:1 RPM distribution only to discretionary cells;
- always include atmosphere (`100 kPa` absolute by default) on the load axis;
- generate clean, readable RPM and load breakpoints;
- calculate pressure effects from actual MAP, never from the number of table cells;
- keep display/export orientation independent from calculation orientation.

## Profiles are defaults, not locked values

A tuner normally edits the engine INI. Selecting an engine loads those values as defaults.

The application may then modify them temporarily to generate a table. Temporary edits do **not** change the selected profile. If the tuner wants to keep the edited engine, it can be explicitly saved as another INI.

Examples:

```bash
# Read D16Z6 defaults and temporarily move the idle MAP band for a cammed engine.
python -m V2.cli --engine d16z6 --idle-map-lo 48 --idle-map-hi 62 --show

# Start with generic "Other" values, override them, and save a reusable profile.
python -m V2.cli --engine other \
  --name "Cammed B18" \
  --displacement-cc 1834 \
  --idle-rpm 900 \
  --idle-map-lo 50 --idle-map-hi 65 \
  --save-engine cammed_b18 \
  --show
```

`--save-engine cammed_b18` writes `engines/cammed_b18.ini` locally. Existing profiles are protected unless overwrite is explicitly requested.

Manual axes can also be supplied for one generation:

```bash
python -m V2.cli --engine d16z6 \
  --rpm-values 500,645,670,745,1500,3000,5200,6700,7200,8200 \
  --load-values 20,30,40,50,60,70,80,90,100,120 \
  --show
```

A manual load axis must still contain the atmosphere crossover.

## V2 defaults

- Cranking/running handoff anchor: **500 RPM**.
- Full vacuum-advance MAP: **40 kPa absolute**.
- Atmosphere crossover: **100 kPa absolute**.
- Overspeed endpoint: **redline + 1000 RPM**.
- Soft-limit start: **redline - 500 RPM** unless the profile changes it.
- Idle pocket: **100 RPM total width**, **25% below / 75% above** target idle.
- Idle pocket timing: **10° target, ±6° authority** by default.
- Warm-idle MAP band: profile-driven and tuner-adjustable.
- Vacuum timing is a total-timing target at 40 kPa, not a fixed amount blindly added at every RPM.
- Boost uses an explicit full-boost timing target. Roughly **2° of retard per psi of boost** is available only as a starting heuristic; an explicit profile target wins.

## Idle pocket

The idle pocket is a localized RPM × MAP ignition-control region.

For a 750 RPM target using the default 100 RPM total span:

```text
725 RPM   catch edge
750 RPM   target
825 RPM   upper retard edge
```

The default timing targets are:

```text
catch edge   16°  (10 + 6)
target       10°
upper edge    4°  (10 - 6)
```

These are defined as `idle_timing_target +/- idle_timing_delta`, not as three unrelated static values and not as a function of the engine's distributor/base timing.

The engine INI contains the tuner-facing controls:

```ini
[idle]
; TOTAL pocket span, not +/-RPM
idle_pocket_width = 100
idle_pocket_lower_share = 0.25
idle_pocket_upper_share = 0.75

idle_timing_target = 10
idle_timing_delta = 6

; Warm-idle MAP band, kPa absolute.
; Camshaft/intake/exhaust changes can move idle vacuum significantly.
idle_map_lo = 30
idle_map_hi = 45
```

The pocket is applied as a protected local timing target after the generic pressure surface, so vacuum/boost interpolation cannot erase it.

## Adjustable load behavior

Idle vacuum is not treated as a fixed engine-family constant. A larger camshaft in particular can raise warm-idle MAP substantially.

`idle_map_lo` and `idle_map_hi` therefore affect both:

1. where the idle pocket is allowed to operate; and
2. which load-axis landmarks are preferred during generated axis placement.

A tuner can edit these in the INI permanently or override them temporarily from the application.

The entire load axis can also be supplied manually for an ECU/table that requires specific breakpoints.

## RPM-axis algorithm

First place structural anchors:

1. cranking RPM;
2. idle-pocket lower edge;
3. target idle RPM;
4. idle-pocket upper edge;
5. peak torque RPM;
6. soft-limit start RPM;
7. redline RPM;
8. overspeed endpoint.

If peak-HP RPM fits within the requested table size, it is a preferred post-torque landmark.

After protected landmarks are placed, split the remaining RPM-cell budget approximately **2:1**:

- about 2/3 between the upper idle-pocket edge and peak torque;
- about 1/3 between peak torque and overspeed.

Only generated filler points are snapped to clean RPM increments. Profile/user landmarks remain exact.

## Load-axis algorithm

V2 calculates load internally in **kPa absolute**. Protected/preferred candidates include:

- deep-vacuum endpoint;
- full-vacuum point (40 kPa by default);
- idle MAP lower/middle/upper landmarks;
- atmosphere (100 kPa, mandatory by default);
- configured maximum boost MAP;
- overboost endpoint.

Remaining cells come from clean-number ladders rather than recursive raw integer midpoints. Profile changes should therefore move meaningful landmarks without creating arbitrary-looking scales such as 196 or 272 kPa unless such a number is itself an exact protected value.

## Timing model

The 100-kPa column is the atmospheric master RPM curve.

### Mechanical

- at/below cranking RPM: cranking timing;
- cranking through idle: base timing;
- idle through peak torque: ramp toward configured full mechanical timing;
- at/above peak torque: hold that total.

### Vacuum

At atmosphere the vacuum correction is zero. At or below `vacuum_full_map_kpa` the pressure fraction is 1.0.

The maximum vacuum addition is:

```text
vacuum_total_timing - full_mechanical_timing
```

Available vacuum advance below peak torque is scaled by mechanical progress. Load interpolation uses the **actual MAP coordinate**, so changing table size changes resolution, not the underlying timing function.

### Boost

At atmosphere the boost correction is zero. At configured maximum boost MAP the pressure fraction is 1.0.

The full-boost side moves toward an explicit timing target. V2 does not divide a fixed retard amount among however many boost cells happen to exist.

A helper can estimate a starting full-boost target from:

```text
full_mechanical_timing - (boost_psi * retard_deg_per_psi)
```

with `retard_deg_per_psi = 2.0` as the current heuristic.

### Soft limit

Soft-limit retard is applied after the normal surface and begins at the configured soft-limit start RPM. Redline and overspeed remain explicit axis landmarks.

## Reuse of V1 code

`V2/render.py` intentionally imports `igngen.table.TimingTable` so V2 keeps the existing terminal heatmap coloring and layouts rather than rewriting presentation code.

V2 does not import the V1 timing or axis calculators.

## Quick test

From the project root after `pip install -e .`:

```bash
python -m V2.cli --engine d16z6 --rpm-cells 16 --load-cells 12 --show
```

Use `--layout default` for the preferred view (RPM left-to-right, load increasing bottom-to-top) or `--layout alpha` for the alternate orientation already supported by the existing renderer.
