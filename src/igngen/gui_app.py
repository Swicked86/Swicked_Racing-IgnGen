from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .units import kpa_abs_to_inhg_gauge
from .calibration import (
    EngineParameters,
    build_table,
    generate_load_axis,
    generate_rpm_axis,
    list_engine_profiles,
    load_engine_profile,
)

GUI_DIR = Path(__file__).with_name("gui")
ATTRIBUTION = {
    "name": "Swicked Racing",
    "product": "IgnGen",
    "phrase": "Ignition table generation by Swicked Racing IgnGen",
    "url": "https://github.com/Swicked86/Swicked_Racing-IgnGen",
}


def _engine_dict(spec: EngineParameters) -> dict[str, Any]:
    data = asdict(spec)
    data["idle_pocket_lo_rpm"] = spec.idle_pocket_lo_rpm
    data["idle_pocket_hi_rpm"] = spec.idle_pocket_hi_rpm
    data["soft_limit_start_rpm"] = spec.soft_limit_start_rpm
    data["overspeed_rpm"] = spec.overspeed_rpm
    data["max_boost_map_kpa"] = spec.max_boost_map_kpa
    return data


def list_engines_payload() -> list[dict[str, Any]]:
    engines = []
    for path in list_engine_profiles():
        spec = load_engine_profile(path)
        engines.append({"id": path.stem, "name": spec.name, "description": spec.description})
    return engines


def load_engine_payload(name: str) -> dict[str, Any]:
    return _engine_dict(load_engine_profile(name))


def _coerce_spec(payload: dict[str, Any]) -> EngineParameters:
    base_name = str(payload.get("engine", "other") or "other")
    spec = load_engine_profile(base_name)
    changes: dict[str, Any] = {}
    for field in spec.__dataclass_fields__:
        if field in {"name", "description"}:
            continue
        if field in payload and payload[field] not in (None, ""):
            changes[field] = float(payload[field])
    spec = spec.with_overrides(**changes)

    if spec.idle_map_hi <= spec.idle_map_lo:
        raise ValueError("idle MAP high must be greater than idle MAP low")
    if spec.idle_pocket_width <= 0:
        raise ValueError("idle pocket width must be greater than zero")
    if spec.redline_rpm <= spec.idle_rpm:
        raise ValueError("redline must be greater than idle RPM")
    if spec.boost_retard_gain < 0:
        raise ValueError("boost retard gain must be >= 0")
    if spec.vacuum_full_map_kpa >= spec.atm_kpa:
        raise ValueError("full-vacuum MAP must be below atmospheric MAP")
    return spec


def _alpha_load_axis(table, atm_kpa: float) -> list[float]:
    return [round(kpa_abs_to_inhg_gauge(float(v), atm_kpa), 2) for v in table.load]


def _export_payload(table, export_mode: str, *, atm_kpa: float) -> dict[str, Any]:
    """Return the selected external row/column orientation without changing canonical data."""
    if export_mode == "alpha":
        load_inhg = _alpha_load_axis(table, atm_kpa)
        return {
            "format": "alpha",
            "row_axis": "rpm",
            "column_axis": "load_inhg_gauge",
            "units": {"row": "rpm", "column": "inHg_gauge", "timing": "deg_BTDC"},
            "rows": [
                [int(round(table.rpm[i])), *[int(round(v)) for v in table.values[i]]]
                for i in range(len(table.rpm))
            ],
            "columns": ["rpm", *load_inhg],
        }
    return {
        "format": "default",
        "row_axis": "load_kpa",
        "column_axis": "rpm",
        "units": {"row": "kPa_abs", "column": "rpm", "timing": "deg_BTDC"},
        "rows": [
            [int(round(table.load[j])), *[int(round(table.values[i][j])) for i in range(len(table.rpm))]]
            for j in range(len(table.load))
        ],
        "columns": ["load_kpa", *[int(round(v)) for v in table.rpm]],
    }


def generate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Public integration boundary: calibration inputs -> generated table JSON.

    Canonical table data remains kPa absolute and RPM-major. Alpha view/export
    receives an additional ALPHAlink-style inHg gauge load axis where 0 inHg is
    the atmospheric crossover, vacuum is negative, and boost is positive.
    """
    spec = _coerce_spec(payload)
    rows = max(6, min(64, int(payload.get("load_cells", 16))))
    cols = max(6, min(64, int(payload.get("rpm_cells", 20))))
    view_mode = str(payload.get("view", "default") or "default").lower()
    export_mode = str(payload.get("export", "default") or "default").lower()
    if view_mode not in {"default", "alpha"}:
        raise ValueError("view must be 'default' or 'alpha'")
    if export_mode not in {"default", "alpha"}:
        raise ValueError("export must be 'default' or 'alpha'")

    rpm = generate_rpm_axis(spec, cols)
    load = generate_load_axis(spec, rows)
    table = build_table(rpm, load, spec)
    alpha_load_inhg = _alpha_load_axis(table, spec.atm_kpa)
    return {
        "schema": "igngen.table.v1",
        "engine": spec.name,
        "view": view_mode,
        "export": export_mode,
        "units": {"rpm": "rpm", "load": "kPa_abs", "timing": "deg_BTDC"},
        "rpm": [int(round(v)) for v in table.rpm],
        "load_kpa": [int(round(v)) for v in table.load],
        "load_inhg_gauge": alpha_load_inhg,
        "timing": [[int(round(v)) for v in row] for row in table.values],
        "export_table": _export_payload(table, export_mode, atm_kpa=spec.atm_kpa),
        "attribution": ATTRIBUTION,
    }


class _Handler(BaseHTTPRequestHandler):
    server_version = "IgnGenGUI/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _json(self, status: int, data: Any) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/engines":
            self._json(200, {"engines": list_engines_payload(), "attribution": ATTRIBUTION})
            return
        if self.path.startswith("/api/engine/"):
            name = self.path.split("/api/engine/", 1)[1]
            try:
                self._json(200, load_engine_payload(name))
            except Exception as exc:
                self._json(404, {"error": str(exc)})
            return

        rel = "index.html" if self.path in {"", "/"} else self.path.lstrip("/")
        target = (GUI_DIR / rel).resolve()
        try:
            target.relative_to(GUI_DIR.resolve())
        except ValueError:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if self.path != "/api/generate":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._json(200, generate_payload(payload))
        except Exception as exc:
            self._json(400, {"error": str(exc)})


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer((host, port), _Handler)
    actual_port = int(server.server_address[1])
    url = f"http://{host}:{actual_port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, url


def launch_gui(*, browser: bool = False, debug: bool = False) -> int:
    server, url = start_server()
    try:
        if not browser:
            try:
                import webview  # type: ignore

                webview.create_window(
                    "Swicked Racing IgnGen",
                    url,
                    width=1450,
                    height=920,
                    min_size=(1050, 700),
                    background_color="#09111a",
                )
                webview.start(debug=debug)
                return 0
            except ImportError:
                pass

        print(f"IgnGen GUI: {url}")
        webbrowser.open(url)
        try:
            input("Press Enter to stop IgnGen GUI... ")
        except (EOFError, KeyboardInterrupt):
            pass
        return 0
    finally:
        server.shutdown()
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch the IgnGen desktop/browser GUI")
    parser.add_argument("--browser", action="store_true", help="Use the default browser instead of pywebview")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)
    return launch_gui(browser=args.browser, debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
