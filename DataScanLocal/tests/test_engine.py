from collections import Counter
from datetime import datetime

import pytest

from datascan.engine import scan
from datascan.loader import numeric
from datascan.model import Settings, Sheet

V = [12.3847, 18.9263, 15.4718, 24.6392, 20.8174, 31.2569, 27.5931, 35.7486]


def sheet(key, values, header="Signal"):
    return Sheet(key, f"{key}.xlsx", key, [[header]] + [[v] for v in values])


def run(rule, a, b=None, **kwargs):
    sheets = [sheet("A", a)] + ([sheet("B", b)] if b is not None else [])
    return scan(sheets, Settings(rules=[rule], **kwargs))


def test_duplicate_grouped_and_full_coordinates():
    result = scan([sheet("A", V), sheet("B", V), sheet("C", V)], Settings(rules=["duplicate"]))
    assert len(result.evidence) == 1
    hit = result.evidence[0]
    assert len(hit.regions) == 3
    assert hit.regions[0].cells == tuple((i, 1) for i in range(2, 10))
    assert hit.regions[0].values == tuple(V)


def test_continuous_partial_match():
    result = run("duplicate", [1.37, *V[:6], 3.98], [7.452, *V[:6], 5.18])
    assert result.evidence
    assert any(r.cells[0] == (3, 1) for r in result.evidence[0].regions)


def test_sparse_coordinates_preserved():
    target = [v for pair in zip(V, [79.031 + i * .173 for i in range(len(V))]) for v in pair]
    result = run("reordered", V, target)
    hit = next(e for e in result.evidence if "隔行" in e.title)
    sparse = next(r for r in hit.regions if r.sheet == "B")
    assert sparse.cells == tuple((i, 1) for i in range(2, 18, 2))


def test_permutation_is_aligned_to_actual_target_coordinates():
    order = [3, 1, 6, 0, 7, 2, 5, 4]
    target = [V[i] for i in order]
    result = run("reordered", V, target)
    hit = next(e for e in result.evidence if "顺序" in e.title)
    a, b = hit.regions
    assert a.values == b.values
    for cell, value in zip(b.cells, b.values):
        assert target[cell[0] - 2] == value


def test_decimal_tail_and_integer_changes():
    target = [round(v + (i + 1) * 10, 4) for i, v in enumerate(V)]
    result = run("decimal", V, target)
    assert len(result.evidence) == 1
    assert result.evidence[0].regions[1].values == tuple(target)
    assert not run("decimal", [1.2, 3.4, 5.6, 7.8, 9.9, 2.3],
                   [11.2, 13.4, 15.6, 17.8, 19.9, 12.3]).evidence


@pytest.mark.parametrize("a,b,title", [(1, .25, "固定差值"), (2.5, 0, "固定比例"), (1.7, 3.142, "线性派生")])
def test_affine_formula_and_residual(a, b, title):
    target = [a * v + b for v in V]
    result = run("affine", V, target)
    hit = result.evidence[0]
    assert title in hit.title
    assert hit.details["slope"] == pytest.approx(a)
    assert hit.details["intercept"] == pytest.approx(b)
    assert hit.details["max_residual"] < 1e-8
    assert len(result.evidence) == 1


def test_no_affine_from_single_different_value():
    target = [2.5 * v for v in V]
    target[3] += 2
    assert not run("affine", V, target).evidence


def test_duplicate_does_not_count_as_affine():
    assert not run("affine", V, V).evidence


def test_cross_sheet_disabled_prevents_all_cross_sheet_matches():
    assert not run("duplicate", V, V, cross_sheet=False).evidence


def test_header_parameters_are_filtered_only_when_enabled():
    inputs = [sheet("A", V, "Time (h)"), sheet("B", V, "时间（h）")]
    assert not scan(inputs, Settings(rules=["duplicate"])).evidence
    assert scan(inputs, Settings(rules=["duplicate"], filter_parameters=False)).evidence


def test_constant_and_low_information_windows_not_flagged():
    for values in [[1] * 10, [0, 1] * 6]:
        assert not run("duplicate", values, values).evidence


def test_blank_cells_are_not_bridged():
    assert not run("duplicate", V[:4] + [None] + V[4:], V).evidence


def test_replicate_requires_label_and_reports_short_samples():
    data = Sheet("A", "a.xlsx", "数据", [["Replicate 1", "Replicate 2"],
                                        [3.124, 3.224], [6.617, 6.717], [2.873, 2.973]])
    result = scan([data], Settings(rules=["replicate"]))
    assert len(result.evidence) == 1
    assert result.evidence[0].details["samples"] == 3
    data.rows[0] = ["A", "B"]
    assert not scan([data], Settings(rules=["replicate"])).evidence


def test_difference_cycle_needs_three_complete_periods():
    values = [1.234]
    for i in range(12):
        values.append(values[-1] + [0.371, 0.823, 0.146][i % 3])
    result = run("cycle", values)
    assert result.evidence[0].details["period"] == 3
    assert not run("cycle", values[:8]).evidence


def test_block_shape_and_coordinates():
    grid = [[3.172, 8.463, 4.291], [9.537, 2.684, 7.815]]
    inputs = [Sheet("A", "a.csv", "A", grid), Sheet("B", "b.csv", "B", grid)]
    result = scan(inputs, Settings(rules=["block"]))
    assert len(result.evidence) == 1
    assert result.evidence[0].details["shape"] == [2, 3]
    assert len(result.evidence[0].regions[0].cells) == 6


def test_digit_distribution_is_quality_only_with_minimum_sample():
    values = [i + 0.121 for i in range(60)]
    result = run("quality", values)
    assert result.evidence[0].level == "质量提示"
    assert result.evidence[0].details["digit_counts"]["1"] == 60
    assert not run("quality", values[:49]).evidence


def test_balanced_digits_include_zero_at_shared_precision():
    values = [i + (120 + digit) / 1000 for i in range(10) for digit in range(10)]
    assert not run("quality", values).evidence


def test_evidence_limit_is_explicitly_incomplete():
    result = scan([sheet("A", V), sheet("B", V)], Settings(max_evidence=0))
    assert result.complete is False
    assert any("部分核验" in w for w in result.warnings)


def test_index_batch_size_is_not_a_candidate_limit():
    result = run("duplicate", V, V, index_batch_size=1)
    assert result.complete
    assert result.statistics["indexed_windows"] > 1
    assert len(result.evidence) == 1


def test_only_quality_rule_does_not_build_unrelated_windows():
    result = run("quality", V)
    assert result.statistics["indexed_windows"] == 0


def test_block_scan_is_not_limited_by_window_batch_size():
    grid = [[3.172, 8.463, 4.291], [9.537, 2.684, 7.815]]
    inputs = [Sheet("A", "a.csv", "A", grid), Sheet("B", "b.csv", "B", grid)]
    result = scan(inputs, Settings(rules=["block"], index_batch_size=1))
    assert result.complete
    assert result.statistics["indexed_blocks"] == 2
    assert len(result.evidence) == 1


def test_cancellation_yields_no_partial_result():
    with pytest.raises(InterruptedError):
        scan([sheet("A", V)], cancelled=lambda: True)


@pytest.mark.parametrize("value", [True, False, None, "", "NaN", "inf", float("inf"), datetime(2026, 1, 1), "=A1*2", "12 mg"])
def test_non_measurements_rejected(value):
    assert numeric(value) is None


def test_finite_numeric_text_and_scientific_notation():
    assert numeric("1.23e-4") == .000123
    assert numeric("-5.31") == -5.31


def test_demo_contains_every_rule(tmp_path):
    from datascan.demo import create_demo
    from datascan.loader import load_file
    result = scan([s for path in create_demo(tmp_path) for s in load_file(path)])
    counts = Counter(e.rule for e in result.evidence)
    assert set(counts) == set(Settings().rules)
    assert result.complete
    assert len(result.evidence) < 25
