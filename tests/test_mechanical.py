"""Test situations for mechanical advance only (layer 1).

These are the checks we agree on before adding vacuum / boost / idle pocket.
"""

from igngen.model import EngineSpec, generate_table, mechanical_advance, timing_at


def _default() -> EngineSpec:
    return EngineSpec(
        base_timing=10,
        mech_timing_at_peak_torque=32,
        idle_rpm=1100,
        peak_torque_rpm=4800,
    )


def test_idle_is_base_timing():
    spec = _default()
    assert mechanical_advance(1100, spec) == 10
    assert mechanical_advance(800, spec) == 10
    assert timing_at(1100, 45, spec, layers="mechanical") == 10
    assert timing_at(1100, 100, spec, layers="mechanical") == 10


def test_peak_torque_is_mech_total():
    spec = _default()
    assert mechanical_advance(4800, spec) == 32
    assert timing_at(4800, 100, spec, layers="mechanical") == 32


def test_holds_after_peak_torque():
    spec = _default()
    assert mechanical_advance(7800, spec) == 32
    assert mechanical_advance(9300, spec) == 32


def test_low_perf_lower_base():
    """Small-cam / low-compression: less initial timing."""
    spec = EngineSpec(base_timing=6, mech_timing_at_peak_torque=28, idle_rpm=900, peak_torque_rpm=4000)
    assert timing_at(900, 100, spec, layers="mechanical") == 6
    assert timing_at(4000, 100, spec, layers="mechanical") == 28


def test_mechanical_ignores_load():
    spec = _default()
    for map_kpa in (20, 60, 100, 148):
        assert timing_at(4800, map_kpa, spec, layers="mechanical") == 32


def test_mechanical_table_flat_across_load():
    spec = _default()
    table = generate_table(
        [1100, 4800, 7800],
        [20, 100, 148],
        spec=spec,
        load_unit="kPa",
        layers="mechanical",
    )
    # same RPM → same timing every load column
    assert table.values[0] == [10.0, 10.0, 10.0]
    assert table.values[1] == [32.0, 32.0, 32.0]
    assert table.values[2] == [32.0, 32.0, 32.0]


def test_ramp_is_between_base_and_peak():
    spec = _default()
    mid = mechanical_advance(3000, spec)
    assert 10 < mid < 32
