from __future__ import annotations

import csv
import html
import io
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from .engine import RULE_NAMES
from .model import ScanResult, coordinate
from . import __version__


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def html_report(result: ScanResult) -> str:
    lookup = {s.key: s for s in result.sheets}
    counts = Counter(e.level for e in result.evidence)
    cards = []
    for e in result.evidence:
        rows = []
        statistics = ""
        if e.rule == "quality":
            digits = e.details.get("digit_counts", {})
            precision = e.details.get("precision_counts", {})
            statistics = "<p>统一精度末位计数：" + esc("；".join(f"{d}: {digits.get(str(d), 0)}" for d in range(10))) + "</p>"
            statistics += "<p>原存储小数位数计数：" + esc("；".join(f"{p} 位: {n}" for p, n in sorted(precision.items(), key=lambda pair: int(pair[0])))) + "</p>"
        for region in e.regions:
            sheet = lookup[region.sheet]
            values = " · ".join(f"{coordinate(*cell)} = {value:.12g}"
                                for cell, value in zip(region.cells, region.values))
            rows.append(f"<tr><td>{esc(sheet.filename)}</td><td>{esc(sheet.name)}</td>"
                        f"<td>{esc(region.address)}</td><td class='values'>{esc(values)}</td></tr>")
        cards.append(f"""<article><div class='eyebrow'>{esc(e.id)} · {esc(e.level)} · {esc(RULE_NAMES[e.rule])}</div>
<h2>{esc(e.title)}</h2><p>{esc(e.description)}</p><div class='formula'>{esc(e.relation)}</div>
<table><thead><tr><th>文件</th><th>工作表</th><th>范围</th><th>坐标与数值</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>{statistics}<p><b>复核状态：</b>{esc(e.review)}　<b>备注：</b>{esc(e.note or '未填写')}</p></article>""")
    scope = "".join(f"<tr><td>{esc(s.filename)}</td><td>{esc(s.name)}</td><td>{len(s.rows)}</td>"
                    f"<td>{s.width}</td><td class='hash'>{esc(s.source_sha256)}</td></tr>" for s in result.sheets)
    rules = "、".join(RULE_NAMES[r] for r in result.settings.rules)
    warnings = "".join(f"<li>{esc(n)}</li>" for n in result.warnings)
    status = "已完成所选规则的筛查" if result.complete else "部分核验 · 达到保护上限"
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>DataScan Local 核验报告</title>
<style>body{{margin:0;background:#f2f5fa;color:#203048;font:14px/1.7 'Microsoft YaHei',sans-serif}}
main{{max-width:1100px;margin:40px auto;padding:0 28px}}header{{border-top:5px solid #345fdf;padding:25px 0}}
h1{{font-size:30px;margin:8px 0}}h2{{font-size:20px}}.eyebrow{{font-size:12px;color:#627289;letter-spacing:1px}}
article,.panel{{background:white;border:1px solid #dce3ee;border-radius:10px;padding:24px;margin:18px 0;break-inside:avoid}}
table{{border-collapse:collapse;width:100%;table-layout:fixed;font-size:12px}}td,th{{text-align:left;padding:10px;border:1px solid #dfe5ef;overflow-wrap:anywhere}}
th{{background:#f4f7fc}}.values,.hash{{font:11px/1.6 Consolas,monospace}}.formula{{padding:12px;background:#edf2ff;font:14px Consolas,monospace;margin:16px 0}}
.stats{{display:flex;gap:30px;padding:14px 0}}.stats strong{{font-size:26px;color:#315ed5;display:block}}
.boundary{{border-left:4px solid #c28a23;padding:12px;background:#fff9ea}}@media print{{body{{background:white}}main{{margin:0;padding:0}}article,.panel{{box-shadow:none}}}}</style></head>
<body><main><header><div class='eyebrow'>DATASCAN LOCAL / SCIENTIFIC DATA REVIEW</div>
<h1>科研原始数据核验报告</h1><p>{esc(result.started)} · {result.elapsed:.2f} 秒 · {esc(status)}</p>
<div class='stats'><div><strong>{len(result.evidence)}</strong>证据记录</div><div><strong>{counts['高风险']}</strong>高风险线索</div>
<div><strong>{counts['中风险']}</strong>中风险线索</div><div><strong>{counts['质量提示']}</strong>质量提示</div></div></header>
<p class='boundary'>自动核验结果仅作为复核线索，不构成学术不端结论。未检出不代表数据真实。正常共享数据、归一化、校准和单位换算均可能产生数值关系，必须结合原始实验记录进行判断。</p>
<section class='panel'><h2>核验范围</h2><table><tr><th>文件</th><th>工作表</th><th>行数</th><th>列数</th><th>文件 SHA-256</th></tr>{scope}</table>
<p>所选规则：{esc(rules)}。</p><p>最短片段：{result.settings.window}；表头参数过滤：{'开启' if result.settings.filter_parameters else '关闭'}；
跨工作表比较：{'开启' if result.settings.cross_sheet else '关闭'}；线性相对／绝对容差：{result.settings.tolerance:g}。</p>
<p>本地分批索引：{result.statistics.get('indexed_windows', 0):,} 个片段，{result.statistics.get('indexed_blocks', 0):,} 个矩形。候选数量不作为中止条件。</p>
<p>文件哈希在导入时计算，对应内存中用于核验的文件快照。风险分级为预设规则标签，不是概率或统计置信度。</p></section>
{''.join(cards) if cards else "<section class='panel'><h2>未检出所选规则覆盖的关系</h2><p>请结合检测范围和方法边界解释结果。</p></section>"}
<section class='panel'><h2>方法与边界</h2><ul>{warnings}</ul><p>重复、重排及小数尾使用确定性数值索引；
线性候选使用归一化指纹后逐项验证。浮点候选指纹存在舍入边界，不能保证检出所有近似关系。
Replicate 规则仅检查明确含 rep / replicate / 重复编号的列；差值循环至少重复三个周期。
质量提示要求至少 50 个非整数值；按最常见的存储小数位数统一舍入（最多 12 位）后，均匀末位分布仅是探索性参考。</p>
<p>本程序为依据公开功能说明独立实现的 DataScan Local {__version__}，不代表原产品的算法、性能或结论。</p></section>
</main></body></html>"""


def csv_text(result: ScanResult) -> str:
    def safe(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
    lookup = {s.key: s for s in result.sheets}
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["证据编号", "规则", "风险", "关系", "文件", "工作表", "范围", "复核状态", "备注"])
    for e in result.evidence:
        for region in e.regions:
            sheet = lookup[region.sheet]
            writer.writerow(map(safe, [e.id, RULE_NAMES[e.rule], e.level, e.relation, sheet.filename,
                                       sheet.name, region.address, e.review, e.note]))
    return stream.getvalue()


def export_report(result: ScanResult, filename: str) -> None:
    path = Path(filename)
    if path.suffix.lower() == ".json":
        text = json.dumps(result.payload(), ensure_ascii=False, indent=2, allow_nan=False)
    elif path.suffix.lower() == ".csv":
        text = csv_text(result)
    elif path.suffix.lower() in {".html", ".htm"}:
        text = html_report(result)
    else:
        raise ValueError("请选择 HTML、JSON 或 CSV 报告。")
    # Write atomically so a failed export does not destroy a prior report.
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig" if path.suffix == ".csv" else "utf-8",
                                         dir=path.parent, delete=False, suffix=".tmp", newline="") as file:
            temp = file.name
            file.write(text)
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)
