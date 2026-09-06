"""Vacuum fans from 100 kPa master curve; scaled by mechanical progress."""

from igngen.model import (
    EngineSpec,
    generate_table,
    mechanical_advance,
    mechanical_progress,
    timing_at,
    vacuum_add_at_rpm,
    vacuum_add_full,
    vacuum_high_at_rpm,
    vacuum_row_timings,
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
    assert _whole_degree_taper(50, 34, 4) == [46, 43, 40, 37]


def test_mechanical_progress_matches_advance_schedule():
    spec = _spec()
    assert mechanical_progress(1100, spec) == 0.0
    assert mechanical_progress(4800, spec) == 1.0
    assert abs(mechanical_progress(2950, spec) - 0.5) < 1e-6


def test_vacuum_add_scales_with_mechanical_progress():
    spec = _spec()  # add_full = 50-32 = 18
    assert vacuum_add_full(spec) == 18
    assert vacuum_add_at_rpm(1100, spec) == 0.0
    assert vacuum_add_at_rpm(4800, spec) == 18
    mid = vacuum_add_at_rpm(2950, spec)
    assert abs(mid - 9.0) < 1e-6


def test_idle_equals_mechanical_across_loads():
    spec = _spec()
    row = vacuum_row_timings(1100, [20, 40, 60, 100], spec)
    assert row == [10, 10, 10, 10]
    assert timing_at(1100, 30, spec, layers="vacuum") == 10


def test_full_advance_reaches_total_at_40_kpa():
    spec = _spec()
    assert timing_at(4800, 40, spec, layers="vacuum") == 50
    assert timing_at(4800, 20, spec, layers="vacuum") == 50
    assert timing_at(4800, 100, spec, layers="vacuum") == 32


def test_mid_rpm_fans_from_master_curve():
    spec = _spec()
    # progress 0.5 → mech 21, add 9 → high 30
    rpm = 2950
    mech = mechanical_advance(rpm, spec)
    assert abs(mech - 21.0) < 1e-6
    high = vacuum_high_at_rpm(rpm, spec)
    assert abs(high - 30.0) < 1e-6
    assert timing_at(rpm, 100, spec, layers="vacuum") == 21
    assert timing_at(rpm, 40, spec, layers="vacuum") == 30


def test_cell_taper_whole_numbers():
    spec = _spec()
    loads = [20, 30, 40, 55, 60, 80, 100]
    row = vacuum_row_timings(4800, loads, spec)
    assert row[0] == row[1] == row[2] == 50
    assert row[-1] == 32
    assert row[3:-1] == _whole_degree_taper(50, 32, 3)


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
