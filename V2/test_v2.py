from __future__ import annotations

from .axes import generate_load_axis, generate_rpm_axis
from .profiles import EngineParameters, load_engine_profile, save_engine_profile
from .timing import mechanical_timing, timing_at


def _example() -> EngineParameters:
    return EngineParameters(
        idle_rpm=750,
        idle_pocket_width=100,
        idle_pocket_lower_share=0.25,
        idle_pocket_upper_share=0.75,
        idle_timing_target=10,
        idle_timing_delta=6,
        idle_map_lo=30,
        idle_map_hi=45,
        peak_torque_rpm=3500,
        peak_hp_rpm=0,
        redline_rpm=6000,
        cranking_rpm=500,
        soft_limit_rpm_before_redline=500,
        overspeed_rpm_after_redline=1000,
        boost_psi=0,
    )


def test_idle_pocket_uses_total_width_and_25_75_split() -> None:
    spec = _example()
    assert spec.idle_pocket_lo_rpm == 725
    assert spec.idle_rpm == 750
    assert spec.idle_pocket_hi_rpm == 825
    assert spec.derived_idle_targets() == (16.0, 10.0, 4.0)


def test_rpm_axis_protects_structural_landmarks() -> None:
    spec = _example()
    axis = generate_rpm_axis(spec, 16)
    for expected in (500, 725, 750, 825, 3500, 5500, 6000, 7000):
        assert expected in axis
    assert len(axis) == 16
    assert axis == sorted(set(axis))


def test_rpm_discretionary_cells_are_pre_torque_dense() -> None:
    spec = _example()
    axis = generate_rpm_axis(spec, 20)
    pre = [x for x in axis if spec.idle_pocket_hi_rpm < x < spec.peak_torque_rpm]
    post = [x for x in axis if spec.peak_torque_rpm < x < spec.overspeed_rpm]
    assert len(pre) >= 5
    assert len(axis) == 20
    assert len(pre) >= len(post) - 2


def test_load_axis_always_contains_atmosphere() -> None:
    for boost in (0.0, 7.0, 10.0, 25.0):
        spec = _example()
        spec.boost_psi = boost
        for count in (8, 12, 16):
            axis = generate_load_axis(spec, count)
            assert 100.0 in axis
            assert len(axis) == count
            assert axis == sorted(set(axis))


def test_load_axis_uses_only_one_row_below_idle_region() -> None:
    spec = _example()
    for count in (8, 12, 16, 20):
        axis = generate_load_axis(spec, count)
        below_idle = [point for point in axis if point < spec.idle_map_lo]
        assert len(below_idle) == 1
        assert below_idle[0] < spec.idle_map_lo
        assert spec.idle_map_lo in axis
        assert spec.idle_map_hi in axis
        assert 100.0 in axis


def test_cammed_idle_map_moves_low_end_of_axis_upward() -> None:
    stockish = _example()
    cammed = stockish.with_overrides(idle_map_lo=50, idle_map_hi=65)

    stock_axis = generate_load_axis(stockish, 16)
    cammed_axis = generate_load_axis(cammed, 16)

    assert len([point for point in stock_axis if point < 30]) == 1
    assert len([point for point in cammed_axis if point < 50]) == 1
    assert min(cammed_axis) > min(stock_axis)
    assert 50.0 in cammed_axis
    assert 65.0 in cammed_axis
    assert 100.0 in cammed_axis


def test_idle_map_changes_are_profile_inputs_and_axis_candidates() -> None:
    stockish = _example()
    cammed = stockish.with_overrides(idle_map_lo=50, idle_map_hi=65)
    assert stockish.idle_map_lo == 30
    assert cammed.idle_map_lo == 50
    assert cammed.idle_map_hi == 65
    axis = generate_load_axis(cammed, 12)
    assert any(50 <= point <= 65 for point in axis)
    assert 100.0 in axis


def test_vacuum_is_full_at_40_kpa_only_after_mechanical_progress() -> None:
    spec = _example()
    spec.base_timing = 15
    spec.mech_timing_at_peak_torque = 36
    spec.vacuum_total_timing = 50
    spec.vacuum_full_map_kpa = 40

    assert mechanical_timing(3500, spec) == 36
    assert timing_at(3500, 100, spec, include_idle_pocket=False, include_soft_limit=False) == 36
    assert timing_at(3500, 40, spec, include_idle_pocket=False, include_soft_limit=False) == 50
    assert timing_at(750, 40, spec, include_idle_pocket=False, include_soft_limit=False) == 15


def test_idle_pocket_overrides_pressure_surface() -> None:
    spec = _example()
    assert timing_at(725, 35, spec, include_soft_limit=False) == 16
    assert timing_at(750, 35, spec, include_soft_limit=False) == 10
    assert timing_at(825, 35, spec, include_soft_limit=False) == 4


def test_temporary_overrides_do_not_mutate_loaded_defaults() -> None:
    base = _example()
    edited = base.with_overrides(idle_map_lo=48, idle_map_hi=62, idle_timing_target=12)
    assert base.idle_map_lo == 30
    assert base.idle_timing_target == 10
    assert edited.idle_map_lo == 48
    assert edited.idle_map_hi == 62
    assert edited.idle_timing_target == 12


def test_save_and_reload_custom_engine(tmp_path) -> None:
    spec = _example().with_overrides(name="Cammed B18", description="test profile", idle_map_lo=48, idle_map_hi=62)
    path = tmp_path / "cammed_b18.ini"
    save_engine_profile(spec, path)
    loaded = load_engine_profile(path)
    assert loaded.name == "Cammed B18"
    assert loaded.idle_pocket_width == 100
    assert loaded.idle_pocket_lower_share == 0.25
    assert loaded.idle_pocket_upper_share == 0.75
    assert loaded.idle_timing_target == 10
    assert loaded.idle_timing_delta == 6
    assert loaded.idle_map_lo == 48
    assert loaded.idle_map_hi == 62
