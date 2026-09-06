from igngen.model import EngineSpec, generate_table, validate_power
from igngen.presets import get_preset


def test_alphalink_preset_shape():
    preset = get_preset("alphalink-high-cam")
    assert len(preset.rpm) == 20
    assert len(preset.load) == 16
    assert preset.load_unit == "inHg"
    assert any(abs(x) < 5 for x in preset.load)


def test_research_model_whole_degrees():
    preset = get_preset("alphalink-high-cam")
    table = generate_table(list(preset.rpm), list(preset.load), load_unit="inhg")
    assert table.shape == (20, 16)
    for row in table.values:
        for cell in row:
            assert float(cell).is_integer()
    mid = len(preset.rpm) // 2
    assert table.values[mid][0] > table.values[mid][-1]


def test_power_validation_catches_inconsistent_peak_torque():
    spec = EngineSpec(peak_hp=280, peak_hp_rpm=7800, peak_torque_lbft=150, peak_torque_rpm=4800)
    warnings = validate_power(spec)
    assert warnings
