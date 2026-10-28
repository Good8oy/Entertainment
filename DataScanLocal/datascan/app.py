from __future__ import annotations

import tempfile
import threading
from collections import Counter
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QTableView, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .demo import create_demo
from .engine import RULE_NAMES, scan
from .loader import load_file, numeric
from .model import Evidence, ScanResult, Settings, Sheet, column_name, coordinate
from .report import export_report
from .style import STYLE
from . import __version__

LEVEL_COLOR = {"高风险": "#d85868", "中风险": "#c38a2a", "质量提示": "#71839f"}
LEVEL_BG = {"高风险": "#fdebed", "中风险": "#fff3df", "质量提示": "#edf1f7"}


def label(text, name=None, wrap=False):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def button(text, callback, name=None):
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.clicked.connect(callback)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def vertical(widget, margins=(0, 0, 0, 0), spacing=10):
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    return layout


class SourceModel(QAbstractTableModel):
    def __init__(self, sheet: Sheet, hits=None, color="#fdebed"):
        super().__init__()
        self.sheet, self.hits, self.color = sheet, hits or set(), color

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.sheet.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else self.sheet.width

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row() + 1, index.column() + 1
        value = self.sheet.value(r, c)
        if role == Qt.ItemDataRole.DisplayRole:
            return "" if value is None else str(value)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{self.sheet.name}!{coordinate(r, c)}\n{value}"
        if role == Qt.ItemDataRole.BackgroundRole:
            if (r, c) in self.hits:
                return QColor(self.color)
            if r == 1:
                return QColor("#f2f5fb")
        if role == Qt.ItemDataRole.ForegroundRole and (r, c) in self.hits:
            return QColor("#a73d50")
        if role == Qt.ItemDataRole.FontRole and numeric(value) is not None:
            return QFont("Consolas", 10)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return column_name(section + 1) if orientation == Qt.Orientation.Horizontal else str(section + 1)
        return None


class Worker(QThread):
    progress = Signal(int, str)
    result = Signal(object)
    failure = Signal(str)
    cancelled = Signal()

    def __init__(self, action, parent=None):
        super().__init__(parent)
        self.action = action
        self.stop = threading.Event()

    def run(self):
        try:
            output = self.action(self.progress.emit, self.stop.is_set)
            if self.stop.is_set():
                self.cancelled.emit()
            else:
                self.result.emit(output)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as error:
            self.failure.emit(f"{type(error).__name__}: {error}")


class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("核验规则与范围")
        self.setMinimumWidth(500)
        layout = vertical(self, (26, 24, 26, 24), 15)
        layout.addWidget(label("选择需要运行的检测规则", "title"))
        layout.addWidget(label("风险级别为规则标签；所有结果都需要人工复核。", "muted", True))
        self.rules = {}
        for key, title in RULE_NAMES.items():
            checkbox = QCheckBox(title)
            checkbox.setChecked(key in settings.rules)
            layout.addWidget(checkbox)
            self.rules[key] = checkbox
        form = QFormLayout()
        self.window = QSpinBox()
        self.window.setRange(4, 20)
        self.window.setValue(settings.window)
        form.addRow("最短连续片段（个数值）", self.window)
        layout.addLayout(form)
        self.parameters = QCheckBox("根据明确的时间、剂量、编号等表头过滤参数")
        self.parameters.setChecked(settings.filter_parameters)
        layout.addWidget(self.parameters)
        self.cross = QCheckBox("允许跨文件、跨 Sheet 比较")
        self.cross.setChecked(settings.cross_sheet)
        layout.addWidget(self.cross)
        layout.addWidget(label("仅核验左侧勾选的工作表。单文件最多 200,000 个单元格；"
                               "候选会自动分批建立本地索引；比较次数或证据达到上限时会明确提示。", "muted", True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("应用规则")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self):
        return Settings(window=self.window.value(), filter_parameters=self.parameters.isChecked(),
                        cross_sheet=self.cross.isChecked(),
                        rules=[key for key, cb in self.rules.items() if cb.isChecked()])


class MainWindow(QMainWindow):
    def __init__(self, demo=False):
        super().__init__()
        self.setWindowTitle(f"DataScan Local {__version__} · 科研数据核验工作台")
        self.resize(1500, 950)
        self.setMinimumSize(1120, 740)
        self.sheets: list[Sheet] = []
        self.settings = Settings()
        self.result: ScanResult | None = None
        self.current_evidence: Evidence | None = None
        self.worker: Worker | None = None
        self.demo_directory = None
        self.source_model = None
        self.setAcceptDrops(True)
        self.build_ui()
        self.setStyleSheet(STYLE)
        self.setWindowIcon(self.icon())
        if demo:
            QTimer.singleShot(150, self.load_demo)

    @staticmethod
    def icon():
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor("#365fdc"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
        painter.end()
        return QIcon(pixmap)

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(178)
        rail_layout = vertical(rail, (16, 30, 16, 23), 6)
        rail_layout.addWidget(label("DataScan", "brand"))
        rail_layout.addWidget(label("LOCAL  /  科研数据核验", "brandSub"))
        rail_layout.addSpacing(45)
        rail_layout.addWidget(label("工 作 空 间", "railCaption"))
        rail_layout.addSpacing(10)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []
        for index, title in enumerate(["▦   核验工作台", "▤   原始数据", "ⓘ   方法与边界"]):
            nav = button(title, lambda checked=False, i=index: self.navigate(i), "nav")
            nav.setCheckable(True)
            self.nav_group.addButton(nav)
            rail_layout.addWidget(nav)
            self.nav_buttons.append(nav)
        self.nav_buttons[0].setChecked(True)
        rail_layout.addStretch()
        rail_layout.addWidget(label("●  本地离线处理", "railFoot"))
        rail_layout.addWidget(label(f"独立实现 · v{__version__}", "railFoot"))
        outer.addWidget(rail)
        body = QWidget()
        body_layout = vertical(body, spacing=0)
        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(90)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(26, 15, 26, 15)
        titles = QVBoxLayout()
        titles.setSpacing(5)
        titles.addWidget(label("科研数据核验工作台", "title"))
        titles.addWidget(label("从原始记录到数值关系，每条线索都有坐标。", "subtitle"))
        header_layout.addLayout(titles)
        header_layout.addStretch()
        header_layout.addWidget(label("●  原始数据仅在本机处理", "pill"))
        self.export_button = button("导出核验报告  ↗", self.export)
        self.export_button.setEnabled(False)
        header_layout.addWidget(self.export_button)
        body_layout.addWidget(header)
        lower = QWidget()
        lower_layout = QHBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(0)
        lower_layout.addWidget(self.build_files())
        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_workbench())
        self.pages.addWidget(self.build_source())
        self.pages.addWidget(self.build_methods())
        lower_layout.addWidget(self.pages, 1)
        body_layout.addWidget(lower, 1)
        outer.addWidget(body, 1)
        self.statusBar().showMessage("就绪 · 导入表格或载入演示数据")

    def build_files(self):
        pane = QFrame()
        pane.setObjectName("files")
        pane.setFixedWidth(220)
        layout = vertical(pane, (16, 24, 16, 20), 12)
        title_row = QHBoxLayout()
        title_row.addWidget(label("数据文件", "sectionTitle"))
        title_row.addStretch()
        self.clear_button = button("清空", self.clear_data, "subtle")
        title_row.addWidget(self.clear_button)
        layout.addLayout(title_row)
        self.import_button = button("＋  导入数据文件", self.choose_files, "primary")
        layout.addWidget(self.import_button)
        layout.addWidget(label("Excel / CSV / TSV · 可拖入文件", "muted"))
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setIndentation(13)
        self.file_tree.itemChanged.connect(self.scope_changed)
        self.file_tree.itemClicked.connect(self.tree_clicked)
        layout.addWidget(self.file_tree, 1)
        self.scope_text = label("尚未导入工作表", "muted", True)
        layout.addWidget(self.scope_text)
        layout.addSpacing(5)
        self.demo_button = button("载入演示数据", self.load_demo)
        layout.addWidget(self.demo_button)
        layout.addSpacing(12)
        layout.addWidget(label("核验配置", "sectionTitle"))
        self.config_summary = label("8 项规则 · 最短 6 个数值\n参数过滤已开启 · 跨 Sheet 比较", "muted", True)
        layout.addWidget(self.config_summary)
        self.settings_button = button("配置检测规则", self.configure)
        layout.addWidget(self.settings_button)
        self.run_button = button("开始核验  →", self.start_scan, "primary")
        self.run_button.setMinimumHeight(43)
        layout.addWidget(self.run_button)
        self.cancel_button = button("取消当前任务", self.cancel_work)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        return pane

    def build_workbench(self):
        page = QWidget()
        layout = vertical(page, (24, 24, 24, 20), 17)
        row = QHBoxLayout()
        title_layout = QVBoxLayout()
        title_layout.setSpacing(5)
        title_layout.addWidget(label("EVIDENCE WORKSPACE", "eyebrow"))
        title_layout.addWidget(label("数值关系 · 有据可查", "largeTitle"))
        row.addLayout(title_layout)
        row.addStretch()
        self.scan_badge = label("等待导入", "muted")
        row.addWidget(self.scan_badge)
        layout.addLayout(row)
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.count_labels = {}
        for key, title, color in [("all", "证据记录", "#315ed5"), ("高风险", "高风险线索", "#d85868"),
                                  ("中风险", "中风险线索", "#c38a2a"), ("质量提示", "质量提示", "#71839f")]:
            card = QFrame()
            card.setObjectName("card")
            box = vertical(card, (18, 12, 18, 13), 0)
            count = label("—", "cardNumber")
            count.setStyleSheet(f"color: {color};")
            box.addWidget(count)
            box.addWidget(label(title, "cardLabel"))
            self.count_labels[key] = count
            cards.addWidget(card)
        layout.addLayout(cards)
        self.banner = label("核验结果仅为风险线索，请结合实验记录和处理流程进行人工复核。", "hint", True)
        layout.addWidget(self.banner)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索证据、文件、工作表或坐标…")
        self.search.textChanged.connect(self.refresh_evidence)
        tools.addWidget(self.search, 1)
        self.level_filter = QComboBox()
        self.level_filter.addItems(["全部风险", "高风险", "中风险", "质量提示"])
        self.level_filter.currentIndexChanged.connect(self.refresh_evidence)
        tools.addWidget(self.level_filter)
        self.review_filter = QComboBox()
        self.review_filter.addItems(["全部状态", "待复核", "已确认关系", "正常共用／已解释"])
        self.review_filter.currentIndexChanged.connect(self.refresh_evidence)
        tools.addWidget(self.review_filter)
        layout.addLayout(tools)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        list_panel = QFrame()
        list_panel.setObjectName("panel")
        list_layout = vertical(list_panel, (0, 0, 0, 0), 0)
        self.list_caption = label("  证据记录", "sectionTitle")
        self.list_caption.setMinimumHeight(46)
        list_layout.addWidget(self.list_caption)
        self.evidence_table = QTableWidget(0, 3)
        self.evidence_table.setHorizontalHeaderLabels(["数值关系", "风险", "状态"])
        self.evidence_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.evidence_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.evidence_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.evidence_table.verticalHeader().hide()
        self.evidence_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.evidence_table.setColumnWidth(1, 65)
        self.evidence_table.setColumnWidth(2, 88)
        self.evidence_table.itemSelectionChanged.connect(self.select_evidence)
        list_layout.addWidget(self.evidence_table)
        self.empty_list = label("导入数据后开始核验\n\n也可载入演示数据体验完整流程", "muted", True)
        self.empty_list.setAlignment(Qt.AlignmentFlag.AlignCenter)
        list_layout.addWidget(self.empty_list, 1)
        self.evidence_table.hide()
        splitter.addWidget(list_panel)
        detail_panel = QFrame()
        detail_panel.setObjectName("panel")
        detail_layout = vertical(detail_panel, (0, 0, 0, 0), 0)
        self.detail_stack = QStackedWidget()
        empty = QWidget()
        empty_layout = vertical(empty, (20, 20, 20, 20), 12)
        empty_layout.addStretch()
        icon = label("▦")
        icon.setStyleSheet("font-size: 48px; color: #b8c8e5;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(icon)
        text = label("选择一条线索，查看数值对应关系", "sectionTitle", True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(text)
        sub = label("原始坐标 · 并列对照 · 复核记录", "muted", True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(sub)
        empty_layout.addStretch()
        self.detail_stack.addWidget(empty)
        self.detail_scroll = QScrollArea()
        self.detail_scroll.setWidgetResizable(True)
        self.detail_stack.addWidget(self.detail_scroll)
        detail_layout.addWidget(self.detail_stack)
        splitter.addWidget(detail_panel)
        splitter.setSizes([390, 500])
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)
        return page

    def build_source(self):
        page = QWidget()
        layout = vertical(page, (24, 24, 24, 24), 16)
        layout.addWidget(label("原始数据与坐标定位", "largeTitle"))
        layout.addWidget(label("只读视图保留导入时的数据；命中单元格按当前证据着色。", "muted", True))
        self.source_select = QComboBox()
        self.source_select.currentIndexChanged.connect(self.refresh_source)
        layout.addWidget(self.source_select)
        self.source_caption = label("请先导入文件", "muted", True)
        layout.addWidget(self.source_caption)
        self.source_table = QTableView()
        self.source_table.setAlternatingRowColors(True)
        self.source_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.source_table.horizontalHeader().setDefaultSectionSize(145)
        self.source_table.verticalHeader().setDefaultSectionSize(32)
        layout.addWidget(self.source_table, 1)
        return page

    def build_methods(self):
        page = QWidget()
        layout = vertical(page, (24, 24, 24, 24), 18)
        layout.addWidget(label("方法与使用边界", "largeTitle"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        body = vertical(content, (5, 5, 15, 5), 16)
        sections = [
            ("本地处理与独立实现", "DataScan Local 是依据公开产品功能说明独立实现的桌面工具，不包含原产品源码、品牌资产或私有算法。"
             "文件解析、关系核验、报告生成均在本机完成。程序不连接网络，不运行 Excel 宏，不计算公式，也不会修改原始文件。"),
            ("检测规则", "完全重复：数值序列逐项相同。错位／稀疏：连续片段、间隔为 2 的片段，以及窗口内数值重排。"
             "小数尾：至少三位小数的绝对值小数部分一致。线性派生：归一化指纹筛选候选，再按 y = a × x + b 逐项验证，容差为 1e-9。"
             "Replicate：表头明确含 rep / replicate / 重复编号的列，至少三个样本满足固定线性关系。"
             "差值循环：周期长度 2–6，至少完整重复三次。矩形复用：2 × 3 的数值矩形。"
             "质量提示：至少 50 个非整数值，按本表最常见的存储小数位数统一舍入（最多 12 位），"
             "再检查末位数字相对均匀分布的 χ² > 27.88 并输出存储精度分布。"),
            ("参数过滤", "开启后根据明确的表头识别时间、剂量、浓度、波长、频率、温度、序号等参数。"
             "至少需要四个不同数值（replicate 至少三个）才会进入相应关系检测；常数、低辨识度序列通常不进入候选。"
             "表头过滤是启发式方法，可能漏排或错排；关闭过滤后可复查。日期、布尔值和公式文本不参与数值比较。"),
            ("范围、性能与遗漏", "单文件上限 50 MB、200,000 个单元格；Excel 解压上限 256 MB。"
             "候选片段和矩形使用本地磁盘分批索引，不因超过 100,000 个候选而中止，也不会抽样跳过片段。"
             "索引仅存指纹与坐标引用，核验结束或取消后清理。达到 2,000 条证据或 500,000 次关系比较时返回明确标记的部分结果。"
             "程序不是穷举检验，不能保证检出全部数值关系。近似线性、任意稀疏间距及其他大小的矩形未覆盖。"
             "含数值文本按浮点数解释，末尾零、显示格式和超出浮点精度的数值信息不能用于判断测量精度。"),
            ("怎样解释结果", "风险级别是规则预设标签，不是造假概率。共同对照、校准、单位转换、正常归一化和周期性实验设计"
             "均可能产生检测到的关系。请回到完整原始数据、实验记录、数据处理流程和作者说明核查。"
             "未检出不代表数据真实，单条记录或截图不构成学术不端结论。"),
            ("复核与报告", "选中证据后可标记状态并填写备注，导出 HTML、JSON 或 CSV 保留复核记录。HTML 可在浏览器中打印成 PDF。"
             "报告含命中数据与文件坐标；JSON 还包含本地文件路径。请将报告保存在合适的位置。"
             "报告记录导入文件的 SHA-256 以便追溯。关闭软件不自动保存原始数据或复核记录，离开前请导出报告。"),
        ]
        for title, text in sections:
            card = QFrame()
            card.setObjectName("panel")
            box = vertical(card, (20, 16, 20, 18), 10)
            box.addWidget(label(title, "sectionTitle"))
            box.addWidget(label(text, wrap=True))
            body.addWidget(card)
        body.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择原始数据文件", "",
            "表格数据 (*.xlsx *.xlsm *.xls *.csv *.tsv)")
        if paths:
            self.import_paths(paths)

    def selected_sheets(self):
        keys = set()
        for i in range(self.file_tree.topLevelItemCount()):
            root = self.file_tree.topLevelItem(i)
            for j in range(root.childCount()):
                item = root.child(j)
                if item.checkState(0) == Qt.CheckState.Checked:
                    keys.add(item.data(0, Qt.ItemDataRole.UserRole))
        return [s for s in self.sheets if s.key in keys]

    def rebuild_files(self):
        self.file_tree.blockSignals(True)
        self.file_tree.clear()
        parents = {}
        for sheet in self.sheets:
            if sheet.path not in parents:
                item = QTreeWidgetItem([sheet.filename])
                item.setToolTip(0, sheet.path)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                self.file_tree.addTopLevelItem(item)
                parents[sheet.path] = item
            child = QTreeWidgetItem([f"{sheet.name}  ·  {len(sheet.rows)} 行"])
            child.setData(0, Qt.ItemDataRole.UserRole, sheet.key)
            child.setToolTip(0, f"{sheet.name}\n{len(sheet.rows)} 行 × {sheet.width} 列")
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setCheckState(0, Qt.CheckState.Checked)
            parents[sheet.path].addChild(child)
        self.file_tree.expandAll()
        self.file_tree.blockSignals(False)
        self.source_select.blockSignals(True)
        self.source_select.clear()
        for sheet in self.sheets:
            self.source_select.addItem(f"{sheet.filename}  /  {sheet.name}", sheet.key)
        self.source_select.blockSignals(False)
        self.refresh_source()
        self.scope_changed()

    def scope_changed(self, *_):
        selected = self.selected_sheets()
        self.scope_text.setText(f"已选 {len(selected)} / {len(self.sheets)} 个工作表\n"
                                f"{len({s.path for s in selected})} 个文件")
        self.invalidate()

    def tree_clicked(self, item, _):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key:
            self.source_select.setCurrentIndex(self.source_select.findData(key))
            self.navigate(1)

    def invalidate(self):
        self.result = None
        self.current_evidence = None
        self.export_button.setEnabled(False)
        self.scan_badge.setText("范围已更新 · 待核验" if self.sheets else "等待导入")
        self.detail_stack.setCurrentIndex(0)
        self.banner.setText("核验结果仅为风险线索，请结合实验记录和处理流程进行人工复核。")
        for count in self.count_labels.values():
            count.setText("—")
        self.refresh_evidence()
        self.refresh_source()

    def import_paths(self, paths, autoscan=False):
        if self.worker:
            return
        def action(progress, cancelled):
            loaded, errors = [], []
            for i, path in enumerate(dict.fromkeys(paths)):
                if cancelled():
                    raise InterruptedError()
                progress(int(i / len(paths) * 95), f"导入 {Path(path).name}")
                try:
                    loaded.extend(load_file(path, cancelled))
                except InterruptedError:
                    raise
                except Exception as error:
                    errors.append(f"{Path(path).name}：{error}")
            return loaded, errors
        def complete(payload):
            loaded, errors = payload
            if loaded:
                replacement_paths = {s.path for s in loaded}
                self.sheets = [s for s in self.sheets if s.path not in replacement_paths] + loaded
                self.rebuild_files()
                self.statusBar().showMessage(f"已导入 {len(loaded)} 个工作表，勾选范围后开始核验。")
            if errors:
                QMessageBox.warning(self, "部分文件未导入", "\n".join(errors))
            if autoscan and loaded:
                QTimer.singleShot(50, self.start_scan)
        self.start_work(action, complete)

    def load_demo(self):
        if self.worker:
            return
        if self.demo_directory is None:
            self.demo_directory = tempfile.TemporaryDirectory(prefix="datascan-demo-")
        try:
            paths = create_demo(Path(self.demo_directory.name))
            self.import_paths(paths, autoscan=True)
        except Exception as error:
            QMessageBox.warning(self, "演示数据未载入", str(error))

    def clear_data(self):
        self.sheets.clear()
        self.rebuild_files()
        self.statusBar().showMessage("内存中的数据已清空。源文件未修改。")

    def configure(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            settings = dialog.settings()
            if not settings.rules:
                QMessageBox.information(self, "未选择规则", "请至少勾选一项检测规则。")
                return
            self.settings = settings
            self.config_summary.setText(f"{len(settings.rules)} 项规则 · 最短 {settings.window} 个数值\n"
                f"参数过滤{'开启' if settings.filter_parameters else '关闭'} · "
                f"{'跨 Sheet' if settings.cross_sheet else 'Sheet 内'}比较")
            self.invalidate()

    def start_scan(self):
        if self.worker:
            return
        sheets = self.selected_sheets()
        if not sheets:
            QMessageBox.information(self, "选择核验范围", "请先导入文件，并至少勾选一个工作表。")
            return
        self.navigate(0)
        settings = self.settings
        def action(progress, cancelled):
            return scan(sheets, settings, progress, cancelled)
        def complete(result):
            self.result = result
            self.current_evidence = None
            counts = Counter(e.level for e in result.evidence)
            self.count_labels["all"].setText(str(len(result.evidence)))
            for level in LEVEL_COLOR:
                self.count_labels[level].setText(str(counts[level]))
            self.export_button.setEnabled(True)
            self.scan_badge.setText(f"{'核验完成' if result.complete else '部分核验'} · {result.elapsed:.2f} 秒")
            extra = [w for w in result.warnings if "公式单元格" in w or "保护上限" in w]
            self.banner.setText(extra[0] if extra else "核验结果仅为风险线索，请结合实验记录和处理流程进行人工复核。")
            self.refresh_evidence()
            self.statusBar().showMessage(f"{'核验完成' if result.complete else '部分核验'} · "
                                        f"{len(sheets)} 个工作表 · {len(result.evidence)} 条证据")
        self.start_work(action, complete)

    def start_work(self, action, callback):
        self.worker = Worker(action, self)
        self.set_busy(True)
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(callback)
        self.worker.failure.connect(self.on_failure)
        self.worker.cancelled.connect(lambda: self.statusBar().showMessage("任务已取消；保留上次完成的结果。"))
        self.worker.finished.connect(self.work_finished)
        self.worker.start()

    def set_busy(self, busy):
        for widget in [self.import_button, self.demo_button, self.clear_button, self.run_button,
                       self.settings_button, self.file_tree]:
            widget.setEnabled(not busy)
        self.export_button.setEnabled(not busy and self.result is not None)
        self.cancel_button.setVisible(busy)
        self.cancel_button.setEnabled(True)
        self.progress.setVisible(busy)
        self.progress.setValue(0)

    def on_progress(self, percent, message):
        self.progress.setValue(percent)
        self.statusBar().showMessage(message)

    def on_failure(self, message):
        self.statusBar().showMessage("任务未完成 · 请检查提示后重试")
        QMessageBox.warning(self, "任务未完成", message)

    def work_finished(self):
        worker = self.worker
        self.worker = None
        self.set_busy(False)
        if worker:
            worker.deleteLater()

    def cancel_work(self):
        if self.worker:
            self.worker.stop.set()
            self.cancel_button.setEnabled(False)
            self.statusBar().showMessage("正在取消，请等待当前文件读取结束…")

    def refresh_evidence(self, *_):
        if not hasattr(self, "evidence_table"):
            return
        previous_id = self.current_evidence.id if self.current_evidence else None
        all_items = self.result.evidence if self.result else []
        query = self.search.text().strip().lower()
        lookup = {s.key: s for s in self.sheets}
        items = []
        for item in all_items:
            if self.level_filter.currentIndex() and item.level != self.level_filter.currentText():
                continue
            if self.review_filter.currentIndex() and item.review != self.review_filter.currentText():
                continue
            text = " ".join([item.id, item.title, item.relation, item.note] +
                            [f"{lookup[r.sheet].filename} {lookup[r.sheet].name} {r.address}" for r in item.regions])
            if not query or query in text.lower():
                items.append(item)
        self.evidence_table.blockSignals(True)
        self.evidence_table.setRowCount(len(items))
        selected_row = 0
        for row, item in enumerate(items):
            first = QTableWidgetItem(f"{item.id}  {item.title}")
            first.setData(Qt.ItemDataRole.UserRole, item.id)
            first.setToolTip(item.description)
            self.evidence_table.setItem(row, 0, first)
            risk = QTableWidgetItem(item.level)
            risk.setForeground(QColor(LEVEL_COLOR[item.level]))
            risk.setBackground(QColor(LEVEL_BG[item.level]))
            self.evidence_table.setItem(row, 1, risk)
            self.evidence_table.setItem(row, 2, QTableWidgetItem(item.review))
            self.evidence_table.setRowHeight(row, 50)
            if item.id == previous_id:
                selected_row = row
        self.evidence_table.blockSignals(False)
        self.list_caption.setText(f"  证据记录   {len(items)} / {len(all_items)}")
        self.evidence_table.setVisible(bool(items))
        self.empty_list.setVisible(not items)
        self.empty_list.setText("当前筛选条件下没有记录" if self.result and all_items else (
            "未检出所选规则覆盖的关系\n\n请结合方法边界解释结果" if self.result else
            "导入数据后开始核验\n\n也可载入演示数据体验完整流程"))
        if items:
            self.evidence_table.blockSignals(True)
            self.evidence_table.selectRow(selected_row)
            self.evidence_table.blockSignals(False)
            self.select_evidence()
        else:
            self.current_evidence = None
            self.detail_stack.setCurrentIndex(0)

    def select_evidence(self):
        row = self.evidence_table.currentRow()
        if row < 0 or self.result is None:
            return
        item = self.evidence_table.item(row, 0)
        if item is None:
            return
        selected_id = item.data(Qt.ItemDataRole.UserRole)
        evidence = next(e for e in self.result.evidence if e.id == selected_id)
        self.current_evidence = evidence
        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = vertical(content, (20, 19, 20, 22), 13)
        layout.addWidget(label(f"{evidence.id}  /  {RULE_NAMES[evidence.rule]}", "eyebrow", True))
        heading = label(evidence.title, "sectionTitle", True)
        heading.setStyleSheet("font-size: 17px;")
        layout.addWidget(heading)
        badge = label(f"● {evidence.level}  ·  {len(evidence.regions)} 组位置")
        badge.setStyleSheet(f"color: {LEVEL_COLOR[evidence.level]};")
        layout.addWidget(badge)
        layout.addWidget(label(evidence.description, "muted", True))
        formula = label(evidence.relation, wrap=True)
        formula.setStyleSheet("background: #edf3ff; padding: 12px; border-radius: 6px; color: #3b60b4; font-family: Consolas;")
        layout.addWidget(formula)
        lookup = {s.key: s for s in self.sheets}
        colors = ["#365fdc", "#27a486", "#bd8541", "#9b69bc"]
        for i, region in enumerate(evidence.regions):
            sheet = lookup[region.sheet]
            row_layout = QHBoxLayout()
            caption = label(f"{chr(65 + i) if i < 26 else i + 1}  {sheet.filename}\n{sheet.name}  ·  {region.address}", wrap=True)
            caption.setStyleSheet(f"color: {colors[i % len(colors)]}; font-size: 11px;")
            row_layout.addWidget(caption, 1)
            jump = button("原表定位 ↗", lambda checked=False, r=region: self.locate_region(r))
            jump.setStyleSheet("font-size: 11px; padding: 5px 8px;")
            row_layout.addWidget(jump)
            layout.addLayout(row_layout)
        layout.addWidget(label("逐项数值对照", "sectionTitle"))
        # Render a bounded preview. All coordinates remain available in source view and exports.
        count = max(len(r.cells) for r in evidence.regions)
        visible_count = min(count, 100)
        comparison = QTableWidget(visible_count, len(evidence.regions))
        comparison.setHorizontalHeaderLabels([f"区域 {i + 1}" for i in range(len(evidence.regions))])
        comparison.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        comparison.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        comparison.verticalHeader().hide()
        comparison.setFont(QFont("Consolas", 10))
        comparison.setMinimumHeight(180)
        comparison.setMaximumHeight(330)
        for col, region in enumerate(evidence.regions):
            for row, (cell, value) in enumerate(zip(region.cells[:100], region.values[:100])):
                data = QTableWidgetItem(f"{coordinate(*cell)}   {value:.12g}")
                data.setBackground(QColor(LEVEL_BG[evidence.level] if col == 0 else "#eaf6f1"))
                comparison.setItem(row, col, data)
                comparison.setRowHeight(row, 30)
        comparison.cellClicked.connect(lambda row, col: self.locate_region(evidence.regions[col], row))
        layout.addWidget(comparison)
        layout.addWidget(label(f"{count} 对数值" + (" · 预览前 100 对，完整数据见报告" if count > 100 else " · 点击数值可定位原表"), "muted"))
        if evidence.rule == "quality":
            counts = evidence.details.get("digit_counts", {})
            layout.addWidget(label("末位计数：" + "  ".join(f"{d}: {counts.get(str(d), 0)}" for d in range(10)), "muted", True))
            precisions = evidence.details.get("precision_counts", {})
            layout.addWidget(label("存储小数位数：" + "  ".join(f"{p} 位: {n}" for p, n in sorted(precisions.items())), "muted", True))
        layout.addWidget(label("人工复核记录", "sectionTitle"))
        review = QComboBox()
        review.addItems(["待复核", "已确认关系", "正常共用／已解释"])
        review.setCurrentText(evidence.review)
        review.currentTextChanged.connect(lambda text, e=evidence: self.update_review(e, text))
        layout.addWidget(review)
        note = QPlainTextEdit(evidence.note)
        note.setPlaceholderText("记录实验背景、处理步骤或复核说明；导出报告时保留。")
        note.setMinimumHeight(85)
        note.setMaximumHeight(120)
        note.textChanged.connect(lambda e=evidence, n=note: setattr(e, "note", n.toPlainText()))
        layout.addWidget(note)
        layout.addStretch()
        previous = self.detail_scroll.takeWidget()
        if previous:
            previous.deleteLater()
        self.detail_scroll.setWidget(content)
        self.detail_stack.setCurrentIndex(1)
        self.refresh_source()

    def update_review(self, evidence, text):
        evidence.review = text
        row = self.evidence_table.currentRow()
        if row >= 0:
            self.evidence_table.item(row, 2).setText(text)
        self.statusBar().showMessage("复核状态已更新 · 导出报告以保存记录")
        if self.review_filter.currentIndex():
            self.refresh_evidence()

    def refresh_source(self, *_):
        if not hasattr(self, "source_select"):
            return
        key = self.source_select.currentData()
        sheet = next((s for s in self.sheets if s.key == key), None)
        if sheet is None:
            self.source_table.setModel(None)
            self.source_model = None
            self.source_caption.setText("请先导入文件")
            return
        hits = set()
        if self.current_evidence:
            hits = {cell for r in self.current_evidence.regions if r.sheet == sheet.key for cell in r.cells}
        old_model = self.source_model
        self.source_model = SourceModel(sheet, hits, LEVEL_BG.get(
            self.current_evidence.level if self.current_evidence else "", "#fdebed"))
        self.source_table.setModel(self.source_model)
        if old_model:
            old_model.deleteLater()
        self.source_caption.setText(f"{len(sheet.rows):,} 行 × {sheet.width:,} 列 · {len(hits):,} 个命中单元格"
                                    + ("\n" + "\n".join(sheet.warnings) if sheet.warnings else ""))

    def locate_region(self, region, offset=0):
        self.source_select.setCurrentIndex(self.source_select.findData(region.sheet))
        self.refresh_source()
        self.navigate(1)
        if self.source_model and region.cells:
            row, col = region.cells[min(offset, len(region.cells) - 1)]
            index = self.source_model.index(row - 1, col - 1)
            self.source_table.setCurrentIndex(index)
            self.source_table.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)

    def export(self):
        if self.result is None:
            return
        path, selected_filter = QFileDialog.getSaveFileName(self, "导出核验报告", "DataScan_核验报告.html",
            "HTML 报告 (*.html);;JSON 证据包 (*.json);;CSV 证据清单 (*.csv)")
        if not path:
            return
        suffix = ".json" if selected_filter.startswith("JSON") else (
            ".csv" if selected_filter.startswith("CSV") else ".html")
        if Path(path).suffix.lower() not in {".html", ".htm", ".json", ".csv"}:
            path += suffix
        try:
            export_report(self.result, path)
            self.statusBar().showMessage(f"报告已导出：{path}")
        except Exception as error:
            QMessageBox.warning(self, "报告未导出", str(error))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and self.worker is None:
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        paths = [p for p in paths if Path(p).suffix.lower() in {".xlsx", ".xlsm", ".xls", ".csv", ".tsv"}]
        if paths:
            self.import_paths(paths)
            event.acceptProposedAction()

    def closeEvent(self, event):
        if self.worker:
            self.worker.stop.set()
            self.statusBar().showMessage("正在停止当前任务，完成后可关闭窗口。")
            event.ignore()
            return
        if self.result is not None:
            answer = QMessageBox.question(self, "关闭工作台", "原始文件不会修改。未导出的复核记录将丢失，确定关闭？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()
