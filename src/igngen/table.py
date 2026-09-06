from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .heatmap import colorize_timing


@dataclass
class TimingTable:
    """RPM × load ignition timing grid (degrees BTDC).

    Internal storage is always:
      rpm ascending, load ascending, values[rpm_i][load_j]
    Display/export orientation is applied at render time.
    """

    rpm: list[float]
    load: list[float]
    values: list[list[float]]  # values[rpm_i][load_j]
    load_unit: str = "inHg"

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
            load_unit=self.load_unit,
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

    def format_grid(
        self,
        *,
        precision: int = 2,
        layout: str = "alphalink",
        color: bool = True,
    ) -> str:
        """Render a terminal grid.

        layouts:
          - ``alphalink``: rows=RPM (top→bottom), cols=Load (left→right) — matches ALPHAlink
          - ``swicked``: rows=Load high→low (bottom-up feel), cols=RPM left→right
        """
        if layout == "swicked":
            return self._format_swicked(precision=precision, color=color)
        return self._format_alphalink(precision=precision, color=color)

    def _format_alphalink(self, *, precision: int, color: bool) -> str:
        hdr = ["rpm"] + [_fmt(x, precision) for x in self.load]
        widths = [max(len("rpm"), 6)] + [max(len(h), 6) for h in hdr[1:]]
        for i, rpm in enumerate(self.rpm):
            widths[0] = max(widths[0], len(_fmt(rpm, precision)))
            for j, cell in enumerate(self.values[i]):
                widths[j + 1] = max(widths[j + 1], len(_fmt(cell, precision)))

        def plain_row(cols: Sequence[str]) -> str:
            return "  ".join(c.rjust(widths[i]) for i, c in enumerate(cols))

        lines = [
            f"Load ({self.load_unit}) →",
            plain_row(hdr),
            plain_row(["-" * w for w in widths]),
        ]
        for i, rpm in enumerate(self.rpm):
            cells = [
                colorize_timing(cell, enabled=color, precision=precision)
                for cell in self.values[i]
            ]
            # pad colored cells to width using plain length
            padded = [_fmt(rpm, precision).rjust(widths[0])]
            for j, (plain, colored) in enumerate(
                zip((_fmt(c, precision) for c in self.values[i]), cells)
            ):
                pad = widths[j + 1] - len(plain)
                padded.append((" " * pad) + colored)
            lines.append("  ".join(padded))
        lines.append("RPM ↓")
        return "\n".join(lines)

    def _format_swicked(self, *, precision: int, color: bool) -> str:
        # Load descending rows, RPM ascending columns (visual bottom-up load)
        hdr = ["load"] + [_fmt(x, precision) for x in self.rpm]
        widths = [max(len("load"), 6)] + [max(6, len(h)) for h in hdr[1:]]
        load_order = list(reversed(range(len(self.load))))
        for j in load_order:
            widths[0] = max(widths[0], len(_fmt(self.load[j], precision)))
            for i, rpm_i in enumerate(range(len(self.rpm))):
                widths[i + 1] = max(
                    widths[i + 1], len(_fmt(self.values[rpm_i][j], precision))
                )

        def plain_row(cols: Sequence[str]) -> str:
            return "  ".join(c.rjust(widths[i]) for i, c in enumerate(cols))

        lines = [
            "Load ↑  (high load at top)",
            plain_row(hdr),
            plain_row(["-" * w for w in widths]),
        ]
        for j in load_order:
            padded = [_fmt(self.load[j], precision).rjust(widths[0])]
            for i in range(len(self.rpm)):
                cell = self.values[i][j]
                plain = _fmt(cell, precision)
                colored = colorize_timing(cell, enabled=color, precision=precision)
                pad = widths[i + 1] - len(plain)
                padded.append((" " * pad) + colored)
            lines.append("  ".join(padded))
        lines.append("RPM →")
        return "\n".join(lines)


def parse_range(spec: str) -> list[float]:
    """Parse `start:stop:step` into inclusive breakpoints."""
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
    while x <= stop + step * 1e-9:
        values.append(round(x, 10))
        x += step
    if values and values[-1] < stop and abs(values[-1] - stop) > abs(step) * 0.51:
        values.append(stop)
    return values


def _fmt(value: float, precision: int) -> str:
    return f"{value:.{precision}f}".rstrip("0").rstrip(".") if precision >= 0 else str(value)
