from __future__ import annotations

import csv
import hashlib
import math
from datetime import date, datetime, time
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from .model import Sheet

MAX_CELLS = 200_000
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_UNPACKED_BYTES = 256 * 1024 * 1024


def numeric(value) -> float | None:
    if isinstance(value, (bool, date, datetime, time)) or value is None:
        return None
    try:
        # Deliberately do not strip units or punctuation from measurements.
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def sheet_key(path: Path, name: str) -> str:
    return hashlib.sha256(f"{path.resolve()}\0{name}".encode()).hexdigest()[:20]


def _make(path: Path, name: str, rows: list, warnings=None) -> Sheet:
    if sum(map(len, rows)) > MAX_CELLS:
        raise ValueError(f"{path.name} / {name} 超过 {MAX_CELLS:,} 个单元格，请拆分文件。")
    while rows and all(v is None or v == "" for v in rows[-1]):
        rows.pop()
    return Sheet(sheet_key(path, name), str(path.resolve()), name, rows, warnings or [])


def _load_file(filename: str, cancelled=lambda: False) -> list[Sheet]:
    path = Path(filename)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} 大于 50 MB，请拆分文件。")
    ext = path.suffix.lower()
    if ext in {".csv", ".tsv"}:
        raw = path.read_bytes()
        text = None
        encodings = ("utf-16",) if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "gb18030")
        for encoding in encodings:
            try:
                text = raw.decode(encoding)
                break
            except UnicodeError:
                pass
        if text is None:
            raise ValueError(f"无法识别 {path.name} 的编码，请另存为 UTF-8。")
        delimiter = "\t" if ext == ".tsv" else ","
        if ext == ".csv":
            try:
                delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t").delimiter
            except csv.Error:
                pass
        rows, count = [], 0
        import io
        for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter):
            if cancelled():
                raise InterruptedError("已取消导入")
            count += len(row)
            if count > MAX_CELLS:
                raise ValueError(f"{path.name} 超过 {MAX_CELLS:,} 个单元格，请拆分。")
            rows.append(row)
        return [_make(path, path.stem, rows)]
    if ext in {".xlsx", ".xlsm"}:
        import openpyxl
        try:
            with ZipFile(path) as archive:
                if sum(i.file_size for i in archive.infolist()) > MAX_UNPACKED_BYTES:
                    raise ValueError("Excel 解压后超过 256 MB，请拆分文件。")
        except BadZipFile as error:
            raise ValueError("文件不是有效的 Excel 工作簿，可能已加密或损坏。") from error
        # Never execute macros or evaluate formulas. Formula cells are deliberately excluded.
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
        sheets = []
        try:
            total = 0
            for ws in workbook.worksheets:
                rows, formulas, errors = [], 0, 0
                for row in ws.iter_rows():
                    if cancelled():
                        raise InterruptedError("已取消导入")
                    total += len(row)
                    if total > MAX_CELLS:
                        raise ValueError(f"{path.name} 超过 {MAX_CELLS:,} 个单元格，请拆分。")
                    values = []
                    for cell in row:
                        if cell.data_type == "f":
                            formulas += 1
                            # Keep the formula visible, numeric() excludes it.
                        if cell.data_type == "e":
                            errors += 1
                        value = cell.value
                        values.append(value.isoformat() if isinstance(value, (date, datetime, time)) else value)
                    rows.append(values)
                notes = []
                if formulas:
                    notes.append(f"{ws.title}：{formulas} 个公式单元格未参与核验；请另存为数值后检查公式结果。")
                if errors:
                    notes.append(f"{ws.title}：{errors} 个 Excel 错误值未参与核验。")
                if ws.sheet_state != "visible":
                    notes.append(f"{ws.title}：这是隐藏工作表，已列入可选范围。")
                sheets.append(_make(path, ws.title, rows, notes))
        finally:
            workbook.close()
        return sheets
    if ext == ".xls":
        import xlrd
        workbook = xlrd.open_workbook(str(path), on_demand=True)
        result, total = [], 0
        try:
            for ws in workbook.sheets():
                if cancelled():
                    raise InterruptedError("已取消导入")
                total += ws.nrows * ws.ncols
                if total > MAX_CELLS:
                    raise ValueError(f"{path.name} 超过 {MAX_CELLS:,} 个单元格，请拆分。")
                rows = []
                for row in ws.get_rows():
                    if cancelled():
                        raise InterruptedError("已取消导入")
                    rows.append([c.value if c.ctype not in (xlrd.XL_CELL_DATE, xlrd.XL_CELL_BOOLEAN,
                                                           xlrd.XL_CELL_ERROR) else str(c.value) + " [非测量值]"
                                 for c in row])
                result.append(_make(path, ws.name, rows, [
                    f"{ws.name}：旧版 .xls 只读取保存的数值缓存，无法识别公式来源；建议转换为 .xlsx。"
                ]))
        finally:
            workbook.release_resources()
        return result
    raise ValueError("支持 .xlsx / .xlsm / .xls / .csv / .tsv")


def load_file(filename: str, cancelled=lambda: False) -> list[Sheet]:
    path = Path(filename)
    before = path.stat()
    if before.st_size > MAX_FILE_BYTES:
        raise ValueError(f"{path.name} 大于 50 MB，请拆分文件。")
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    result = _load_file(filename, cancelled)
    after = path.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError(f"{path.name} 在导入期间发生变化，请保存文件后重新导入。")
    for sheet in result:
        sheet.source_sha256 = source_hash
    return result
