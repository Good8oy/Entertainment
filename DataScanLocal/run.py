"""Desktop entry point; PyInstaller also freezes this file."""
import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from PySide6.QtWidgets import QApplication
from datascan.app import MainWindow
from datascan import __version__


def main():
    parser = argparse.ArgumentParser(description="本地科研原始数据核验工作台")
    parser.add_argument("--demo", action="store_true", help="载入合成示例并核验")
    parser.add_argument("--self-test", metavar="RESULT.json", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_test:
        # Frozen-runtime verification without opening or controlling any desktop window.
        from datascan.demo import create_demo
        from datascan.engine import RULE_NAMES, scan
        from datascan.loader import load_file
        from datascan.report import export_report
        try:
            with tempfile.TemporaryDirectory(prefix="datascan-check-") as directory:
                folder = Path(directory)
                result = scan([s for p in create_demo(folder) for s in load_file(p)])
                counts = Counter(e.rule for e in result.evidence)
                if set(counts) != set(RULE_NAMES) or not result.complete:
                    raise RuntimeError("Synthetic rule coverage check failed")
                for suffix in ("html", "json", "csv"):
                    export_report(result, str(folder / f"check.{suffix}"))
                report = json.loads((folder / "check.json").read_text(encoding="utf-8"))
                if len(report["evidence"]) != len(result.evidence):
                    raise RuntimeError("Report round-trip check failed")
                # Exercise the former 100,000-candidate failure in the actual frozen runtime.
                from random import Random
                from datascan.model import Sheet
                random = Random(196)
                rows = [["Signal A", "Signal B"]]
                rows += [[round(random.uniform(1, 1000), 4), round(random.uniform(1, 1000), 4)]
                         for _ in range(26_000)]
                for offset in range(6):
                    rows[-6 + offset][1] = rows[1 + offset][0]
                large = scan([Sheet("large", "synthetic-large.xlsx", "Data", rows)])
                found_last = any(e.rule == "duplicate" and
                                 any(r.cells[-1] == (len(rows), 2) for r in e.regions)
                                 for e in large.evidence)
                if not large.complete or large.statistics["indexed_windows"] <= 100_000 or not found_last:
                    raise RuntimeError("Large-candidate regression check failed")
                payload = {"success": True, "version": __version__,
                           "frozen": bool(getattr(sys, "frozen", False)),
                           "sheets": len(result.sheets), "evidence": len(result.evidence), "rules": dict(counts),
                           "large_scan": {**large.statistics, "complete": large.complete,
                                          "last_row_match": found_last, "elapsed_seconds": round(large.elapsed, 3)}}
        except Exception as error:
            payload = {"success": False, "error": f"{type(error).__name__}: {error}"}
        Path(args.self_test).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if payload["success"] else 1
    app = QApplication(sys.argv[:1])
    app.setApplicationName("DataScan Local")
    app.setOrganizationName("DataScanLocal")
    window = MainWindow(demo=args.demo)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
