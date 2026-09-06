from pathlib import Path

from igngen.axes import generate_rpm_axis
from igngen.vehicles import find_vehicle, load_vehicle


def test_d16z6_vehicle_loads():
    repo = Path(__file__).resolve().parents[1]
    v = find_vehicle("D16Z6", search_dirs=[repo / "vehicles"])
    assert v is not None
    assert v.name == "D16Z6"
    s = v.spec
    assert s.peak_hp == 125
    assert s.peak_hp_rpm == 6600
    assert s.peak_torque_lbft == 106
    assert s.peak_torque_rpm == 5200
    assert s.redline_rpm == 7200
    assert s.idle_rpm == 670
    assert s.idle_pocket_width == 100
    assert s.base_timing == 16
    assert s.mech_timing_at_peak_torque == 34
    assert abs(s.boost_psi - 10.4) < 0.15


def test_d16z6_rpm_axis_hits_idle_pocket_and_peaks():
    repo = Path(__file__).resolve().parents[1]
    v = load_vehicle(repo / "vehicles" / "d16z6.ini")
    axis = generate_rpm_axis(v.spec, 16)
    assert len(axis) == 16
    # idle pocket 670 ± 50 → 620 … 670 … 720
    assert any(abs(x - 620) < 1 for x in axis)
    assert any(abs(x - 670) < 1 for x in axis)
    assert any(abs(x - 720) < 1 for x in axis)
    assert any(abs(x - 5200) < 1 for x in axis)
    assert any(abs(x - 7200) < 1 for x in axis)
    # overspeed ~8200
    assert max(axis) >= 8000
