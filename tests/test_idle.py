"""Idle pocket: width is ±RPM from idle; ±° on those edges at idle MAP."""

from igngen.model import (
    EngineSpec,
    generate_table,
    idle_pocket_correction,
    idle_pocket_half_rpm,
    timing_at,
)
from igngen.axes import _pocket_edges, generate_rpm_axis


def _spec(**kwargs) -> EngineSpec:
    base = dict(
        base_timing=16,
        mech_timing_at_peak_torque=34,
        idle_rpm=750,
        idle_pocket_width=100,  # ±100 → 650 / 750 / 850
        peak_torque_rpm=5200,
        vacuum_total_timing=50,
        vacuum_full_map_kpa=40,
        boost_psi=10.4,
        boost_timing_limit=20,
        idle_map_lo=30,
        idle_map_hi=45,
        idle_pocket_bump=2,
        atm_kpa=100,
        redline_rpm=7200,
    )
    base.update(kwargs)
    return EngineSpec(**base)


def test_width_is_plus_minus_not_total_span():
    spec = _spec(idle_rpm=750, idle_pocket_width=100)
    assert idle_pocket_half_rpm(spec) == 100.0
    lo, hi = _pocket_edges(spec)
    assert lo == 650.0
    assert hi == 850.0


def test_axis_landmarks_match_plus_minus():
    spec = _spec(idle_rpm=750, idle_pocket_width=100)
    rpm = generate_rpm_axis(spec, 16)
    assert 650 in rpm or 650.0 in rpm
    assert 750 in rpm or 750.0 in rpm
    assert 850 in rpm or 850.0 in rpm


def test_stabilization_on_edges():
    spec = _spec(idle_rpm=750, idle_pocket_width=100, idle_pocket_bump=2)
    assert idle_pocket_correction(650, 35, spec) == 2.0
    assert idle_pocket_correction(750, 35, spec) == 0.0
    assert idle_pocket_correction(850, 35, spec) == -2.0
    # Upper edge sits slightly above idle, so boost surface may already be 17°
    # before −2° pocket (→ 15°). Assert correction + relative edges.
    assert timing_at(650, 35, spec, layers="idle") == 18
    assert timing_at(750, 35, spec, layers="idle") == 16
    assert timing_at(850, 35, spec, layers="idle") == timing_at(850, 35, spec, layers="boost") - 2


def test_d16z6_style_fifty():
    spec = _spec(idle_rpm=670, idle_pocket_width=50)
    lo, hi = _pocket_edges(spec)
    assert (lo, hi) == (620.0, 720.0)
    assert timing_at(620, 35, spec, layers="idle") == 18
    assert timing_at(720, 35, spec, layers="idle") == 14
