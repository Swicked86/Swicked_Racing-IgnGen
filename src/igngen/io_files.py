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


def save_table(table: TimingTable, path: str | Path) -> None:
    path = Path(path)
    if path.suffix.lower() == ".json":
        save_json(table, path)
    else:
        save_csv(table, path)


def load_csv(path: str | Path) -> TimingTable:
    path = Path(path)
    with path.open(newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"empty CSV: {path}")

    header = [h.strip() for h in rows[0]]
    if not header or header[0].lower() != "rpm":
        raise ValueError("CSV header must start with 'rpm'")

    load = [float(x) for x in header[1:]]
    rpm: list[float] = []
    values: list[list[float]] = []
    for row in rows[1:]:
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) != len(header):
            raise ValueError(f"row length mismatch in {path}")
        rpm.append(float(row[0]))
        values.append([float(c) for c in row[1:]])

    return TimingTable(rpm=rpm, load=load, values=values)


def save_csv(table: TimingTable, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["rpm", *[ _num(x) for x in table.load ]])
        for i, r in enumerate(table.rpm):
            writer.writerow([_num(r), *[_num(c) for c in table.values[i]]])


def load_json(path: str | Path) -> TimingTable:
    path = Path(path)
    data = json.loads(path.read_text())
    return TimingTable(
        rpm=[float(x) for x in data["rpm"]],
        load=[float(x) for x in data["load"]],
        values=[[float(c) for c in row] for row in data["values"]],
    )


def save_json(table: TimingTable, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rpm": table.rpm,
        "load": table.load,
        "values": table.values,
        "units": {"timing": "deg_btdc", "load": "percent_or_kpa"},
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _num(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4g}"
