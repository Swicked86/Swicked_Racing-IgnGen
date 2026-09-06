from igngen.axes import example_axes_for_docs, generate_rpm_axis
from igngen.model import EngineSpec
from igngen.preset_ini import find_preset_ini


def test_rpm_8_keeps_core_landmarks():
    spec = EngineSpec()
    axis = generate_rpm_axis(spec, 8)
    assert len(axis) == 8
    assert axis == sorted(axis)
    # idle, peak torque, redline, overspeed should survive on 8
    assert any(abs(x - 1100) < 1 for x in axis)
    assert any(abs(x - 4800) < 1 for x in axis)
    assert any(abs(x - 9300) < 1 for x in axis)


def test_rpm_12_denser_than_8():
    spec = EngineSpec()
    a8 = generate_rpm_axis(spec, 8)
    a12 = generate_rpm_axis(spec, 12)
    assert len(a12) == 12
    # more points in/near idle band on 12
    idle_band_8 = sum(1 for x in a8 if 700 <= x <= 1500)
    idle_band_12 = sum(1 for x in a12 if 700 <= x <= 1500)
    assert idle_band_12 >= idle_band_8


def test_example_axes_for_docs():
    examples = example_axes_for_docs()
    assert len(examples["rpm_8"]) == 8
    assert len(examples["rpm_12"]) == 12


def test_alpha_ini_exists():
    ini = find_preset_ini("alpha", search_dirs=[])
    # may be None if not installed from repo root; at least parse works when path given
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    ini = find_preset_ini("alpha", search_dirs=[repo / "presets"])
    assert ini is not None
    assert ini.layout == "alpha"
    assert ini.export == "alpha"
    assert ini.origin == "top_left"
