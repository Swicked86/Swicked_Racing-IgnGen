# Axis spacing (from ChatGPT research + user tuning)

## RPM budget (current)

After mandatory anchors, **remaining columns are split 2:1**:

| Share | Zone |
|------:|------|
| **2** | Above idle-pocket upper → peak torque (mechanical climb) |
| **1** | Peak torque → overspeed (flat hold / soft later) |

Anchors always preferred: cranking (300), idle, pocket upper, peak torque,
redline, overspeed.

Mechanical timing itself rises **linearly from idle** — advance starts right
out of idle, not after the pocket. The pocket is a later load-layer feature;
it must not freeze the RPM curve.

## Load axis

Still landmark-priority; **atmosphere is mandatory** (`100` kPa / `0` inHg).

Implemented in `src/igngen/axes.py`.
