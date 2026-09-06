from __future__ import annotations

import csv
import json
from pathlib import Path

from .table import TimingTable


def load_table(path: str | Path) -> TimingTable:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return load_json(path)
    return load_csv(path)


def save_table(table: TimingTable, path: str | Path, *, export: str = "swicked") -> None:
    path = Path(path)
    if path.suffix.lower() == ".json":
        save_json(table, path)
    else:
        save_csv(table, path, export=export)


def load_csv(path: str | Path) -> TimingTable:
    path = Path(path)
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"empty CSV: {path}")

    header = [h.strip() for h in rows[0]]
    if not header or header[0].lower() not in {"rpm", "load"}:
        raise ValueError("CSV header must start with 'rpm' or 'load'")

    if header[0].lower() == "rpm":
        load = [float(int(round(float(x)))) for x in header[1:]]
        rpm: list[float] = []
        values: list[list[float]] = []
        for row in rows[1:]:
            if not row or all(not c.strip() for c in row):
                continue
            if len(row) != len(header):
                raise ValueError(f"row length mismatch in {path}")
            rpm.append(float(int(round(float(row[0])))))
            values.append([float(int(round(float(c)))) for c in row[1:]])
        return TimingTable(rpm=rpm, load=load, values=values)

    rpm = [float(int(round(float(x)))) for x in header[1:]]
    load_vals: list[float] = []
    raw_rows: list[list[float]] = []
    for row in rows[1:]:
        if not row or all(not c.strip() for c in row):
            continue
        load_vals.append(float(int(round(float(row[0])))))
        raw_rows.append([float(int(round(float(c)))) for c in row[1:]])
    pairs = sorted(zip(load_vals, raw_rows), key=lambda p: p[0])
    load_sorted = [p[0] for p in pairs]
    values = []
    for i in range(len(rpm)):
        values.append([pairs[j][1][i] for j in range(len(load_sorted))])
    return TimingTable(rpm=rpm, load=load_sorted, values=values)


def save_csv(table: TimingTable, path: str | Path, *, export: str = "swicked") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        if export in {"alpha", "alphalink"}:
            writer.writerow(["rpm", *[_num(x) for x in table.load]])
            for i, r in enumerate(table.rpm):
                writer.writerow([_num(r), *[str(int(round(c))) for c in table.values[i]]])
            return

        # swicked / base: load ascending (low→high) so first data row is low load;
        # last row is high load — bottom-left origin when viewed with RPM→
        writer.writerow(["load", *[_num(x) for x in table.rpm]])
        for j in range(len(table.load)):
            writer.writerow(
                [
                    _num(table.load[j]),
                    *[str(int(round(table.values[i][j]))) for i in range(len(table.rpm))],
                ]
            )


def load_json(path: str | Path) -> TimingTable:
    path = Path(path)
    data = json.loads(path.read_text())
    return TimingTable(
        rpm=[float(int(round(float(x)))) for x in data["rpm"]],
        load=[float(int(round(float(x)))) for x in data["load"]],
        values=[[float(int(round(float(c)))) for c in row] for row in data["values"]],
        load_unit=str(data.get("load_unit", "inHg")),
    )


def save_json(table: TimingTable, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rpm": [int(r) for r in table.rpm],
        "load": [int(v) for v in table.load],
        "values": [[int(round(c)) for c in row] for row in table.values],
        "load_unit": table.load_unit,
        "units": {"timing": "deg_btdc_integer", "load": table.load_unit},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _num(value: float) -> str:
    return str(int(round(value)))
