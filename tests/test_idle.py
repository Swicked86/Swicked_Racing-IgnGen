"""Idle pocket: ±bump° on RPM edges at idle MAP (620=+2, 670=0, 720=-2)."""

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
        idle_pocket_width=100,  # ±50 → 620 / 670 / 720
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


def test_rpm_edges_plus_minus_bump():
    spec = _spec()
    assert idle_pocket_correction(620, 35, spec) == 2.0
    assert idle_pocket_correction(670, 35, spec) == 0.0
    assert idle_pocket_correction(720, 35, spec) == -2.0


def test_timing_matches_user_example():
    """620→18, 670→16, 720→14 on 16° base with ±2 at idle MAP."""
    spec = _spec()
    assert timing_at(620, 35, spec, layers="idle") == 18
    assert timing_at(670, 35, spec, layers="idle") == 16
    assert timing_at(720, 35, spec, layers="idle") == 14


def test_outside_rpm_or_map_zero():
    spec = _spec()
    assert idle_pocket_correction(2000, 35, spec) == 0.0
    assert idle_pocket_correction(670, 20, spec) == 0.0
    assert idle_pocket_correction(620, 100, spec) == 0.0


def test_custom_stabilization_degrees():
    spec = _spec(idle_pocket_bump=3)
    assert idle_pocket_correction(620, 35, spec) == 3.0
    assert idle_pocket_correction(720, 35, spec) == -3.0


def test_idle_table_rpm_cells():
    spec = _spec()
    table = generate_table(
        [620, 670, 720],
        [35, 100],
        spec=spec,
        load_unit="kPa",
        layers="idle",
    )
    # values[rpm][load]
    assert table.values[0][0] == 18.0
    assert table.values[1][0] == 16.0
    assert table.values[2][0] == 14.0
    # outside idle MAP — no pocket
    assert table.values[0][1] == 16.0
    assert table.values[1][1] == 16.0
    assert table.values[2][1] == 16.0
