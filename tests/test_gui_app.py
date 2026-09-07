from igngen.gui_app import ATTRIBUTION, generate_payload


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
    assert result["attribution"] == ATTRIBUTION


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
    # At/above 200 kPa the 0.60 gain has reached the configured absolute limit.
    full_boost_indices = [i for i, kpa in enumerate(load) if kpa >= 200]
    assert full_boost_indices
    assert all(result["timing"][peak_index][i] == 20 for i in full_boost_indices)
