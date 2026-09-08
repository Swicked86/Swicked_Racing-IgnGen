from pathlib import Path

from igngen.engines import find_engine


def test_4age_engine_loads():
    repo = Path(__file__).resolve().parents[1]
    v = find_engine("4age", search_dirs=[repo / "engines"])
    assert v is not None
    assert v.name == "4AGE"
    s = v.spec
    assert s.displacement_cc == 1600
    assert s.peak_hp == 280
    assert s.peak_hp_rpm == 7800
    assert s.peak_torque_lbft == 189
    assert s.peak_torque_rpm == 4800
    assert s.redline_rpm == 9300
    assert s.boost_psi == 12
    assert s.idle_rpm == 1100
    assert s.idle_pocket_width == 100
    assert s.base_timing == 10
    assert s.mech_timing_at_peak_torque == 36
