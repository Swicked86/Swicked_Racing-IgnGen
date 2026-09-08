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

Through vehicle **max boost / MAP** (from whatever the loaded profile has —
including values edited after defaults), then **one overboost** row:

1. Snap max MAP to the nearest **logical round** on the boost-region ladder
   (midpoint; ties read up) — e.g. ~172 → reads as **180**.
2. Overboost = **one logical step past** that read — e.g. **200**.

This is not “max + N kPa”; it is one step over on the round ladder.
Ceiling stops at overboost; no filler walk past it.

Implemented in `src/igngen/axes.py`.
