# IgnGen V2

V2 is a clean-room refactor of the ignition-table generator while reusing proven project pieces where they make sense, especially the existing table representation, terminal coloring, layouts, and export behavior.

The goals are:

- keep the existing `engines/*.ini` files as the source of engine-profile parameters;
- use one canonical timing function for both point queries and full tables;
- separate axis placement from ignition-timing math;
- preserve mandatory landmarks before applying any spacing ratio;
- apply the 2:1 RPM distribution only to discretionary cells;
- always include atmosphere (`100 kPa` absolute) on the load axis;
- generate clean, readable RPM and load breakpoints;
- calculate pressure effects from actual MAP, never from the number of cells between two points;
- keep display/export orientation independent from calculation orientation.

## V2 defaults

- Cranking/running handoff anchor: **500 RPM**.
- Full vacuum-advance MAP: **40 kPa absolute**.
- Atmosphere crossover: **100 kPa absolute**.
- Overspeed endpoint: **redline + 1000 RPM**.
- Soft-limit start: **redline - 500 RPM** unless the profile/config changes it.
- Vacuum timing is a total-timing target at 40 kPa, not a fixed number of degrees blindly added at every RPM.
- Boost uses an explicit full-boost timing target. A common heuristic of roughly **2 degrees of retard per psi of boost** is exposed as a helper, but the engine profile's explicit target wins when supplied.

## RPM-axis algorithm

First place structural anchors:

1. cranking RPM
2. idle-pocket lower edge
3. target idle RPM
4. idle-pocket upper edge
5. peak torque RPM
6. soft-limit start RPM
7. redline RPM
8. overspeed endpoint

If peak-HP RPM fits within the requested table size, it is treated as a preferred landmark in the post-torque region.

After protected landmarks are placed, split the remaining RPM-cell budget approximately **2:1**:

- 2/3 between the upper idle-pocket edge and peak torque;
- 1/3 between peak torque and overspeed.

Generated filler values are snapped to clean RPM increments. Protected engine/profile landmarks are not moved simply to make them prettier.

For the example discussed during design:

```text
idle             750 RPM
idle pocket      +/-250 RPM
peak torque      3500 RPM
redline          6000 RPM
soft limit start 5500 RPM
overspeed        7000 RPM
```

The protected 8-cell axis is:

```text
500, 750, 1000, 3500, 5500, 6000, 7000
```

If the lower idle-pocket edge collides with the 500-RPM cranking anchor, the collision is intentional: one table breakpoint can represent both landmarks. The freed cell becomes discretionary resolution instead of inventing a second nearly identical RPM point.

## Load-axis algorithm

V2 generates load internally in **kPa absolute**. Protected candidates include:

- deep-vacuum endpoint;
- full-vacuum point (40 kPa by default);
- idle MAP lower/middle/upper landmarks;
- atmosphere (100 kPa, mandatory);
- configured maximum boost MAP;
- overboost endpoint.

Remaining cells are selected from a clean-number ladder rather than raw recursive integer midpoints. This prevents profile changes from producing arbitrary-looking values such as 196 or 272 kPa unless such a value is itself an exact protected profile landmark.

## Timing model

The 100-kPa column is the master mechanical curve.

### Mechanical

- at/below cranking RPM: cranking timing;
- cranking through idle: base timing;
- idle through peak torque: ramp to configured total mechanical timing;
- at/above peak torque: hold that total.

### Vacuum

At 100 kPa the correction is zero. At or below 40 kPa the pressure fraction is 1.0.

The maximum vacuum addition is:

```text
vacuum_total_timing - full_mechanical_timing
```

Available vacuum advance below peak torque is scaled by mechanical progress. The load interpolation uses the **actual MAP coordinate**, not the ordinal position of a load cell.

### Boost

At 100 kPa the correction is zero. At configured maximum boost MAP the pressure fraction is 1.0.

The full-boost side is generated toward an explicit timing target. The V2 model does not divide a fixed retard amount among however many boost cells happen to exist.

A helper can estimate a starting full-boost target from:

```text
full_mechanical_timing - (boost_psi * retard_deg_per_psi)
```

with `retard_deg_per_psi = 2.0` as the default heuristic. If `boost_timing_limit` exists in the engine profile, that explicit value is used instead.

### Idle pocket

The idle pocket is applied as the final local timing target inside the configured RPM x MAP pocket so normal vacuum/boost calculations cannot erase it.

Existing profiles that only provide `idle_pocket_bump` remain compatible. Future profiles may provide explicit lower/target/upper idle timing values.

### Soft limit

Soft-limit retard is applied after the normal timing surface and begins at the configured soft-limit start RPM. Redline and overspeed remain explicit axis landmarks.

## Reuse of V1 code

`V2/render.py` intentionally imports `igngen.table.TimingTable` so V2 keeps the existing terminal heatmap coloring and layouts rather than rewriting proven presentation code.

V2 does not import the V1 timing or axis calculators.

## Quick test

From the project root after `pip install -e .`:

```bash
python -m V2.cli --engine d16z6 --rpm-cells 16 --load-cells 12 --show
```

Use `--layout default` for the preferred view (RPM left-to-right, load increasing bottom-to-top) or `--layout alpha` for the alternate orientation already supported by the existing table renderer.
