from __future__ import annotations

from .axes import generate_load_axis, generate_rpm_axis
from .profiles import EngineParameters
from .timing import mechanical_timing, timing_at


def _example() -> EngineParameters:
    return EngineParameters(
        idle_rpm=750,
        idle_pocket_width=250,
        peak_torque_rpm=3500,
        peak_hp_rpm=0,
        redline_rpm=6000,
        cranking_rpm=500,
        soft_limit_rpm_before_redline=500,
        overspeed_rpm_after_redline=1000,
        boost_psi=0,
    )


def test_rpm_axis_protects_structural_landmarks() -> None:
    spec = _example()
    axis = generate_rpm_axis(spec, 16)
    for expected in (500, 750, 1000, 3500, 5500, 6000, 7000):
        assert expected in axis
    assert len(axis) == 16
    assert axis == sorted(set(axis))


def test_rpm_discretionary_cells_are_pre_torque_dense() -> None:
    spec = _example()
    axis = generate_rpm_axis(spec, 20)
    pre = [x for x in axis if spec.idle_pocket_hi_rpm < x < spec.peak_torque_rpm]
    post = [x for x in axis if spec.peak_torque_rpm < x < spec.overspeed_rpm]
    # Structural high-RPM anchors already consume cells; discretionary placement
    # should still leave visibly greater resolution in the mechanical-climb region.
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
    spec.base_timing = 15
    spec.idle_timing_low = 20
    spec.idle_timing_target = 15
    spec.idle_timing_high = 5

    assert timing_at(500, 35, spec, include_soft_limit=False) == 20
    assert timing_at(750, 35, spec, include_soft_limit=False) == 15
    assert timing_at(1000, 35, spec, include_soft_limit=False) == 5
