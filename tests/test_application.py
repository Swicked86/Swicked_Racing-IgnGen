from igngen.calibration import (
    EngineParameters,
    boost_map_fraction,
    build_table,
    generate_load_axis,
    generate_rpm_axis,
    load_engine_profile,
    mechanical_timing,
    timing_at,
    validate_recurve,
)


def test_application_loads_boost_gain_from_engine_profile():
    spec = load_engine_profile("d16z6")
    assert spec.boost_retard_gain == 0.6
    assert spec.boost_timing_limit == 20


def test_default_recurve_points_preserve_linear_mechanical_curve():
    spec = EngineParameters(
        idle_rpm=1000,
        peak_torque_rpm=5000,
        base_timing=10,
        mech_timing_at_peak_torque=34,
    )
    validate_recurve(spec)
    assert spec.recurve_points == ((2000.0, 16.0), (3000.0, 22.0), (4000.0, 28.0))
    assert mechanical_timing(2000, spec) == 16
    assert mechanical_timing(3000, spec) == 22
    assert mechanical_timing(4000, spec) == 28


def test_4age_profile_uses_front_loaded_recurve_points():
    spec = load_engine_profile("4age")
    assert spec.recurve_points == ((1750.0, 17.0), (2400.0, 23.0), (3500.0, 31.0))
    assert mechanical_timing(1750, spec) == 17
    assert mechanical_timing(2400, spec) == 23
    assert mechanical_timing(3500, spec) == 31
    assert mechanical_timing(spec.peak_torque_rpm, spec) == 36


def test_recurve_can_front_load_or_taper_without_missing_control_points():
    spec = EngineParameters(
        idle_rpm=1000,
        peak_torque_rpm=5000,
        base_timing=10,
        mech_timing_at_peak_torque=34,
        recurve_rpm_1=1800,
        recurve_timing_1=22,
        recurve_rpm_2=2800,
        recurve_timing_2=30,
        recurve_rpm_3=4000,
        recurve_timing_3=28,
    )
    validate_recurve(spec)
    assert mechanical_timing(1800, spec) == 22
    assert mechanical_timing(2800, spec) == 30
    assert mechanical_timing(4000, spec) == 28
    assert mechanical_timing(5000, spec) == 34


def test_recurve_can_start_at_idle_without_overwriting_idle_pocket():
    spec = EngineParameters(
        idle_rpm=1100,
        peak_torque_rpm=4800,
        base_timing=10,
        mech_timing_at_peak_torque=36,
        recurve_rpm_1=1100,
        recurve_timing_1=18,
        recurve_rpm_2=2400,
        recurve_timing_2=25,
        recurve_rpm_3=3500,
        recurve_timing_3=32,
        idle_map_lo=30,
        idle_map_hi=45,
        idle_timing_target=10,
        idle_timing_delta=6,
    )
    validate_recurve(spec)
    assert mechanical_timing(1100, spec) == 18
    # Outside the protected MAP band, the recurve is active immediately at idle RPM.
    assert timing_at(1100, 50, spec) == 18
    assert timing_at(1100, 100, spec) == 18
    # Inside the protected idle pocket, the special idle target still wins.
    assert timing_at(1100, 45, spec) == 10
    assert timing_at(1100, 38, spec) == 10


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


def test_application_generated_axes_keep_atmosphere_idle_and_recurve_structure():
    spec = load_engine_profile("4age").with_overrides(
        boost_psi=25,
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
    assert all(point_rpm in rpm for point_rpm, _ in spec.recurve_points)
    assert len(rpm) == 20
    assert len(load) == 16


def test_application_build_table_uses_canonical_timing():
    spec = load_engine_profile("4age").with_overrides(boost_psi=25)
    rpm = [spec.peak_torque_rpm]
    load = [100, 150, 200]
    table = build_table(rpm, load, spec)
    assert table.values[0] == [36.0, 28.0, 20.0]
