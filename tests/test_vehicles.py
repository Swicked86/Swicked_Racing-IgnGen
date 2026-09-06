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
    assert any(abs(x - 620) < 1 for x in axis)
    assert any(abs(x - 670) < 1 for x in axis)
    assert any(abs(x - 720) < 1 for x in axis)
    assert any(abs(x - 5200) < 1 for x in axis)
    assert any(abs(x - 7200) < 1 for x in axis)
    assert max(axis) >= 8000


def test_d16z6_fillers_are_multiples_of_50():
    repo = Path(__file__).resolve().parents[1]
    v = load_vehicle(repo / "vehicles" / "d16z6.ini")
    s = v.spec
    axis = generate_rpm_axis(s, 16)
    specified = {
        300.0,
        float(s.idle_rpm - s.idle_pocket_width / 2),
        float(s.idle_rpm),
        float(s.idle_rpm + s.idle_pocket_width / 2),
        float(s.peak_torque_rpm),
        float(s.redline_rpm),
        float(s.redline_rpm + 1000),
    }
    for x in axis:
        if x in specified or any(abs(x - s) < 1 for s in specified):
            continue
        assert x % 50 == 0, f"filler {x} not on a 50 RPM step"
