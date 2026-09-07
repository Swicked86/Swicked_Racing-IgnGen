from igngen.axes import generate_load_axis, generate_rpm_axis
from igngen.model import EngineSpec, timing_at
from igngen.table import TimingTable


def test_axes_are_whole_numbers():
    spec = EngineSpec()
    for n in (8, 12, 16):
        rpm = generate_rpm_axis(spec, n)
        load = generate_load_axis(spec, n, unit="kPa")
        assert len(rpm) == n
        assert len(load) == n
        assert all(float(x).is_integer() for x in rpm)
        assert all(float(x).is_integer() for x in load)
        assert 100 in load or any(abs(x - 100) < 0.5 for x in load)


def test_vacuum_and_boost_limits_are_total_timing():
    spec = EngineSpec(
        base_timing=15,
        mech_timing_at_peak_torque=32,
        vacuum_advance_per_kpa=2.0,
        vacuum_advance_max=40,
        boost_retard_per_psi=3.0,
        boost_retard_max=12,
        atm_kpa=100,
        idle_pocket_width=0,
        soft_limit_retard=0,
    )
    # Deep vacuum: step would overshoot; clamp to total vacuum limit
    assert timing_at(4800, 40, spec, layers="full") == 40
    # Mild vacuum: below total limit → mechanical + step
    mild = timing_at(1100, 96, spec, layers="full")  # 4 kPa below → +8° on base 15 = 23
    assert mild == 23
    # Boost: step would go under floor; clamp to total boost limit
    over = 100 + 10 * 6.895  # 10 psi
    assert timing_at(4800, over, spec, layers="full") == 12


def test_default_view_bottom_left_origin():
    table = TimingTable(
        rpm=[1000.0, 2000.0],
        load=[40.0, 100.0],
        values=[[30.0, 20.0], [32.0, 18.0]],
        load_unit="kPa",
    )
    text = table.format_grid(layout="default", color=False)
    lines = text.splitlines()
    data = [ln for ln in lines if ln.strip()[:1].isdigit()]
    assert data[0].lstrip().startswith("100")
    assert data[-1].lstrip().startswith("40")
    assert any(ln.strip().startswith("rpm") for ln in lines)
    assert lines[-1].strip().startswith("RPM")
    rpm_line = next(ln for ln in lines if ln.strip().startswith("rpm"))
    assert "1000" in rpm_line and "2000" in rpm_line


def test_idle_pocket_width_affects_timing_full_layers():
    wide = EngineSpec(idle_rpm=1100, idle_pocket_width=400, base_timing=10)
    narrow = EngineSpec(idle_rpm=1100, idle_pocket_width=100, base_timing=10)
    t_wide = timing_at(1300, 45, wide, layers="full")
    t_narrow = timing_at(1300, 45, narrow, layers="full")
    assert t_wide != t_narrow



def test_inhg_load_axis_is_kpa_converted():
    """inHg axis = kPa generation first, then kpa_abs_to_inhg_gauge (idle band preserved)."""
    from igngen.axes import generate_load_axis
    from igngen.model import EngineSpec, timing_at
    from igngen.units import inhg_gauge_to_kpa_abs, kpa_abs_to_inhg_gauge

    spec = EngineSpec(
        base_timing=16,
        mech_timing_at_peak_torque=34,
        idle_rpm=900,
        idle_pocket_width=50,
        idle_pocket_bump=2,
        idle_map_lo=30,
        idle_map_hi=45,
        peak_torque_rpm=5200,
        redline_rpm=7200,
        boost_psi=0.0,
        cranking_rpm=500,
        cranking_timing=10,
        vacuum_total_timing=50,
    )
    kpa = generate_load_axis(spec, 16, unit="kPa")
    inhg = generate_load_axis(spec, 16, unit="inHg")
    assert len(kpa) == len(inhg) == 16
    assert all(
        abs(inhg[i] - kpa_abs_to_inhg_gauge(kpa[i], spec.atm_kpa)) < 1e-9
        for i in range(len(kpa))
    )
    band = [x for x in kpa if 30 <= x <= 45]
    assert len(band) >= 2, band
    k = band[0]
    assert timing_at(850, k, spec, layers="idle") == 18
    assert timing_at(900, k, spec, layers="idle") == 16
    assert timing_at(950, k, spec, layers="idle") == 14

