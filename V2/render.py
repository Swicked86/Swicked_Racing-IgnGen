from __future__ import annotations

from igngen.table import TimingTable

from .profiles import EngineParameters
from .timing import timing_at


def build_table(
    rpm_axis: list[float],
    load_axis_kpa: list[float],
    spec: EngineParameters,
) -> TimingTable:
    """Build a TimingTable using the existing V1 renderer/layout implementation."""
    values: list[list[float]] = []
    for rpm in rpm_axis:
        row = [float(round(timing_at(rpm, map_kpa, spec))) for map_kpa in load_axis_kpa]
        values.append(row)

    return TimingTable(
        rpm=[float(round(v)) for v in rpm_axis],
        load=[float(round(v)) for v in load_axis_kpa],
        values=values,
        load_unit="kPa",
    )
