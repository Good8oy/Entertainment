"""In-process Qt integration checks against the real import/scan/export handlers."""
import json
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from datascan.app import MainWindow
from datascan.demo import create_demo


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    window = MainWindow()
    yield window
    window.result = None
    window.close()
    window.deleteLater()
    app.processEvents()


def wait(app, predicate, timeout=15):
    start = time.monotonic()
    while not predicate():
        app.processEvents()
        time.sleep(.005)
        if time.monotonic() - start > timeout:
            raise TimeoutError("Qt worker did not finish")
    app.processEvents()


def import_and_scan(app, window, tmp_path):
    window.import_paths(create_demo(tmp_path))
    wait(app, lambda: window.worker is None)
    assert len(window.sheets) == 5
    window.start_scan()
    wait(app, lambda: window.worker is None)
    assert window.result is not None


def test_full_import_scan_source_review_and_export(app, window, tmp_path, monkeypatch):
    import_and_scan(app, window, tmp_path)
    assert window.export_button.isEnabled()
    assert len(window.result.evidence) == 12
    assert window.current_evidence is not None
    selected = window.current_evidence
    region = selected.regions[0]
    window.locate_region(region, 2)
    assert window.pages.currentIndex() == 1
    assert window.source_select.currentData() == region.sheet
    assert region.cells[2] in window.source_model.hits
    assert window.source_table.currentIndex().row() == region.cells[2][0] - 1
    assert window.source_model.data(window.source_model.index(0, 0), Qt.ItemDataRole.DisplayRole)
    window.update_review(selected, "正常共用／已解释")
    selected.note = "测试：共享同一组对照。"
    target = tmp_path / "review.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **kw: (str(target), "JSON 证据包 (*.json)"))
    window.export()
    payload = json.loads(target.read_text(encoding="utf-8"))
    hit = next(e for e in payload["evidence"] if e["id"] == selected.id)
    assert hit["review"] == "正常共用／已解释"
    assert hit["note"] == "测试：共享同一组对照。"


def test_filters_and_scope_invalidation(app, window, tmp_path):
    import_and_scan(app, window, tmp_path)
    window.level_filter.setCurrentText("质量提示")
    assert window.evidence_table.rowCount() == 1
    assert window.current_evidence.rule == "quality"
    window.search.setText("does-not-exist")
    assert window.evidence_table.rowCount() == 0
    assert window.current_evidence is None
    window.search.clear()
    assert window.evidence_table.rowCount() == 1
    child = window.file_tree.topLevelItem(0).child(0)
    child.setCheckState(0, Qt.CheckState.Unchecked)
    assert len(window.selected_sheets()) == 4
    assert window.result is None
    assert not window.export_button.isEnabled()


def test_repeat_scan_rebuilds_detail_and_clear_resets_source(app, window, tmp_path):
    import_and_scan(app, window, tmp_path)
    old_evidence = window.current_evidence
    window.start_scan()
    wait(app, lambda: window.worker is None)
    assert window.current_evidence is not old_evidence
    assert window.current_evidence is window.result.evidence[0]
    window.clear_data()
    assert not window.sheets
    assert window.source_table.model() is None
    assert window.current_evidence is None
