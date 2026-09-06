"""Test situations for vacuum advance layer (mechanical + vacuum)."""

from igngen.model import (
    EngineSpec,
    generate_table,
    mechanical_advance,
    timing_at,
    vacuum_advance,
)


def _spec(**kwargs) -> EngineSpec:
    base = dict(
        base_timing=10,
        mech_timing_at_peak_torque=32,
        idle_rpm=1100,
        peak_torque_rpm=4800,
        vacuum_advance=10,
        vacuum_full_map_kpa=50,
        vacuum_advance_max=42,
        atm_kpa=100,
    )
    base.update(kwargs)
    return EngineSpec(**base)


def test_full_vacuum_at_or_below_50_kpa():
    spec = _spec()
    assert vacuum_advance(50, spec) == 10
    assert vacuum_advance(20, spec) == 10
    assert vacuum_advance(45, spec) == 10


def test_zero_vacuum_at_atmosphere():
    spec = _spec()
    assert vacuum_advance(100, spec) == 0
    assert vacuum_advance(120, spec) == 0


def test_taper_between_50_and_atm():
    spec = _spec()
    mid = vacuum_advance(75, spec)  # halfway 50→100
    assert abs(mid - 5.0) < 1e-6
    assert 0 < vacuum_advance(60, spec) < 10
    assert 0 < vacuum_advance(90, spec) < 5


def test_vacuum_layer_adds_on_mechanical():
    spec = _spec()
    # at peak TQ: mech 32 + vac 10 = 42 at ≤50 kPa
    assert timing_at(4800, 50, spec, layers="vacuum") == 42
    assert timing_at(4800, 20, spec, layers="vacuum") == 42
    # at atm: mechanical only
    assert timing_at(4800, 100, spec, layers="vacuum") == 32
    # idle + full vac
    assert timing_at(1100, 45, spec, layers="vacuum") == 20


def test_vacuum_respects_total_ceiling():
    spec = _spec(vacuum_advance=20, vacuum_advance_max=42)
    # 32 + 20 would be 52 → clamp to 42
    assert timing_at(4800, 40, spec, layers="vacuum") == 42


def test_mechanical_layer_still_ignores_load():
    spec = _spec()
    for map_kpa in (20, 50, 100, 148):
        assert timing_at(4800, map_kpa, spec, layers="mechanical") == 32


def test_vacuum_table_varies_with_load():
    spec = _spec()
    table = generate_table(
        [4800],
        [20, 50, 75, 100],
        spec=spec,
        load_unit="kPa",
        layers="vacuum",
    )
    assert table.values[0] == [42.0, 42.0, 37.0, 32.0]


def test_static_50_kpa_full_in_not_rate_based():
    """Full-in MAP is the breakpoint; amount is vacuum_advance °."""
    spec = _spec(vacuum_advance=12, vacuum_full_map_kpa=50)
    assert vacuum_advance(50, spec) == 12
    assert vacuum_advance(49, spec) == 12
    assert abs(vacuum_advance(75, spec) - 6.0) < 1e-6
