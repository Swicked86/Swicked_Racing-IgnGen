"""Boost retard mirrors vacuum: fan from 100 kPa with total° limit."""

from igngen.model import (
    EngineSpec,
    boost_low_at_rpm,
    boost_retard_full,
    boost_retard_at_rpm,
    generate_table,
    mechanical_advance,
    mechanical_progress,
    pressure_row_timings,
    timing_at,
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
        boost_psi=10.0,
        boost_timing_limit=20,
        boost_retard_max=20,
        atm_kpa=100,
    )
    base.update(kwargs)
    return EngineSpec(**base)


def test_boost_retard_scales_with_mechanical_progress():
    spec = _spec()  # retard_full = 32-20 = 12
    assert boost_retard_full(spec) == 12
    assert boost_retard_at_rpm(1100, spec) == 0.0
    assert boost_retard_at_rpm(4800, spec) == 12
    assert abs(boost_retard_at_rpm(2950, spec) - 6.0) < 1e-6


def test_full_boost_reaches_limit():
    spec = _spec()
    # max boost MAP ≈ 100 + 10*6.895 ≈ 168.9
    assert timing_at(4800, 170, spec, layers="boost") == 20
    assert timing_at(4800, 100, spec, layers="boost") == 32
    assert timing_at(4800, 40, spec, layers="boost") == 50


def test_idle_no_boost_or_vac_fan():
    spec = _spec()
    row = pressure_row_timings(1100, [20, 100, 170], spec, include_boost=True)
    assert row == [10, 10, 10]


def test_boost_cell_taper_whole_numbers():
    spec = _spec()
    # atm 100, max boost ~169; mids between
    loads = [100, 120, 140, 160, 170]
    row = pressure_row_timings(4800, loads, spec, include_boost=True)
    assert row[0] == 32
    assert row[-1] == 20
    # 120,140,160 are mids (100 < x < ~168.9); 170 is full
    assert row[1:4] == _whole_degree_taper(32, 20, 3)


def test_boost_table_layer():
    spec = _spec()
    table = generate_table(
        [4800],
        [40, 100, 170],
        spec=spec,
        load_unit="kPa",
        layers="boost",
    )
    assert table.values[0] == [50.0, 32.0, 20.0]


def test_vacuum_layer_ignores_boost_side():
    spec = _spec()
    assert timing_at(4800, 170, spec, layers="vacuum") == 32


def test_na_boost_psi_zero_ignored():
    """boost_psi=0: ignore boost retard — atm and tip stay on mechanical total."""
    spec = EngineSpec(
        base_timing=16,
        mech_timing_at_peak_torque=34,
        idle_rpm=670,
        peak_torque_rpm=5200,
        vacuum_total_timing=50,
        boost_psi=0.0,
        boost_timing_limit=20,
        atm_kpa=100,
    )
    assert timing_at(5200, 100, spec, layers="idle") == 34
    assert timing_at(5200, 120, spec, layers="idle") == 34
    row = pressure_row_timings(5200, [100.0, 120.0], spec, include_boost=True)
    assert row == [34, 34]
