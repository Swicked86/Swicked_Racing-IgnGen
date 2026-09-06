import pytest

from igngen.table import TimingTable, parse_range


def test_parse_range_inclusive():
    assert parse_range("500:1500:500") == [500.0, 1000.0, 1500.0]


def test_parse_range_rejects_bad_step():
    with pytest.raises(ValueError):
        parse_range("1:10:0")


def test_bump_and_clamp():
    table = TimingTable(
        rpm=[1000.0, 2000.0],
        load=[50.0, 100.0],
        values=[[10.0, 12.0], [14.0, 16.0]],
    )
    bumped = table.bump(2.0)
    assert bumped.values[0][0] == 12.0
    clamped = bumped.clamp(11.0, 15.0)
    assert clamped.values[0][0] == 12.0
    assert clamped.values[1][1] == 15.0
