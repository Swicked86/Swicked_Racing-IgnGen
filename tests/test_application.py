from igngen.calibration import (
    boost_map_fraction,
    build_table,
    generate_load_axis,
    generate_rpm_axis,
    load_engine_profile,
    timing_at,
)


def test_application_loads_boost_gain_from_engine_profile():
    spec = load_engine_profile("d16z6")
    assert spec.boost_retard_gain == 0.6
    assert spec.boost_timing_limit == 20


def test_application_boost_curve_uses_mirrored_kpa_gain():
    spec = load_engine_profile("4age").with_overrides(
        boost_psi=25,
        boost_retard_gain=0.6,
        vacuum_full_map_kpa=40,
        mech_timing_at_peak_torque=36,
        boost_timing_limit=20,
    )
    rpm = spec.peak_torque_rpm
    assert boost_map_fraction(100, spec) == 0.0
    assert boost_map_fraction(150, spec) == 0.5
    assert boost_map_fraction(200, spec) == 1.0
    assert timing_at(rpm, 100, spec) == 36
    assert timing_at(rpm, 150, spec) == 28
    assert timing_at(rpm, 200, spec) == 20
    assert timing_at(rpm, 250, spec) == 20


def test_application_generated_axes_keep_atmosphere_and_idle_structure():
    spec = load_engine_profile("4age").with_overrides(
        boost_psi=25,
        idle_rpm=900,
        idle_map_lo=35,
        idle_map_hi=65,
    )
    rpm = generate_rpm_axis(spec, 20)
    load = generate_load_axis(spec, 16)
    assert 100.0 in load
    assert len([x for x in load if x < spec.idle_map_lo]) == 1
    assert spec.idle_rpm in rpm
    assert spec.peak_torque_rpm in rpm
    assert spec.redline_rpm in rpm
    assert len(rpm) == 20
    assert len(load) == 16


def test_application_build_table_uses_canonical_timing():
    spec = load_engine_profile("4age").with_overrides(boost_psi=25)
    rpm = [spec.peak_torque_rpm]
    load = [100, 150, 200]
    table = build_table(rpm, load, spec)
    assert table.values[0] == [36.0, 28.0, 20.0]
