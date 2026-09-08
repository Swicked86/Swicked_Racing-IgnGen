from pathlib import Path

from igngen.generate import generate_baseline
from igngen.io_files import load_csv, save_csv, save_json, load_json
from igngen.table import parse_range


def test_generate_shape():
    table = generate_baseline(
        parse_range("1000:3000:1000"),
        parse_range("20:100:40"),
        idle=10,
        cruise=25,
        wot=15,
    )
    assert table.shape == (3, 3)
    # Light load should be nearer idle than WOT at low RPM
    assert table.values[0][0] < table.values[0][1]


def test_csv_roundtrip(tmp_path: Path):
    table = generate_baseline([1000.0, 2000.0], [40.0, 80.0])
    path = tmp_path / "t.csv"
    save_csv(table, path)
    loaded = load_csv(path)
    assert loaded.rpm == table.rpm
    assert loaded.load == table.load
    assert loaded.values == table.values


def test_json_roundtrip(tmp_path: Path):
    table = generate_baseline([1000.0], [50.0, 100.0])
    path = tmp_path / "t.json"
    save_json(table, path)
    loaded = load_json(path)
    assert loaded.values == table.values
