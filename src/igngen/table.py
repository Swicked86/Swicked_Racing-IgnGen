from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass
class TimingTable:
    """RPM × load ignition timing grid (degrees BTDC)."""

    rpm: list[float]
    load: list[float]
    values: list[list[float]]  # values[rpm_i][load_j]

    def __post_init__(self) -> None:
        if not self.rpm:
            raise ValueError("rpm breakpoints required")
        if not self.load:
            raise ValueError("load breakpoints required")
        if len(self.values) != len(self.rpm):
            raise ValueError("values rows must match rpm count")
        for row in self.values:
            if len(row) != len(self.load):
                raise ValueError("each values row must match load count")

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rpm), len(self.load)

    def copy(self) -> TimingTable:
        return TimingTable(
            rpm=list(self.rpm),
            load=list(self.load),
            values=[list(row) for row in self.values],
        )

    def bump(self, degrees: float) -> TimingTable:
        out = self.copy()
        out.values = [[cell + degrees for cell in row] for row in out.values]
        return out

    def clamp(self, minimum: float, maximum: float) -> TimingTable:
        if minimum > maximum:
            raise ValueError("minimum cannot exceed maximum")
        out = self.copy()
        out.values = [
            [min(maximum, max(minimum, cell)) for cell in row] for row in out.values
        ]
        return out

    def format_grid(self, precision: int = 1) -> str:
        hdr = ["rpm"] + [_fmt(x, precision) for x in self.load]
        widths = [max(len(h), 6) for h in hdr]
        for i, rpm in enumerate(self.rpm):
            widths[0] = max(widths[0], len(_fmt(rpm, precision)))
            for j, cell in enumerate(self.values[i]):
                widths[j + 1] = max(widths[j + 1], len(_fmt(cell, precision)))

        def row_line(cols: Sequence[str]) -> str:
            return "  ".join(c.rjust(widths[i]) for i, c in enumerate(cols))

        lines = [row_line(hdr), row_line(["-" * w for w in widths])]
        for i, rpm in enumerate(self.rpm):
            cols = [_fmt(rpm, precision)] + [
                _fmt(cell, precision) for cell in self.values[i]
            ]
            lines.append(row_line(cols))
        return "\n".join(lines)


def parse_range(spec: str) -> list[float]:
    """Parse `start:stop:step` into inclusive breakpoints.

    Example: `500:8000:500` → 500, 1000, …, 8000
    """
    parts = [p.strip() for p in spec.split(":")]
    if len(parts) != 3:
        raise ValueError(f"expected start:stop:step, got {spec!r}")
    start, stop, step = (float(parts[0]), float(parts[1]), float(parts[2]))
    if step <= 0:
        raise ValueError("step must be > 0")
    if stop < start:
        raise ValueError("stop must be >= start")

    values: list[float] = []
    x = start
    # Inclusive stop with float-safe termination
    while x <= stop + step * 1e-9:
        values.append(round(x, 10))
        x += step
    if values and abs(values[-1] - stop) > abs(step) * 0.51:
        # If float drift skipped exact stop, append it
        if values[-1] < stop:
            values.append(stop)
    return values


def _fmt(value: float, precision: int) -> str:
    return f"{value:.{precision}f}".rstrip("0").rstrip(".") if precision >= 0 else str(value)


def assert_same_axes(a: TimingTable, b: TimingTable) -> None:
    if a.rpm != b.rpm or a.load != b.load:
        raise ValueError("tables must share the same RPM and load axes")
