from igngen.gui_app import ATTRIBUTION, generate_payload, load_engine_payload


def test_generate_payload_returns_host_neutral_table() -> None:
    result = generate_payload(
        {
            "engine": "d16z6",
            "boost_psi": 12,
            "boost_retard_gain": 0.60,
            "load_cells": 16,
            "rpm_cells": 20,
        }
    )

    assert result["schema"] == "igngen.table.v1"
    assert len(result["rpm"]) == 20
    assert len(result["load_kpa"]) == 16
    assert 100 in result["load_kpa"]
    assert len(result["timing"]) == 20
    assert all(len(row) == 16 for row in result["timing"])
    assert result["units"]["load"] == "kPa_abs"
    assert len(result["recurve"]) == 3
    assert result["attribution"] == ATTRIBUTION


def test_gui_engine_payload_resolves_recurve_defaults_for_editing() -> None:
    profile = load_engine_payload("d16z6")
    assert profile["recurve_rpm_1"] > profile["idle_rpm"]
    assert profile["recurve_rpm_1"] < profile["recurve_rpm_2"] < profile["recurve_rpm_3"]
    assert profile["recurve_rpm_3"] < profile["peak_torque_rpm"]


def test_gui_payload_accepts_user_recurve_points() -> None:
    result = generate_payload(
        {
            "engine": "4age",
            "recurve_rpm_1": 1800,
            "recurve_timing_1": 20,
            "recurve_rpm_2": 2400,
            "recurve_timing_2": 25,
            "recurve_rpm_3": 3500,
            "recurve_timing_3": 32,
            "load_cells": 16,
            "rpm_cells": 20,
        }
    )
    assert result["recurve"] == [
        {"rpm": 1800, "timing": 20.0},
        {"rpm": 2400, "timing": 25.0},
        {"rpm": 3500, "timing": 32.0},
    ]
    atm_index = result["load_kpa"].index(100)
    rpm_index = result["rpm"].index(2400)
    assert result["timing"][rpm_index][atm_index] == 25


def test_gui_payload_uses_absolute_boost_limit_and_gain() -> None:
    result = generate_payload(
        {
            "engine": "4age",
            "boost_psi": 25,
            "boost_timing_limit": 20,
            "boost_retard_gain": 0.60,
            "load_cells": 16,
            "rpm_cells": 20,
        }
    )

    load = result["load_kpa"]
    rpm = result["rpm"]
    peak_index = rpm.index(4800)
    full_boost_indices = [i for i, kpa in enumerate(load) if kpa >= 200]
    assert full_boost_indices
    assert all(result["timing"][peak_index][i] == 20 for i in full_boost_indices)
