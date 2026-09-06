from igngen.axes import example_axes_for_docs, generate_rpm_axis
from igngen.model import EngineSpec
from igngen.preset_ini import find_preset_ini


def test_rpm_8_keeps_core_landmarks():
    spec = EngineSpec()
    axis = generate_rpm_axis(spec, 8)
    assert len(axis) == 8
    assert axis == sorted(axis)
    assert any(abs(x - 1100) < 1 for x in axis)
    assert any(abs(x - 4800) < 1 for x in axis)
    assert any(abs(x - 9300) < 1 for x in axis)


def test_rpm_16_dense_on_mech_ramp_not_flat_hold():
    """Mechanical layer: more columns on idle→peak torque than on the 32° hold."""
    spec = EngineSpec(idle_rpm=1100, peak_torque_rpm=4800, redline_rpm=9300)
    axis = generate_rpm_axis(spec, 16)
    assert len(axis) == 16
    ramp = [x for x in axis if 1100 < x < 4800]
    post = [x for x in axis if x > 4800]
    # Ramp should get real resolution; post-peak must not own half the table
    assert len(ramp) >= 4
    assert len(post) <= 6


def test_rpm_12_has_ramp_resolution():
    spec = EngineSpec()
    a12 = generate_rpm_axis(spec, 12)
    ramp = [x for x in a12 if 1100 < x < 4800]
    assert len(ramp) >= 3


def test_example_axes_for_docs():
    examples = example_axes_for_docs()
    assert len(examples["rpm_8"]) == 8
    assert len(examples["rpm_12"]) == 12
    assert len(examples["rpm_16"]) == 16


def test_alpha_ini_exists():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    ini = find_preset_ini("alpha", search_dirs=[repo / "presets"])
    assert ini is not None
    assert ini.layout == "alpha"
    assert ini.export == "alpha"
    assert ini.origin == "top_left"
