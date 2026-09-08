# Axis generation

IgnGen generates RPM and load breakpoints from engine calibration landmarks rather than using evenly spaced axes. The goal is to preserve the regions that matter most to ignition behavior while still fitting the requested table dimensions.

The canonical implementation is in:

```text
src/igngen/calibration.py
```

All load calculations are performed in **kPa absolute**. Display and export conversions, including Alpha inHg gauge presentation, are applied after the canonical axis has been generated.

## RPM axis

The RPM axis preserves engine landmarks first, then allocates remaining cells into useful operating regions.

### Required landmarks

The generator begins with these anchors:

- cranking RPM
- idle-pocket lower edge
- target idle RPM
- idle-pocket upper edge
- three mechanical **Recurve** RPM control points
- peak torque RPM / full mechanical timing endpoint
- soft-limit start RPM
- redline RPM
- overspeed RPM

If the requested cell count permits it, peak horsepower RPM is also preserved when it lies between peak torque and the overspeed endpoint.

### Mechanical Recurve landmarks

The mechanical advance curve is defined by five points:

```text
idle RPM / base timing
recurve point 1 RPM / timing
recurve point 2 RPM / timing
recurve point 3 RPM / timing
peak torque RPM / full mechanical timing
```

The three Recurve points must have strictly increasing RPM values between idle and peak torque. Their timing values are user-set and may be used to bring timing in earlier, later, flatten early, or create a deliberate intermediate taper.

IgnGen uses shape-preserving cubic interpolation through the points so the generated mechanical curve passes through each user-entered knot without the uncontrolled overshoot associated with a generic spline.

Profiles that do not contain an explicit `[recurve]` section receive collinear defaults at 25%, 50%, and 75% of both the RPM span and timing span. This exactly preserves the original straight-line mechanical advance behavior.

Because Recurve RPM values are actual calibration knots, the RPM-axis generator protects them as table breakpoints whenever the requested table size permits it.

### Idle-pocket edges

The idle pocket uses a configurable total width and lower/upper shares.

For example, with:

```text
idle RPM = 900
pocket width = 100 RPM
lower share = 0.25
upper share = 0.75
```

the RPM landmarks are:

```text
875 / 900 / 975 RPM
```

These points remain available to define the local idle-stabilization region in the generated timing surface.

### Remaining RPM cells

After protected landmarks are inserted, remaining cells are weighted approximately **2:1**:

```text
~2/3  idle-pocket upper edge -> peak torque
~1/3  peak torque -> overspeed
```

The first region now contains the explicit Recurve knots, so filler cells add resolution around the user-defined mechanical-advance shape rather than defining the shape themselves.

Candidate values are snapped to readable RPM steps from:

```text
50, 100, 250, 500, 1000 RPM
```

If cells remain after the first allocation pass, the generator fills the largest remaining RPM gaps until the requested count is reached.

## Load axis

The load axis is generated in **kPa absolute** and always preserves atmospheric pressure as the master crossover.

### Mandatory 100 kPa crossover

The atmospheric breakpoint is mandatory:

```text
100 kPa absolute
```

At this row, pressure correction is zero and timing follows the Recurve-defined mechanical RPM curve directly.

The generator asserts that this breakpoint remains present in the final load axis.

### Idle and deceleration landmarks

The load axis starts with:

- one structural deceleration row below the normal idle MAP region
- idle MAP low
- idle MAP midpoint
- idle MAP high
- 100 kPa atmosphere

The deceleration row is derived from the configured idle MAP low value rather than using one universal floor.

Examples:

```text
idle MAP low = 50 kPa -> decel row = 40 kPa
idle MAP low = 35 kPa -> decel row = 20 kPa
```

For lower idle-MAP values, the generator can use a 5 kPa step and will not place the structural row below 5 kPa absolute.

## Naturally aspirated tables

For naturally aspirated profiles, the generator keeps the normal operating range below atmosphere and adds one small headroom row above atmosphere.

The current headroom convention is:

```text
100 kPa atmosphere
105 kPa headroom
```

Additional cells are concentrated below 100 kPa rather than filling arbitrary rows above atmosphere.

## Boosted tables

For boosted profiles, maximum MAP is derived from the configured boost pressure:

```text
max MAP = atmosphere + boost_psi × 6.895
```

The boost-region step is chosen from readable MAP increments:

```text
5, 10, 20, 25, 50 kPa
```

The calculated maximum MAP is rounded onto that ladder, and one additional step is added as an overboost/headroom row.

For example, a boosted table may contain a progression similar to:

```text
100, 125, 150, 175, 200, 225, 250, 275, 300 kPa
```

The exact values depend on the configured boost pressure and requested number of load cells.

## Resolution allocation

Once the required load landmarks are placed, the remaining cells are distributed between the naturally aspirated region and boost region.

For boosted tables, the allocator intentionally weights the vacuum/NA span somewhat more heavily than a pure span-ratio allocation. This keeps useful resolution in the idle, cruise, and atmospheric-transition areas while still providing meaningful boost breakpoints.

If the first pass does not fill the requested number of cells, the generator performs refinement passes using progressively finer candidate spacing:

```text
5 kPa -> 2 kPa -> 1 kPa
```

It preferentially fills the largest remaining gaps until the requested cell count is reached.

## Canonical orientation

Axis generation is independent of display layout.

The canonical representation is:

```text
RPM:  ascending
Load: ascending kPa absolute
Values: timing[rpm_index][load_index]
```

The default GUI view displays load bottom-to-top with RPM left-to-right.

Alpha view/export transposes the presentation and converts the load labels to gauge-style inHg, where approximately:

```text
vacuum      < 0 inHg
atmosphere  = 0 inHg
boost       > 0 inHg
```

That conversion does **not** alter the underlying load breakpoints or timing calculation.

## Why the axes are nonlinear

Ignition tables do not benefit equally from uniform spacing everywhere. IgnGen therefore prioritizes calibration landmarks and operating transitions instead of treating the table as a purely geometric grid.

The generated axes are designed to preserve:

- cranking and idle behavior
- the idle timing pocket
- user-defined Recurve points
- mechanical advance progression
- peak torque and peak horsepower landmarks
- the 100 kPa pressure crossover
- vacuum/cruise resolution
- configured boost range
- redline and overspeed headroom

Engine profiles change the input landmarks. The axis-generation rules remain common across profiles.
