from igngen.model import EngineSpec, generate_table, timing_at, validate_power
from igngen.presets import get_preset
from igngen.units import inhg_gauge_to_kpa_abs


def test_alpha_preset_shape():
    preset = get_preset("alpha")
    assert preset.name == "alpha"
    assert len(preset.rpm) == 20
    assert len(preset.load) == 16
    assert preset.load_unit == "inHg"
    assert get_preset("alphalink-high-cam").name == "alpha"


def test_research_model_non_negative_whole_degrees():
    preset = get_preset("alpha")
    table = generate_table(
        list(preset.rpm), list(preset.load), load_unit="inhg", layers="mechanical"
    )
    assert table.shape == (20, 16)
    assert table.load_unit == "inHg"
    for row in table.values:
        for cell in row:
            assert float(cell).is_integer()
            assert cell >= 0


def test_atmosphere_matches_mechanical_at_peak_torque():
    spec = EngineSpec()
    atm_timing = timing_at(
        4800, inhg_gauge_to_kpa_abs(0.0), spec, layers="mechanical"
    )
    assert atm_timing == 32


def test_power_validation_catches_inconsistent_peak_torque():
    spec = EngineSpec(peak_hp=280, peak_hp_rpm=7800, peak_torque_lbft=150, peak_torque_rpm=4800)
    assert validate_power(spec)
