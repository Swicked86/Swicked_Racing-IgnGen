# Axis spacing (from ChatGPT research + user tuning)

## RPM budget (current)

After mandatory anchors, **remaining columns are split 2:1**:

| Share | Zone |
|------:|------|
| **2** | Above idle-pocket upper → peak torque (mechanical climb) |
| **1** | Peak torque → overspeed (flat hold / soft later) |

Anchors always preferred: cranking (300), idle, pocket upper, peak torque,
redline, overspeed (`redline + 1000`).

Mechanical timing itself rises **linearly from idle** — advance starts right
out of idle, not after the pocket. The pocket is a later load-layer feature;
it must not freeze the RPM curve.

## Load axis

Landmark-priority; **atmosphere is mandatory** (`100` kPa / `0` inHg).

Through vehicle **max boost / MAP**, then **one overboost** breakpoint at the
next round number above that max (kPa ×10, inHg ×5) — same idea as RPM
overspeed. Ceiling stops there; no filler walk past overboost.

Implemented in `src/igngen/axes.py`.
