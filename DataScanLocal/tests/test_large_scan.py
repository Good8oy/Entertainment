"""Regression for the 100,000-candidate failure reported from the first release."""
from random import Random

from datascan.engine import scan
from datascan.model import Settings, Sheet


def large_sheet(rows=26_000):
    random = Random(196)
    data = [["Signal A", "Signal B"]]
    data += [[round(random.uniform(1, 1000), 4), round(random.uniform(1, 1000), 4)]
             for _ in range(rows)]
    # Only this fragment is repeated, and its destination is at the very end of the sheet.
    for i in range(6):
        data[-6 + i][1] = data[1 + i][0]
    return Sheet("large", "large.xlsx", "Data", data)


def test_more_than_100k_windows_complete_and_find_last_rows():
    sheet = large_sheet()
    result = scan([sheet])
    assert result.statistics["indexed_windows"] > 100_000
    assert result.complete
    assert any(e.rule == "duplicate" and
               any(r.cells[-1] == (len(sheet.rows), 2) for r in e.regions)
               for e in result.evidence)
    assert not any("部分核验" in note for note in result.warnings)


def test_small_transactions_do_not_drop_cross_batch_matches():
    sheet = large_sheet(rows=80)
    result = scan([sheet], Settings(index_batch_size=3))
    assert result.complete
    assert result.statistics["indexed_windows"] > 3
    assert any(e.rule == "duplicate" and
               any(r.cells[-1] == (len(sheet.rows), 2) for r in e.regions)
               for e in result.evidence)


def test_more_than_100k_blocks_complete_and_find_last_block():
    random = Random(311)
    data = [[f"Signal {i}" for i in range(5)]]
    data += [[round(random.uniform(1, 1000), 4) for _ in range(5)] for _ in range(35_000)]
    for offset in (0, 1):
        data[-2 + offset][2:5] = data[1 + offset][:3]
    sheet = Sheet("blocks", "blocks.xlsx", "Data", data)
    result = scan([sheet], Settings(rules=["block"]))
    assert result.statistics["indexed_blocks"] > 100_000
    assert result.complete
    assert any(e.rule == "block" and
               any(r.cells[-1] == (len(data), 5) for r in e.regions)
               for e in result.evidence)
