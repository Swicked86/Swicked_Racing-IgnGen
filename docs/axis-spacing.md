# Axis spacing (from ChatGPT research)

Philosophy: **not** even spacing, **not** a literal log scale — more like an
audio EQ graph: dense where control matters, sparse where the model is flat.

## Landmark priorities (RPM)

| Priority | Breakpoints |
|---:|---|
| 100 | cranking, idle target, peak torque, redline, overspeed (+1000) |
| 90 | idle pocket edges (± width, default 250) |
| 85 | peak HP, soft-limit start |
| ≤70 | transition / filler midpoints |

## Fit into table size

Same landmarks, different resolution:

**8 RPM columns** (keep mandatory + pocket edges; soft-limit may interpolate):

```text
300, 850, 1100, 1350, 4800, 7800, 9300, 10300
```

**12 RPM columns** (denser idle + soft-limit explicit):

```text
300, 700, 850, 1000, 1100, 1200, 1350, 2500, 4800, 7800, 8800, 10300
```

**24** can keep almost every landmark plus transitions.

Load axis uses the same priority idea; **atmosphere is always mandatory**
(`0` inHg on alpha, `100` kPa on base).

Implemented in `src/igngen/axes.py` (`generate_rpm_axis`, `generate_load_axis`).
