from pathlib import Path

from igngen.vehicles import find_vehicle


def test_ae86_vehicle_loads():
    repo = Path(__file__).resolve().parents[1]
    v = find_vehicle("ae86", search_dirs=[repo / "vehicles"])
    assert v is not None
    assert v.name == "AE86"
    s = v.spec
    assert s.displacement_cc == 1600
    assert s.peak_hp == 280
    assert s.peak_hp_rpm == 7800
    assert s.peak_torque_lbft == 189
    assert s.peak_torque_rpm == 4800
    assert s.redline_rpm == 9300
    assert s.boost_psi == 7
    assert s.idle_rpm == 1100
    assert s.idle_pocket_width == 250
    assert s.base_timing == 10
    assert s.mech_timing_at_peak_torque == 32
