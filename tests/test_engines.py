from pathlib import Path

from igngen.axes import (
    _max_load_kpa,
    _overboost_from_logical,
    _overboost_kpa,
    _snap_to_logical,
    generate_load_axis,
    generate_rpm_axis,
)
from igngen.model import EngineSpec
from igngen.engines import find_engine, load_engine


def test_d16z6_engine_loads():
    repo = Path(__file__).resolve().parents[1]
    v = find_engine("D16Z6", search_dirs=[repo / "engines"])
    assert v is not None
    assert v.name == "D16Z6"
    s = v.spec
    assert s.peak_hp == 125
    assert s.peak_hp_rpm == 6600
    assert s.peak_torque_lbft == 106
    assert s.peak_torque_rpm == 5200
    assert s.redline_rpm == 7200
    assert s.idle_rpm == 670
    assert s.idle_pocket_width == 50
    assert s.base_timing == 16
    assert s.mech_timing_at_peak_torque == 34
    assert s.boost_psi == 0.0


def test_d16z6_rpm_axis_hits_idle_pocket_and_peaks():
    repo = Path(__file__).resolve().parents[1]
    v = load_engine(repo / "engines" / "d16z6.ini")
    axis = generate_rpm_axis(v.spec, 16)
    assert len(axis) == 16
    assert any(abs(x - 500) < 1 for x in axis)  # cranking
    assert any(abs(x - 620) < 1 for x in axis)
    assert any(abs(x - 670) < 1 for x in axis)
    assert any(abs(x - 720) < 1 for x in axis)
    assert any(abs(x - 5200) < 1 for x in axis)
    assert any(abs(x - 7200) < 1 for x in axis)
    assert max(axis) >= 8000


def test_d16z6_fillers_are_multiples_of_50():
    repo = Path(__file__).resolve().parents[1]
    v = load_engine(repo / "engines" / "d16z6.ini")
    s = v.spec
    axis = generate_rpm_axis(s, 16)
    specified = {
        float(s.cranking_rpm),
        float(s.idle_rpm - s.idle_pocket_width),
        float(s.idle_rpm),
        float(s.idle_rpm + s.idle_pocket_width),
        float(s.peak_torque_rpm),
        float(s.redline_rpm),
        float(s.redline_rpm + 1000),
    }
    for x in axis:
        if x in specified or any(abs(x - s) < 1 for s in specified):
            continue
        assert x % 50 == 0, f"filler {x} not on a 50 RPM step"


def test_logical_overboost_is_one_step_past_how_max_reads():
    # ladder 100,120,...,200 — not "max + 20"
    rounds = [100.0, 120.0, 140.0, 160.0, 180.0, 200.0, 220.0]
    assert _snap_to_logical(172.0, rounds) == 180.0
    assert _overboost_from_logical(172.0, rounds) == 200.0
    assert _snap_to_logical(165.0, rounds) == 160.0
    assert _overboost_from_logical(165.0, rounds) == 180.0


def test_overboost_follows_profile_max_not_profile_name():
    s = EngineSpec(boost_psi=10.4)  # ~172 kPa → reads 180 → overboost 200
    assert _overboost_kpa(s) == 200.0
    s2 = EngineSpec(boost_psi=7.0)  # ~148 → reads 140 or 160?
    # mid(140,160)=150; 148 < 150 → snap 140 → overboost 160
    assert _overboost_kpa(s2) == 160.0


def test_d16z6_load_axis_na_plus_one_overboost():
    """NA (boost_psi=0): max=atm, one overboost tip; densifies below for any size."""
    repo = Path(__file__).resolve().parents[1]
    v = load_engine(repo / "engines" / "d16z6.ini")
    assert v.spec.boost_psi == 0.0
    max_map = _max_load_kpa(v.spec)
    over = _overboost_kpa(v.spec)
    assert abs(max_map - 100.0) < 1e-6
    assert over == 120.0
    for count in (12, 24):
        load = generate_load_axis(v.spec, count, unit="kPa")
        assert len(load) == count
        above = [x for x in load if x > 100 + 1e-9]
        assert above == [120.0], above
        assert 100 in load or any(abs(x - 100) < 1 for x in load)
