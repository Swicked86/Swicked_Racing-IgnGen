# Axis spacing (from ChatGPT research)

Philosophy: **not** even spacing, **not** a literal log scale — more like an
audio EQ graph: dense where control matters, sparse where the model is flat.

Spacing follows **rate of change of the timing model**, especially mechanical
advance (changing from idle → peak torque, flat after).

## Landmark priorities (RPM)

| Priority | Breakpoints |
|---:|---|
| 100 | cranking, idle target, peak torque |
| 95–90 | redline, overspeed (+1000) |
| 92 | mechanical ramp quarters (idle→peak torque) |
| 75 | off-idle |
| 55 | idle pocket edges (until pocket layer needs them) |
| ≤45 | peak HP, soft-limit, post-peak fillers |

Gap filling after landmark selection is **weighted**: idle→peak-torque gaps
score ~3× raw span; post-peak hold scores ~0.35× so we don't burn half the
table on a flat 32° plateau.

## Fit into table size

Same landmarks, different resolution. Exact integers depend on engine inputs;
shape should look like:

**8 RPM columns** — anchors + a couple ramp points:

```text
300, 1100, ~2200, ~3500, 4800, 9300, …, overspeed
```

**12–16 RPM columns** — denser on the mechanical ramp; sparse after peak torque:

```text
cranking, idle, several ramp steps, peak torque, few post-peak, redline, overspeed
```

**24** can keep pocket edges, soft-limit, and more transitions.

Load axis uses the same priority idea; **atmosphere is always mandatory**
(`0` inHg on alpha, `100` kPa on base).

Implemented in `src/igngen/axes.py` (`generate_rpm_axis`, `generate_load_axis`).
