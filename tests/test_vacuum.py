"""Test vacuum total-timing layer (≤40 kPa + whole° cell taper)."""

from igngen.model import (
    EngineSpec,
    generate_table,
    mechanical_advance,
    timing_at,
    vacuum_row_timings,
    vacuum_rpm_scale,
    _whole_degree_taper,
)


def _spec(**kwargs) -> EngineSpec:
    base = dict(
        base_timing=10,
        mech_timing_at_peak_torque=32,
        idle_rpm=1100,
        idle_pocket_width=250,
        peak_torque_rpm=4800,
        vacuum_total_timing=50,
        vacuum_full_map_kpa=40,
        atm_kpa=100,
    )
    base.update(kwargs)
    return EngineSpec(**base)


def test_whole_degree_taper_splits_evenly():
    # 50 → 34 across 4 mid cells: 5 gaps, diff 16 → 4,3,3,3,3 → 46,43,40,37
    assert _whole_degree_taper(50, 34, 4) == [46, 43, 40, 37]


def test_idle_pocket_no_vacuum():
    spec = _spec()
    assert vacuum_rpm_scale(1100, spec) == 0.0
    assert timing_at(1100, 30, spec, layers="vacuum") == 10
    row = vacuum_row_timings(1100, [20, 40, 60, 100], spec)
    assert row == [10, 10, 10, 10]


def test_full_vacuum_at_or_below_40_kpa():
    spec = _spec()
    # well above idle pocket / full RPM
    assert timing_at(4800, 40, spec, layers="vacuum") == 50
    assert timing_at(4800, 20, spec, layers="vacuum") == 50
    assert timing_at(4800, 100, spec, layers="vacuum") == 32


def test_cell_taper_whole_numbers():
    spec = _spec()
    loads = [20, 30, 40, 55, 60, 80, 100]
    row = vacuum_row_timings(4800, loads, spec)
    assert row[0] == row[1] == row[2] == 50  # ≤40
    assert row[-1] == 32  # atm
    # mids are ints between 50 and 32
    assert row[3:-1] == _whole_degree_taper(50, 32, 3)
    assert all(isinstance(x, int) for x in row)


def test_vacuum_table_uses_cell_taper():
    spec = _spec()
    table = generate_table(
        [4800],
        [20, 40, 60, 80, 100],
        spec=spec,
        load_unit="kPa",
        layers="vacuum",
    )
    assert table.values[0][0] == 50.0
    assert table.values[0][1] == 50.0
    assert table.values[0][-1] == 32.0
    mids = [int(table.values[0][i]) for i in (2, 3)]
    assert mids == _whole_degree_taper(50, 32, 2)


def test_mechanical_layer_still_ignores_load():
    spec = _spec()
    for map_kpa in (20, 50, 100, 148):
        assert timing_at(4800, map_kpa, spec, layers="mechanical") == 32
