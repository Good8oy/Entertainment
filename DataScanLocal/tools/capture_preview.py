"""Render this application's own widgets on the native Qt platform for visual QA."""
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication
from datascan.app import MainWindow
from datascan.demo import create_demo
from datascan.report import export_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hidden", action="store_true", help="Render this app's widgets without showing a desktop window")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    app = QApplication([])
    window = MainWindow()
    if args.hidden:
        window.ensurePolished()
    else:
        window.show()
    window.import_paths(create_demo(output / "demo"))
    deadline = time.monotonic() + 20
    while window.worker:
        app.processEvents()
        if time.monotonic() > deadline:
            raise TimeoutError("Demo import timed out")
    window.start_scan()
    while window.worker:
        app.processEvents()
        if time.monotonic() > deadline:
            raise TimeoutError("Demo scan timed out")
    app.processEvents()
    assert window.result is not None
    assert window.grab().save(str(output / "workbench.png"))
    region = window.current_evidence.regions[0]
    window.locate_region(region)
    app.processEvents()
    assert window.grab().save(str(output / "source.png"))
    window.navigate(0)
    window.resize(1120, 740)
    app.processEvents()
    assert window.grab().save(str(output / "compact.png"))
    export_report(window.result, str(output / "demo-report.html"))
    export_report(window.result, str(output / "demo-evidence.json"))
    print(f"Verified {len(window.result.evidence)} records; previews in {output}")
    window.result = None
    window.close()


if __name__ == "__main__":
    main()
