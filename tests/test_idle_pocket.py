from igngen.calibration import EngineParameters, timing_at


def test_idle_pocket_adds_timing_below_target_and_removes_it_above_target():
    spec = EngineParameters(
        idle_rpm=1000,
        idle_pocket_width=200,
        idle_pocket_lower_share=0.5,
        idle_pocket_upper_share=0.5,
        idle_timing_target=10,
        idle_timing_delta=6,
        idle_map_lo=30,
        idle_map_hi=45,
    )

    assert spec.idle_pocket_lo_rpm == 900
    assert spec.idle_pocket_hi_rpm == 1100
    assert timing_at(900, 40, spec) == 16
    assert timing_at(1000, 40, spec) == 10
    assert timing_at(1100, 40, spec) == 4
