# IgnGen GUI and ALPHAlink integration

IgnGen's GUI is intentionally a single configuration panel with the generated ignition table directly below it. The GUI is HTML/CSS/JavaScript and the generation engine remains Python.

This split is deliberate: the same front end can run standalone on Linux, in a pywebview desktop window on Windows, or be incorporated into an existing HTML/JavaScript tuning application without rewriting the timing model.

## Standalone development on Linux

Browser mode has no GUI dependency beyond Python:

```bash
pip install -e .
igngen-gui --browser
```

For a native pywebview window, install the optional GUI dependency and the platform WebKit/GTK requirements required by pywebview:

```bash
pip install -e ".[gui]"
igngen-gui
```

If pywebview is not installed, `igngen-gui` automatically falls back to the system browser.

## Windows standalone

On Windows:

```powershell
py -m pip install -e ".[gui]"
igngen-gui
```

The HTML/CSS/JS assets live under:

```text
src/igngen/gui/
  index.html
  styles.css
  app.js
```

The desktop/browser host is:

```text
src/igngen/gui_app.py
```

## Integration boundary

The public Python integration function is:

```python
from igngen.gui_app import generate_payload

result = generate_payload({
    "engine": "d16z6",
    "boost_psi": 12,
    "boost_retard_gain": 0.60,
    "load_cells": 16,
    "rpm_cells": 20,
})
```

The result is intentionally host-neutral:

```json
{
  "schema": "igngen.table.v1",
  "engine": "D16Z6",
  "units": {
    "rpm": "rpm",
    "load": "kPa_abs",
    "timing": "deg_BTDC"
  },
  "rpm": [500, 645, 670, 745],
  "load_kpa": [20, 30, 37, 45, 70, 100],
  "timing": [[10, 10, 10, 10, 10, 10]],
  "attribution": {
    "name": "Swicked Racing",
    "product": "IgnGen",
    "phrase": "Ignition table generation by Swicked Racing IgnGen",
    "url": "https://github.com/Swicked86/Swicked_Racing-IgnGen"
  }
}
```

The exact array lengths depend on the requested table shape. Canonical internal orientation is `timing[rpm_index][load_index]`.

## Local HTTP integration

The standalone GUI exposes the same engine through localhost:

```text
GET  /api/engines
GET  /api/engine/{profile}
POST /api/generate
```

`POST /api/generate` accepts the same object as `generate_payload()` and returns the same `igngen.table.v1` response.

This endpoint exists to keep the web UI independent of the Python host. It is bound to `127.0.0.1` only.

## Preferred ALPHAlink integration

The observed ALPHAlink installation contains a bundled Python 3.11 runtime, a `webview` package, and a `gui/` tree containing `index.html`, CSS, and JavaScript assets. That strongly suggests a Python-hosted web UI, but the exact application architecture should be confirmed by its developer before integration.

There are three practical integration levels.

### 1. Direct Python call — preferred

If ALPHAlink can import IgnGen's Python package, call `generate_payload()` directly when the user presses **Generate Table**. This avoids localhost networking and gives the host application the generated arrays immediately.

Conceptually:

```python
result = generate_payload(settings)
alpha_table.set_rpm_axis(result["rpm"])
alpha_table.set_load_axis(result["load_kpa"])
alpha_table.set_ignition_values(result["timing"])
```

The final three lines are placeholders for ALPHAlink's own table API.

### 2. Embed the panel assets

The host can reuse or restyle the contents of `src/igngen/gui/` inside its existing calibration workspace. The standalone GUI should be treated as a reference implementation of the controls, not as a requirement to create a second desktop window.

The host application should own:

- calibration/workspace state
- undo/redo
- table editing
- ECU-specific semantics
- file save/load
- datalogging
- final table import

IgnGen should own:

- engine/calibration inputs
- RPM breakpoint generation
- MAP breakpoint generation
- absolute crank-timing generation

### 3. Local API

If the Windows application cannot directly import the Python module, it can launch the IgnGen server and POST to `/api/generate`. This is the least preferred integration because the direct call is simpler inside a Python-based host.

## Host-side table import

The generated timing surface uses absolute crank timing. Target-specific ECU offsets or alternate timing semantics should be applied by the host/export adapter after IgnGen generation.

The host should not reinterpret the returned load axis as gauge pressure. `load_kpa` is absolute manifold pressure and explicitly includes the 100 kPa atmospheric crossover.

## Attribution requirement

The repository is licensed under the Swicked Racing Attribution License 1.0. A graphical larger work incorporating IgnGen or a material portion of its generation logic must make this attribution accessible in the normal UI:

```text
Ignition table generation by Swicked Racing IgnGen
https://github.com/Swicked86/Swicked_Racing-IgnGen
```

A small footer in the generator panel, an About/credits dialog, or an equivalent plugin-information location satisfies the intended integration model. See `LICENSE` for the controlling terms.
