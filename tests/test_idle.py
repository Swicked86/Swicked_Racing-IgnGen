"""Idle pocket: ±bump° across idle MAP band inside RPM pocket."""

from igngen.model import (
    EngineSpec,
    generate_table,
    idle_pocket_correction,
    timing_at,
)


def _spec(**kwargs) -> EngineSpec:
    base = dict(
        base_timing=16,
        mech_timing_at_peak_torque=34,
        idle_rpm=670,
        idle_pocket_width=100,
        peak_torque_rpm=5200,
        vacuum_total_timing=50,
        vacuum_full_map_kpa=40,
        boost_psi=10.4,
        boost_timing_limit=20,
        idle_map_lo=30,
        idle_map_hi=45,
        idle_pocket_bump=2,
        atm_kpa=100,
    )
    base.update(kwargs)
    return EngineSpec(**base)


def test_idle_map_band_plus_minus_bump():
    spec = _spec()
    # at idle RPM
    assert idle_pocket_correction(670, 30, spec) == 2.0
    assert idle_pocket_correction(670, 45, spec) == -2.0
    assert abs(idle_pocket_correction(670, 37.5, spec) - 0.0) < 1e-9


def test_outside_rpm_or_map_zero():
    spec = _spec()
    assert idle_pocket_correction(2000, 30, spec) == 0.0
    assert idle_pocket_correction(670, 20, spec) == 0.0
    assert idle_pocket_correction(670, 60, spec) == 0.0


def test_custom_stabilization_degrees():
    spec = _spec(idle_pocket_bump=3)
    assert idle_pocket_correction(670, 30, spec) == 3.0
    assert idle_pocket_correction(670, 45, spec) == -3.0


def test_idle_layer_applies_on_boost_surface():
    spec = _spec()
    # idle RPM, 30 kPa: boost surface at idle is mechanical 16 (vac gated) +2
    assert timing_at(670, 30, spec, layers="idle") == 18
    assert timing_at(670, 45, spec, layers="idle") == 14
    assert timing_at(670, 100, spec, layers="idle") == 16


def test_idle_table_cells():
    spec = _spec()
    table = generate_table(
        [670],
        [30, 37, 45, 100],
        spec=spec,
        load_unit="kPa",
        layers="idle",
    )
    assert table.values[0][0] == 18.0  # +2
    assert table.values[0][2] == 14.0  # -2
    assert table.values[0][3] == 16.0  # outside band
