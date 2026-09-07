# IgnGen requirements (from Swicked Racing + ChatGPT research)

Source of truth for behavior. Code should match this; Alpha is a **preset/export target**, not the design default.

## Build order (layers)

Review each layer before enabling the next:

1. **`mechanical`** — RPM-only curve; load rows are identical
2. **`vacuum`** — mechanical + vacuum (total timing)
3. **`boost`** — vacuum + boost retard (mirror fan from 100 kPa)
4. **`idle` (current review)** — boost + idle pocket (±° across idle MAP band)
5. Soft redline retard

CLI: `igngen new --layers mechanical|vacuum|boost|idle|full` (default **`idle`**).

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
2. **Vacuum** (fans from the 100 kPa master RPM curve):
   - One prompt: **Total timing** (°); full-in MAP is fixed **40 kPa** (not prompted)
   - **100 kPa row = mechanical advance** (master curve)
   - Max vacuum timing (e.g. 50° at ≤40 kPa) only once mechanical is **all-in**
     (at/above peak-torque RPM)
   - Below that RPM: available vacuum add =
     `(total − peak_mech) × mechanical_progress` (same 0→1 schedule as mechanical)
   - Load cells between 40 kPa and atm → **whole-degree** staircase
     from (mech + scaled add) down to mechanical
3. **Boost retard** (mirrors vacuum on the boost side of 100 kPa):
   - One prompt: **Boost timing limit** (total ° min under full boost; default **20°**)
   - **100 kPa row = mechanical** (master)
   - Full retard at ≥ configured max boost MAP → that limit (once mechanical all-in)
   - Below peak-torque RPM: retard × mechanical_progress
   - Load cells between atm and max boost → **whole-degree** staircase
4. **Idle pocket** (localized basin at idle RPM × idle MAP):
   - Prompt: **Idle pocket (±RPM from idle)** — e.g. 750 ± 100 → landmarks 650 / 750 / 850
   - Typical idle vacuum band **30–45 kPa** abs (where the pocket applies)
   - Prompt: **Idle stabilization (±°)** — pocket lower **+N°**, idle **0°**,
     pocket upper **−N°** (default **2**)
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
