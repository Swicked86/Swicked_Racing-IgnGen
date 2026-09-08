# IgnGen — calculation & logic review

Single source of truth for how the table is built on branch `scaffold/python-cli`.
Engines only change **inputs**. Presets only change **size / units / layout**.
Timing math is always in **kPa absolute**.

---

## Pipeline (one path)

1. Load `EngineSpec` (engine profile defaults → interactive prompts override).
2. Apply preset (`base` / `alpha`) → RPM×load counts, load unit, layout/export.
3. Generate **RPM axis** and **load axis** (load always computed in kPa first).
4. If preset load unit is inHg: convert each load breakpoint with `kPa → inHg`.
5. Fill every cell with the same layer stack (CLI default: `--layers idle`).
6. Print / export — layout only (no re-calculation).

**Alpha is post-processing** (view + inHg labels + export shape), not a second calculator.

---

## 1. Engine inputs (`EngineSpec`)

Same fields for every engine. Profiles only pre-fill numbers.

| Group | Fields | Notes |
| --- | --- | --- |
| Atmosphere | `atm_kpa` | Default **100** |
| Power / landmarks | `peak_torque_rpm`, `redline_rpm`, `boost_psi` | Drive axes + boost MAP |
| Mechanical | `cranking_rpm` (500), `cranking_timing` (10°), `idle_rpm`, `base_timing`, `mech_timing_at_peak_torque` | Master curve @ 100 kPa |
| Vacuum | `vacuum_total_timing`, `vacuum_full_map_kpa` (**40**) | Total ° at ≤40 kPa |
| Boost | `boost_timing_limit` | Floor ° at full boost; **off** if `boost_psi == 0` |
| Idle pocket | `idle_pocket_width` (±RPM), `idle_map_lo`/`hi` (30–45), `idle_pocket_bump` | Stabilization overlay |
| Soft limit | `soft_limit_rpm_before_redline`, `soft_limit_retard` | Only `layers=full` |

---

## 2. Units

```
inHg = (kPa − atm_kpa) × 0.2953
kPa  = atm_kpa + inHg / 0.2953
1 psi = 6.895 kPa
max_boost_MAP = atm_kpa + boost_psi × 6.895
```

- **0 inHg ≈ 100 kPa** (atmosphere crossover).
- Vacuum = negative inHg; boost = positive inHg.
- Table fill always converts inHg labels back to kPa before timing math.

---

## 3. RPM axis (shared)

Pinned landmarks (in order):

`cranking` → `idle − width` → `idle` → `idle + width` → `peak_torque` → `redline` → `overspeed` (`redline + 1000`)

Remaining slots split **2:1**:

- **2** — densify `(pocket_hi → peak_torque]` (mechanical climb)
- **1** — densify `(peak_torque → overspeed]`

Fillers snap to multiples of **50 RPM**. Profile landmarks stay exact.

`idle_pocket_width` means **±RPM from idle** (not total span).  
Example: idle 750, width 50 → pocket edges **700 / 750 / 800**.

---

## 4. Load axis (always kPa first)

### 4.1 Landmarks (kPa abs)

```
20, idle_map_lo, mid(lo/hi), idle_map_hi, 55, 60, 80, atm(100)
[+ light boost, max MAP]     if boost_psi > 0
[+ one overboost tip]
```

**Overboost** = one logical round past how max MAP “reads” on a **20 kPa** ladder above atm  
(example: ~183 kPa → tip **200**).

### 4.2 Selection (`select_axis`)

1. Keep highest-priority landmark per rounded value.
2. Pin floor (20) and ceiling (overboost).
3. Split largest gaps until `count` is filled.

**NA** (`boost_psi == 0`): `no_fill_above = atm` — never densify between atm and the single overboost tip; extra rows densify **below** atm.

**Boosted**: densify across vacuum + boost up to the overboost ceiling.

### 4.3 inHg display (alpha)

```
for each kPa breakpoint:
    label = kpa_abs_to_inhg_gauge(kPa, atm)
# then rounded to whole numbers for the table header
```

There is a leftover `load_landmarks_inhg()` in `axes.py` — **not used** by `generate_load_axis`.

### 4.4 Preset sizes

| Preset | Axes | Size | Load unit | Layout |
| --- | --- | --- | --- | --- |
| `base` | generated | 16×12 | kPa | default (bottom-left) |
| `alpha` | generated | 20×16 | inHg | alpha (top-left) |

Fixed High Cam breakpoints in `presets.py` are **fallback only** when `axes = fixed` (alpha.ini uses `axes = generated`).

---

## 5. Timing layers (one stack)

Default CLI layer: **`idle`** = mechanical + vacuum + boost + idle pocket.

All formulas below use **MAP in kPa abs**.

### 5.1 Mechanical — master curve @ 100 kPa

```
if rpm ≤ cranking:   cranking_timing
elif rpm ≤ idle:     base_timing
elif rpm ≥ peak_tq:  mech_timing_at_peak_torque
else:                base + (peak − base) × (rpm − idle) / (peak_tq − idle)
```

Linear idle → peak torque; hold above.

### 5.2 Mechanical progress (scales vac / boost)

```
progress = 0                         if rpm ≤ idle
progress = 1                         if rpm ≥ peak_tq
progress = (rpm − idle) / (peak_tq − idle)   otherwise
```

### 5.3 Vacuum (left of atm)

```
vac_add_full = max(0, vacuum_total_timing − mech_timing_at_peak_torque)
vac_add(rpm) = vac_add_full × progress
high(rpm)    = mechanical(rpm) + vac_add(rpm)    # total at ≤ 40 kPa
```

Across load at a fixed RPM (table fill uses whole-degree steps):

| MAP region | Timing |
| --- | --- |
| ≤ `vacuum_full_map_kpa` (40) | `high` |
| 40 < MAP < 100 | whole° taper `high` → `mech` |
| ≥ 100 (and NA tip) | `mech` |

### 5.4 Boost (right of atm; **skipped if `boost_psi == 0`**)

```
retard_full = max(0, mech_timing_at_peak_torque − boost_timing_limit)
retard(rpm) = retard_full × progress
low(rpm)    = mechanical(rpm) − retard(rpm)     # at ≥ max_boost_MAP
```

| MAP region | Timing |
| --- | --- |
| = atm | `mech` |
| atm < MAP < max_boost_MAP | whole° taper `mech` → `low` |
| ≥ max_boost_MAP | `low` |

### 5.5 Idle pocket (overlay)

Applies only when **both**:

- `|rpm − idle| ≤ idle_pocket_width` (±)
- `idle_map_lo ≤ MAP ≤ idle_map_hi`

```
correction = −bump × (rpm − idle) / width
```

| RPM | Correction |
| --- | --- |
| pocket lower (`idle − width`) | `+bump` |
| idle | `0` |
| pocket upper (`idle + width`) | `−bump` |

Outside the RPM window or MAP band → `0` (no pocket).

### 5.6 Soft redline (`layers=full` only)

Retard from `redline − soft_limit_rpm_before_redline` to redline (smoothstep), then clamp floors/ceilings. **Not** in the default `idle` layer.

### 5.7 Layer names

| `--layers` | What’s included |
| --- | --- |
| `mechanical` | A only |
| `vacuum` | A + C (boost side stays on mech) |
| `boost` | A + C + D |
| `idle` *(default)* | A + C + D + E |
| `full` | idle + soft redline + clamps |

---

## 6. Table fill

For each RPM row × load column:

1. Convert load label → kPa if unit is inHg.
2. Build the vac/boost row with `pressure_row_timings` (whole° fans from the 100 kPa master).
3. If `layers=idle`: add `idle_pocket_correction` per cell.
4. Round to **integer degrees**.

`timing_at()` is the scalar equivalent (used for mechanical / full / point queries). Default table path for vacuum/boost/idle uses the **row taper** so every load cell stays a whole degree.

---

## 7. Display / export only (post-process)

| | `base` / default | `alpha` |
| --- | --- | --- |
| Origin | bottom-left | top-left |
| Terminal | high load at top; RPM → along bottom | RPM ↓ rows; Load → columns |
| Load labels | kPa abs | inHg gauge |
| Values | unchanged | unchanged |

No timing recalculation in layout or export.

---

## 8. What engines change vs what they don’t

**Do change (inputs only):** idle RPM, pocket width/bump, MAP band, base/peak mech, vacuum total, boost psi / limit, redline, etc.

**Do not change:** formulas, layer order, kPa-first axis builder, unit conversion, whole° taper rules.

---

## 9. Known leftovers (not on the default path)

These still exist in source but are **not** what `igngen new --preset alpha|base` uses today:

- `load_landmarks_inhg()` — old inHg-first landmarks
- Fixed High Cam `ALPHA.load` tuple — only if `axes = fixed`
- Legacy `vacuum_advance` / `pressure_delta` / per-psi `boost_retard_per_psi` helpers
- `layers=full` soft-limit path (staged; not default)

If a generated alpha map still shows a load header like `-90 -81 -72 … -20`, that is the **old** inHg landmark path / stale install — current kPa-first conversion looks more like `-24 -21 -18 -16 …` with the idle pocket on the 30/38/45 kPa band columns.

---

## 10. How to regenerate for review

```bash
git pull
pip install -e .

# research view (kPa, bottom-left)
igngen new --preset base --engine D16Z6 --show

# ALPHAlink view (same math, inHg labels, top-left)
igngen new --preset alpha --engine 4AGE --show
```

Compare the same engine under both presets: cell logic should match after unit conversion; only axes density (20×16 vs 16×12), labels, and orientation differ.
