from igngen.axes import generate_load_axis, generate_rpm_axis
from igngen.model import EngineSpec, pressure_correction, timing_at
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


def test_vacuum_and_boost_step_limits():
    spec = EngineSpec(
        vacuum_advance_per_kpa=0.5,
        vacuum_advance_max=10,
        boost_retard_per_psi=2.0,
        boost_retard_max=8,
        atm_kpa=100,
    )
    # 20 kPa below atm → 10° advance, hit limit
    assert pressure_correction(80, spec) == 10.0
    # 4 psi over → 8° retard, hit limit
    over = 100 + 4 * 6.895
    assert pressure_correction(over, spec) == -8.0
    # small vacuum not at limit
    assert abs(pressure_correction(96, spec) - 2.0) < 1e-9


def test_swicked_view_low_load_first():
    table = TimingTable(
        rpm=[1000.0, 2000.0],
        load=[40.0, 100.0],
        values=[[30.0, 20.0], [32.0, 18.0]],
        load_unit="kPa",
    )
    text = table.format_grid(layout="swicked", color=False)
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("-") and not ln.startswith("Load") and not ln.startswith("RPM")]
    # first data row after header should be load 40
    assert "40" in lines[0].split()[0] or lines[0].strip().startswith("40")


def test_idle_pocket_width_affects_timing():
    wide = EngineSpec(idle_rpm=1100, idle_pocket_width=400, base_timing=15)
    narrow = EngineSpec(idle_rpm=1100, idle_pocket_width=100, base_timing=15)
    # 200 RPM off idle: inside wide pocket, outside narrow
    t_wide = timing_at(1300, 45, wide)
    t_narrow = timing_at(1300, 45, narrow)
    assert t_wide != t_narrow
