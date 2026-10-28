"""Bounded, deterministic screening rules. No network, AI model, or hidden scoring."""
from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from math import isclose, isfinite
from time import perf_counter

from .loader import numeric
from .index import CandidateIndex
from .model import Evidence, Region, ScanResult, Settings, Sheet

RULE_NAMES = {
    "duplicate": "完全重复与连续片段", "reordered": "错位、稀疏与重排",
    "decimal": "整数改写与小数尾一致", "affine": "固定差值、比例与线性派生",
    "cycle": "差值循环复用", "replicate": "Replicate 机械关系",
    "block": "矩形块与多组位置复用", "quality": "末位数字与精度分布",
}
PARAMETERS = {"time", "timepoint", "dose", "concentration", "index", "id", "no",
              "wavelength", "frequency", "temperature", "时间", "浓度", "剂量", "序号",
              "编号", "波长", "频率", "温度", "sampleid"}


def is_parameter(label: str) -> bool:
    import re
    normalized = re.sub(r"[\s_\-]", "", label.lower().strip())
    head = re.split(r"[（(\[/]", normalized)[0]
    return head in PARAMETERS


def informative(values) -> bool:
    return len(set(values)) >= min(4, len(values))


def same(a: float, b: float, tolerance: float) -> bool:
    return isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def disjoint(a: Region, b: Region) -> bool:
    return a.sheet != b.sheet or set(a.cells).isdisjoint(b.cells)


def affine(a, b, tolerance):
    index = next((i for i in range(1, len(a)) if a[i] != a[0]), None)
    if index is None:
        return None
    slope = (b[index] - b[0]) / (a[index] - a[0])
    intercept = b[0] - slope * a[0]
    if not isfinite(slope) or not isfinite(intercept) or abs(slope) < 1e-12:
        return None
    if all(same(slope * x + intercept, y, tolerance) for x, y in zip(a, b)):
        return slope, intercept
    return None


def affine_signature(values):
    delta = next((v - values[0] for v in values[1:] if v != values[0]), 0)
    if not delta or not isfinite(delta):
        return None
    normalized = tuple((v - values[0]) / delta for v in values)
    return tuple(round(v, 8) for v in normalized) if all(map(isfinite, normalized)) else None


def fractional_signature(values):
    result = []
    try:
        for value in values:
            d = Decimal(str(abs(value)))
            if d.as_tuple().exponent > -3:
                return None
            result.append(str((d % 1).normalize()))
    except InvalidOperation:
        return None
    return tuple(result)


def _series(sheet, settings):
    # Split at blank, text, boolean, date and formula cells; never bridge a gap.
    result = []
    for vertical in (True, False):
        outer = sheet.width if vertical else len(sheet.rows)
        inner = len(sheet.rows) if vertical else sheet.width
        for line in range(1, outer + 1):
            cells, values, label = [], [], ""
            for pos in range(1, inner + 2):
                row, col = (pos, line) if vertical else (line, pos)
                raw = sheet.value(row, col)
                value = numeric(raw)
                if value is not None:
                    cells.append((row, col))
                    values.append(value)
                else:
                    if len(values) >= 3 and not (settings.filter_parameters and is_parameter(label)):
                        result.append(Region(sheet.key, tuple(cells), tuple(values), label))
                    cells, values = [], []
                    label = str(raw or "")
    return result


class EvidenceLimit(Exception):
    pass


def scan(sheets: list[Sheet], settings: Settings | None = None,
         progress=lambda percent, message: None, cancelled=lambda: False) -> ScanResult:
    settings = settings or Settings()
    with CandidateIndex(settings.index_batch_size, cancelled) as index:
        return _scan(sheets, settings, progress, cancelled, index)


def _scan(sheets, settings, progress, cancelled, index):
    if not 4 <= settings.window <= 20:
        raise ValueError("连续片段长度必须在 4–20 之间。")
    if not sheets:
        raise ValueError("请至少选择一个工作表。")
    start = perf_counter()
    notes = [f"{s.filename} / {w}" for s in sheets for w in s.warnings]
    evidence: list[Evidence] = []
    containment_cache = {}
    all_series = []
    block_count = 0

    def check():
        if cancelled():
            raise InterruptedError("已取消核验；未生成部分结果。")

    def add(rule, title, level, description, relation, regions, details=None):
        # Suppress contained sliding-window hits with the same relationship.
        regions = list(dict.fromkeys(regions))
        if not regions:
            return
        for previous in evidence:
            if previous.rule != rule or previous.relation != relation:
                continue
            def contains(p, r):
                key = id(p)
                if key not in containment_cache:
                    containment_cache[key] = frozenset(p.cells)
                return set(r.cells) <= containment_cache[key]
            if all(any(r.sheet == p.sheet and contains(p, r)
                       for p in previous.regions) for r in regions):
                return
            if rule in {"affine", "decimal"} and previous.regions[0] == regions[0]:
                previous.regions = list(dict.fromkeys([*previous.regions, *regions[1:]]))
                if details and "max_residual" in details:
                    previous.details["max_residual"] = max(previous.details.get("max_residual", 0), details["max_residual"])
                return
        if len(evidence) >= settings.max_evidence:
            raise EvidenceLimit
        evidence.append(Evidence(f"DS-{len(evidence) + 1:04d}", rule, title, level,
                                 description, relation, regions, details or {}))

    progress(1, "读取工作表数值区域")
    window_rules = set(settings.rules) & {"duplicate", "reordered", "decimal", "affine"}
    if window_rules or set(settings.rules) & {"replicate", "cycle"}:
        for sheet in sheets:
            check()
            all_series.extend(_series(sheet, settings))
    w = settings.window
    # Only numeric series stay in memory. Sliding candidates are compact references on disk.
    # No per-window Region, coordinate tuple or value tuple is retained in a Python list.
    def references(length):
        if length < w:
            return
        yield 0, length, 1
        if length > w:
            for start in range(length - w + 1):
                yield start, start + w, 1
        if "reordered" in window_rules:
            for parity in (0, 1):
                size = (length - parity + 1) // 2
                if size >= w:
                    yield parity, length, 2
            for start in range(length - 2 * w + 2):
                # Avoid repeating the full parity slice when its length is exactly w.
                if start in (0, 1) and (length - start + 1) // 2 == w:
                    continue
                yield start, start + 2 * w - 1, 2

    if window_rules:
        for source, series in sorted(enumerate(all_series), key=lambda pair: -len(pair[1].values)):
            check()
            for start_pos, stop_pos, step in references(len(series.values)):
                values = series.values[start_pos:stop_pos:step]
                if not informative(values):
                    continue
                signatures = {}
                if window_rules & {"duplicate", "reordered"}:
                    signatures["exact"] = values
                if "reordered" in window_rules:
                    signatures["reordered"] = tuple(sorted(values))
                if "decimal" in window_rules:
                    signatures["decimal"] = fractional_signature(values)
                if "affine" in window_rules:
                    signatures["affine"] = affine_signature(values)
                index.add((source, start_pos, stop_pos, step),
                          "" if settings.cross_sheet else series.sheet, len(values), signatures)
                if index.count % 1024 == 0:
                    check()
                    progress(10, f"本地分批索引：{index.count:,} 个片段")
    progress(15, f"已建立 {index.count:,} 个片段索引")

    def materialize(reference):
        source, start_pos, stop_pos, step = reference
        series = all_series[source]
        return Region(series.sheet, series.cells[start_pos:stop_pos:step],
                      series.values[start_pos:stop_pos:step], series.label)

    @contextmanager
    def buckets(kind):
        with index.groups(kind) as groups:
            yield ((materialize(reference) for reference in group) for group in groups)

    comparisons = 0

    def compatible(a, b):
        nonlocal comparisons
        comparisons += 1
        if comparisons % 1000 == 0:
            check()
        if comparisons > 500_000:
            raise EvidenceLimit
        return disjoint(a, b) and (settings.cross_sheet or a.sheet == b.sheet)

    complete = True
    try:
        if "duplicate" in settings.rules or "reordered" in settings.rules:
            with buckets("exact") as groups:
                for group in groups:
                    accepted = []
                    for candidate in group:
                        if accepted and candidate.values != accepted[0].values:
                            continue
                        if all(compatible(candidate, previous) for previous in accepted):
                            accepted.append(candidate)
                    if len(accepted) >= 2:
                        def is_sparse(r):
                            return len(r.cells) > 1 and (
                            abs(r.cells[1][0] - r.cells[0][0]) == 2 or
                            abs(r.cells[1][1] - r.cells[0][1]) == 2)
                        dense = [r for r in accepted if not is_sparse(r)]
                        if "duplicate" in settings.rules and len(dense) >= 2:
                            add("duplicate", "完全相同的数值片段", "高风险",
                                "多个不重叠区域具有完全相同的数值顺序；请核对是否为正常共享数据或记录复用。",
                                "对应数值完全一致", dense)
                        if "reordered" in settings.rules and any(map(is_sparse, accepted)):
                            add("reordered", "隔行／隔列片段复用", "高风险",
                                "相同数值序列涉及间隔为 2 的片段；具体命中坐标保留在对照视图和报告中。",
                                "对应数值完全一致", accepted)
        progress(30, "检查错位重排与小数尾关系")
        if "reordered" in settings.rules:
            with buckets("reordered") as groups:
                for group in groups:
                    # Compare a representative with each candidate; exact copies handled above.
                    anchor = next(group)
                    ordered = sorted(anchor.values)
                    for candidate in group:
                        if (compatible(anchor, candidate) and anchor.values != candidate.values
                                and sorted(candidate.values) == ordered):
                            positions = defaultdict(list)
                            for position, value in enumerate(candidate.values):
                                positions[value].append(position)
                            mapping = [positions[value].pop(0) for value in anchor.values]
                            aligned = Region(candidate.sheet, tuple(candidate.cells[i] for i in mapping),
                                             tuple(candidate.values[i] for i in mapping), candidate.label)
                            add("reordered", "同一组数值以不同顺序出现", "高风险",
                                "区域数值的多重集合完全一致，顺序不同；对照视图已按源区域顺序重排目标坐标。",
                                "数值重排后完全一致", [anchor, aligned], {"target_permutation": mapping})
        if "decimal" in settings.rules:
            with buckets("decimal") as groups:
                for group in groups:
                    anchor = next(group)
                    signature = fractional_signature(anchor.values)
                    for candidate in group:
                        if (compatible(anchor, candidate) and candidate.values != anchor.values
                                and fractional_signature(candidate.values) == signature):
                            add("decimal", "整数部分改变，小数尾保持一致", "高风险",
                                "各对应值绝对值的小数部分（至少三位）一致。需结合量纲与处理流程复核。",
                                "abs(y) 与 abs(x) 的小数部分一致", [anchor, candidate])
        progress(48, "检查固定差值、比例与线性派生")
        if "affine" in settings.rules:
            with buckets("affine") as groups:
                for group in groups:
                    anchor = next(group)
                    for candidate in group:
                        if not compatible(anchor, candidate):
                            continue
                        relation = affine(anchor.values, candidate.values, settings.tolerance)
                        if relation is None:
                            continue
                        slope, intercept = relation
                        if same(slope, 1, settings.tolerance) and same(intercept, 0, settings.tolerance):
                            continue
                        title = "固定差值关系" if same(slope, 1, settings.tolerance) else (
                            "固定比例关系" if same(intercept, 0, settings.tolerance) else "线性派生关系")
                        display_slope = 1 if same(slope, 1, settings.tolerance) else slope
                        display_intercept = 0 if same(intercept, 0, settings.tolerance) else intercept
                        formula = f"y = {display_slope:.10g} × x {display_intercept:+.10g}"
                        add("affine", title, "中风险", "对应数值满足同一仿射关系；归一化、校准或单位转换也可能产生此关系。",
                            formula, [anchor, candidate], {"slope": slope, "intercept": intercept,
                            "max_residual": max(abs(y - (slope * x + intercept))
                                                for x, y in zip(anchor.values, candidate.values))})
        progress(66, "检查 replicate 与差值循环")
        if "replicate" in settings.rules:
            # Require explicit replicate labels; do not infer biological replicates from arbitrary columns.
            import re
            labelled = [s for s in all_series if len(s.values) >= 3 and
                        re.search(r"rep(?:licate)?[\s_\-]*\d|重复[\s_\-]*\d", s.label, re.I)]
            for i, anchor in enumerate(labelled):
                check()
                for candidate in labelled[i + 1:]:
                    if (anchor.sheet != candidate.sheet or len(anchor.values) != len(candidate.values)
                            or not compatible(anchor, candidate)
                            or [c[0] for c in anchor.cells] != [c[0] for c in candidate.cells]):
                        continue
                    relation = affine(anchor.values, candidate.values, settings.tolerance)
                    if relation and len(set(anchor.values)) >= 3:
                        a, b = relation
                        add("replicate", "标注 replicate 的列存在机械关系", "高风险",
                            "带 replicate / rep / 重复编号的列在相同行满足固定线性关系；未计算小样本显著性。",
                            f"y = {a:.10g} × x {b:+.10g}", [anchor, candidate],
                            {"slope": a, "intercept": b, "samples": len(anchor.values)})
        if "cycle" in settings.rules:
            for region in all_series:
                check()
                diffs = [b - a for a, b in zip(region.values, region.values[1:])]
                if not all(map(isfinite, diffs)):
                    continue
                for period in range(2, min(7, len(diffs) // 3 + 1)):
                    base = diffs[:period]
                    if len(set(round(v, 8) for v in base)) < 2:
                        continue
                    if all(same(v, base[i % period], settings.tolerance) for i, v in enumerate(diffs)):
                        add("cycle", "差值序列按固定周期循环", "中风险",
                            "整个连续数值区域的相邻差值重复至少三个周期；周期性实验设计也可能产生此关系。",
                            f"差值周期 = {period}，完整循环 {len(diffs) // period} 次", [region],
                            {"period": period, "difference_sequence": base})
                        break
        progress(80, "检查矩形块与数字分布")
        if "block" in settings.rules:
            with CandidateIndex(settings.index_batch_size, cancelled) as blocks:
                for source, sheet in enumerate(sheets):
                    width = sheet.width
                    for row in range(1, len(sheet.rows)):
                        check()
                        for col in range(1, width - 1):
                            cells = tuple((r, c) for r in (row, row + 1) for c in range(col, col + 3))
                            values = tuple(numeric(sheet.value(*cell)) for cell in cells)
                            if None in values or not informative(values):
                                continue
                            if settings.filter_parameters and any(is_parameter(str(sheet.value(1, c) or ""))
                                                                  for c in range(col, col + 3)):
                                continue
                            blocks.add((source, row, col, 0), "" if settings.cross_sheet else sheet.key,
                                       6, {"exact": values})
                            if blocks.count % 1024 == 0:
                                progress(82, f"本地分批索引：{blocks.count:,} 个矩形")
                block_count = blocks.count
                with blocks.groups("exact") as groups:
                    for group in groups:
                        accepted = []
                        for source, row, col, _ in group:
                            sheet = sheets[source]
                            cells = tuple((r, c) for r in (row, row + 1) for c in range(col, col + 3))
                            region = Region(sheet.key, cells, tuple(numeric(sheet.value(*cell)) for cell in cells), "2 × 3 矩形")
                            if accepted and region.values != accepted[0].values:
                                continue
                            if all(compatible(region, r) for r in accepted):
                                accepted.append(region)
                        if len(accepted) > 1:
                            add("block", "2 × 3 矩形区域重复", "高风险",
                                "多个不重叠的 2 行 × 3 列矩形块包含相同的数值排列。",
                                "矩形中相同位置的数值完全一致", accepted, {"shape": [2, 3]})
        if "quality" in settings.rules:
            for sheet in sheets:
                check()
                cells, values, precisions = [], [], []
                for row, record in enumerate(sheet.rows, 1):
                    for col, raw in enumerate(record, 1):
                        if settings.filter_parameters and (is_parameter(str(sheet.value(1, col) or "")) or
                                                           is_parameter(str(sheet.value(row, 1) or ""))):
                            continue
                        value = numeric(raw)
                        if value is None or value == int(value):
                            continue
                        text = format(Decimal(str(abs(value))), "f").rstrip("0")
                        if "." in text:
                            precisions.append(len(text.split(".")[1]))
                            cells.append((row, col))
                            values.append(value)
                if len(values) >= 50:
                    # A shared precision keeps zero possible despite float trailing-zero stripping.
                    precision = min(12, Counter(precisions).most_common(1)[0][0])
                    digits = [int(f"{abs(v):.{precision}f}"[-1]) for v in values]
                    counts = Counter(digits)
                    expected = len(digits) / 10
                    chi = sum((counts[d] - expected) ** 2 / expected for d in range(10))
                    if chi > 27.88:
                        # Store all inspected coordinates so source highlighting remains traceable.
                        add("quality", "小数末位分布偏离均匀分布", "质量提示",
                            "数值先按本表最常见的存储小数位数统一舍入（最多 12 位），再以十个末位数字等概率为探索性基线；仪器精度、舍入会影响结果，不据此判断造假。",
                            f"统一 {precision} 位小数；末位 χ² = {chi:.2f}；非整数样本 {len(digits)} 个",
                            [Region(sheet.key, tuple(cells), tuple(values), "非整数值")],
                            {"digit_counts": {str(d): counts[d] for d in range(10)},
                             "precision_counts": dict(Counter(precisions)), "chi_square": chi,
                             "reference_precision": precision})
    except EvidenceLimit:
        complete = False
        notes.append(f"达到 {settings.max_evidence:,} 条证据或 500,000 次关系比较的保护上限；"
                     "这是部分核验结果，请缩小范围后重新核验。")
    check()
    progress(100, f"完成：{len(evidence)} 条待复核线索")
    notes.append("数值文本按浮点数比较；公式不计算，日期与布尔值不参与。数字精度来自存储值，不代表仪器精度。")
    notes.append("错位核验限连续片段、间隔为 2 的片段及窗口内重排；矩形核验限 2 × 3。近似线性与其他稀疏间距未覆盖。")
    return ScanResult(settings, sheets, evidence, list(dict.fromkeys(notes)), perf_counter() - start,
                      complete=complete, statistics={"indexed_windows": index.count,
                      "indexed_blocks": block_count,
                      "candidate_storage": "local_sqlite", "index_batch_size": settings.index_batch_size})
