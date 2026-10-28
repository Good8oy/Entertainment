from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from . import __version__


def column_name(col: int) -> str:
    result = ""
    while col:
        col, rest = divmod(col - 1, 26)
        result = chr(65 + rest) + result
    return result


def coordinate(row: int, col: int) -> str:
    return f"{column_name(col)}{row}"


@dataclass
class Sheet:
    key: str
    path: str
    name: str
    rows: list[list[Any]]
    warnings: list[str] = field(default_factory=list)
    source_sha256: str = ""

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def width(self) -> int:
        return max(map(len, self.rows), default=0)

    def value(self, row: int, col: int) -> Any:
        if 1 <= row <= len(self.rows) and 1 <= col <= len(self.rows[row - 1]):
            return self.rows[row - 1][col - 1]
        return None


@dataclass(frozen=True)
class Region:
    sheet: str
    cells: tuple[tuple[int, int], ...]
    values: tuple[float, ...]
    label: str = ""

    @property
    def address(self) -> str:
        if not self.cells:
            return ""
        start, end = self.cells[0], self.cells[-1]
        if start == end:
            return coordinate(*start)
        return f"{coordinate(*start)}:{coordinate(*end)}"


@dataclass
class Evidence:
    id: str
    rule: str
    title: str
    level: str
    description: str
    relation: str
    regions: list[Region]
    details: dict = field(default_factory=dict)
    review: str = "待复核"
    note: str = ""


@dataclass
class Settings:
    window: int = 6
    filter_parameters: bool = True
    cross_sheet: bool = True
    tolerance: float = 1e-9
    rules: list[str] = field(default_factory=lambda: [
        "duplicate", "reordered", "decimal", "affine", "cycle",
        "replicate", "block", "quality",
    ])
    index_batch_size: int = 10_000
    max_evidence: int = 2_000


@dataclass
class ScanResult:
    settings: Settings
    sheets: list[Sheet]
    evidence: list[Evidence]
    warnings: list[str]
    elapsed: float
    started: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    complete: bool = True
    statistics: dict = field(default_factory=dict)

    def payload(self) -> dict:
        return {
            "application": "DataScan Local", "version": __version__,
            "started": self.started, "elapsed_seconds": round(self.elapsed, 3),
            "complete": self.complete, "settings": asdict(self.settings),
            "scan_statistics": self.statistics,
            "scope": [{"key": s.key, "file": s.filename, "path": s.path,
                       "sheet": s.name, "rows": len(s.rows), "columns": s.width,
                       "source_sha256": s.source_sha256}
                      for s in self.sheets],
            "warnings": self.warnings,
            "evidence": [asdict(e) for e in self.evidence],
            "boundary": "独立实现的确定性规则；风险线索不构成学术不端结论。未命中不代表数据真实。",
        }
