"""Package only the verified executable, documentation and synthetic examples."""
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    root = Path(__file__).resolve().parents[1]
    executable = root / "dist" / "DataScanLocal.exe"
    check = json.loads((root / "artifacts" / "frozen-self-test.json").read_text(encoding="utf-8"))
    if not check.get("success") or not check.get("frozen"):
        raise RuntimeError("Package only a successfully verified frozen executable")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    manifest = {"version": "0.1.0", "source_commit": commit,
                "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                "frozen_self_test": check}
    archive = root / "dist" / "DataScanLocal-0.1.0-Windows.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        output.write(executable, "DataScanLocal.exe")
        output.write(root / "README.md", "README.md")
        output.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for path in sorted((root / "artifacts" / "demo").glob("*.xlsx")):
            output.write(path, "演示数据/" + path.name)
        for name in ("workbench.png", "source.png", "demo-report.html"):
            path = root / "artifacts" / name
            if path.exists():
                output.write(path, "示例与预览/" + name)
    with ZipFile(archive) as output:
        assert output.testzip() is None
        assert "DataScanLocal.exe" in output.namelist()
    print(f"Packaged {archive} ({archive.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
