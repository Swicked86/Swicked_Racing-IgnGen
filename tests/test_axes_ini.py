from igngen.axes import _pocket_edges, describe_rpm_axis, example_axes_for_docs, generate_rpm_axis
from igngen.model import EngineSpec, mechanical_advance
from igngen.preset_ini import find_preset_ini


def test_rpm_8_keeps_core_landmarks():
    spec = EngineSpec()
    axis = generate_rpm_axis(spec, 8)
    assert len(axis) == 8
    assert axis == sorted(axis)
    assert any(abs(x - 1100) < 1 for x in axis)
    assert any(abs(x - 4800) < 1 for x in axis)


def test_rpm_axis_includes_idle_pocket_edges():
    spec = EngineSpec(idle_rpm=1100, idle_pocket_width=250, peak_torque_rpm=4800)
    axis = generate_rpm_axis(spec, 16)
    pocket_lo, pocket_hi = _pocket_edges(spec)
    assert any(abs(x - pocket_lo) < 1 for x in axis)
    assert any(abs(x - 1100) < 1 for x in axis)
    assert any(abs(x - pocket_hi) < 1 for x in axis)
    # pocket lower is below idle, upper above
    assert pocket_lo < 1100 < pocket_hi


def test_rpm_16_two_to_one_zone_budget():
    spec = EngineSpec(idle_rpm=1100, idle_pocket_width=250, peak_torque_rpm=4800, redline_rpm=9300)
    axis = generate_rpm_axis(spec, 16)
    assert len(axis) == 16
    _, pocket_hi = _pocket_edges(spec)
    climb = [x for x in axis if pocket_hi < x <= 4800]
    after = [x for x in axis if x > 4800]
    assert len(climb) >= 2 * len(after) - 1
    assert len(after) <= 5


def test_mech_advances_linearly_from_idle():
    spec = EngineSpec(base_timing=10, mech_timing_at_peak_torque=32, idle_rpm=1100, peak_torque_rpm=4800)
    assert mechanical_advance(1100, spec) == 10
    mid = mechanical_advance(2950, spec)
    assert abs(mid - 21.0) < 0.6
    assert mechanical_advance(4800, spec) == 32


def test_example_axes_for_docs():
    examples = example_axes_for_docs()
    assert len(examples["rpm_16"]) == 16
    text = describe_rpm_axis(EngineSpec(), examples["rpm_16"])
    assert "idle pocket" in text
    assert "2:1" in text


def test_alpha_ini_exists():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    ini = find_preset_ini("alpha", search_dirs=[repo / "presets"])
    assert ini is not None
