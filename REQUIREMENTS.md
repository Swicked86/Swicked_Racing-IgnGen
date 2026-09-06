# IgnGen requirements (from Swicked Racing + ChatGPT research)

Source of truth for behavior. Code should match this; Alpha is a **preset/export target**, not the design default.

## Inputs

User supplies (prompted):

- Displacement (cc)
- Peak HP @ RPM
- Peak torque (lb-ft) @ RPM — if inconsistent with HP, **estimate** the missing/invalid torque and warn
- Max / redline RPM
- Boost (psi, 0 = NA)
- Base timing (°BTDC, whole degrees)
- Target idle RPM (suggest if unknown)

Optional later: compressor efficiency / NA base HP for turbo VE concepts (shared with future fuel maps).

## Timing model (distributor metaphor)

1. **Mechanical advance** curve vs RPM (hits a limit)
2. **Vacuum advance** under vacuum (separate limit)
3. **Pressure / boost retard** the other direction (separate limit — **not** a mirror of vacuum)
4. **Idle pocket**: localized only around idle RPM ± pocket width (default ±250 RPM) and **light load only**; must not smear into light-throttle cells. Tight RPM spacing; strong enough drop above target idle so the engine falls into the pocket (avoid stall / floating).
5. **Soft power loss**: start retarding ~500 RPM before redline; final axis point ~1000 RPM past redline when generating axes
6. Atmosphere (**~0 inHg on Alpha gauge**, or 100 kPa abs in MAP models) **always** on the load axis as crossover
7. Normal generated map: **whole degrees**, floor **≥ 0** (no negative cells in the base map)

## Axes

- Table size is a constraint (8×8, 12×12, 12×24, Alpha 20×16, …)
- Prefer **nonlinear** RPM/load spacing like an audio scale: dense at cranking / idle pocket / to peak torque; coarser where the curve is flat; soft-limit then overspeed
- Preset `alpha`: fixed 20×16 RPM × Load(**inHg**) from ALPHAlink High Cam — size/labels only; values still come from the model

## Orientation (three layers)

| Layer | Default |
|-------|--------|
| **Internal** | RPM ascending, load ascending, `values[rpm][load]` |
| **Display (Swicked)** | RPM → left to right; Load ↑ bottom to top (high load at top of screen) |
| **Export** | Configurable. Default = Swicked. `--export alpha` = Alpha paste (RPM rows top→bottom, load columns left→right) |

Alpha on-screen layout is **not** the Swicked default.
