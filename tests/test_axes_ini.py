from igngen.axes import describe_rpm_axis, example_axes_for_docs, generate_rpm_axis
from igngen.model import EngineSpec, mechanical_advance
from igngen.preset_ini import find_preset_ini


def test_rpm_8_keeps_core_landmarks():
    spec = EngineSpec()
    axis = generate_rpm_axis(spec, 8)
    assert len(axis) == 8
    assert axis == sorted(axis)
    assert any(abs(x - 1100) < 1 for x in axis)
    assert any(abs(x - 4800) < 1 for x in axis)
    assert any(abs(x - 9300) < 1 for x in axis)


def test_rpm_16_two_to_one_dense_vs_sparse():
    """~2:1 interiors: above pocket→peak TQ vs after peak TQ."""
    spec = EngineSpec(idle_rpm=1100, idle_pocket_width=250, peak_torque_rpm=4800, redline_rpm=9300)
    axis = generate_rpm_axis(spec, 16)
    assert len(axis) == 16
    pocket_hi = 1100 + 125
    dense = [x for x in axis if pocket_hi < x < 4800]
    sparse = [x for x in axis if x > 4800]
    # denser on the climb than on the hold
    assert len(dense) >= len(sparse)
    # and roughly 2:1 when both non-empty
    if sparse:
        assert len(dense) >= int(len(sparse) * 1.5)


def test_mech_advances_immediately_past_idle():
    spec = EngineSpec(base_timing=10, mech_timing_at_peak_torque=32, idle_rpm=1100, peak_torque_rpm=4800)
    assert mechanical_advance(1100, spec) == 10
    # linear: halfway in RPM → halfway in degrees
    mid = mechanical_advance(2950, spec)
    assert abs(mid - 21.0) < 0.6
    assert mechanical_advance(4800, spec) == 32


def test_example_axes_for_docs():
    examples = example_axes_for_docs()
    assert len(examples["rpm_8"]) == 8
    assert len(examples["rpm_12"]) == 12
    assert len(examples["rpm_16"]) == 16
    spec = EngineSpec()
    assert "2:1" in describe_rpm_axis(spec, examples["rpm_16"])


def test_alpha_ini_exists():
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    ini = find_preset_ini("alpha", search_dirs=[repo / "presets"])
    assert ini is not None
    assert ini.layout == "alpha"
