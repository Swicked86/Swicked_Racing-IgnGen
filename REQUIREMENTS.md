# IgnGen requirements (from Swicked Racing + ChatGPT research)

Source of truth for behavior. Code should match this; Alpha is a **preset/export target**, not the design default.

## Build order (layers)

Review each layer before enabling the next:

1. **`mechanical`** — RPM-only curve; load rows are identical
2. **`vacuum` (current review)** — mechanical + vacuum (total timing)
3. Boost retard
4. Idle pocket
5. Soft redline retard

CLI: `igngen new --layers mechanical|vacuum|full` (default **`vacuum`** while reviewing this layer).

## Inputs

User supplies (prompted):

- Displacement (cc)
- Peak HP @ RPM
- Peak torque (lb-ft) @ RPM — if inconsistent with HP, **estimate** the missing/invalid torque and warn
- Max / redline RPM
- Boost (psi, 0 = NA)
- Target idle RPM
- **Base / initial timing** (°BTDC, whole degrees) — default **10°** (small-cam / low-perf may want less)
- **Total timing at peak torque** — default **32°** (safe mechanical all-in)
- **Vacuum advance** (additive °) — default **10°**; full-in MAP is static **50 kPa**
- Optional: vacuum total ° ceiling (default **42°**)

Optional later: compressor efficiency / NA base HP for turbo VE concepts (shared with future fuel maps).

## Timing model (distributor metaphor)

1. **Mechanical advance** curve vs RPM:
   - ≤ idle → base timing
   - idle → peak-torque RPM → ramp to total-at-peak-torque
   - above peak torque → **hold** (no further climb)
2. **Vacuum** (total timing under vacuum):
   - One prompt: **Total timing** (°); full-in MAP is fixed **40 kPa** (not prompted)
   - MAP ≤ **40 kPa** → that total timing (absolute °)
   - MAP ≥ atmosphere → mechanical only
   - Load cells between 40 kPa and atm → **whole-degree** staircase
     (difference ÷ number of gaps, integer steps)
   - **RPM gate:** **0°** vacuum through the idle pocket; linear ramp to full
     by ~pocket_hi+800 RPM
3. **Boost retard** (separate **total °** min — **not** a mirror of vacuum) — later layer
4. **Idle pocket**: localized only around idle RPM ± pocket width and **light load only** — later layer
5. **Soft power loss**: start retarding ~500 RPM before redline — later layer
6. Atmosphere (**100 kPa** abs / ~0 inHg Alpha gauge) **always** on the load axis as crossover
7. Normal generated map: **whole degrees**, floor **≥ 0**

## Axes

- Table size is a constraint (8×8, 12×12, 12×24, Alpha 20×16, …)
- Prefer **nonlinear** RPM/load spacing like an audio scale
- Preset `alpha`: fixed 20×16 RPM × Load(**inHg**) from ALPHAlink High Cam — size/labels only; values still come from the model
- Default preset: **`base`**

## Orientation

| Layer | Default |
|-------|--------|
| **Internal** | RPM ascending, load ascending, `values[rpm][load]` |
| **Display (Swicked)** | RPM → ; Load ↑ (high load at top; RPM labels on bottom row) |
| **Export** | Configurable. Default = Swicked. `--export alpha` = Alpha paste |
