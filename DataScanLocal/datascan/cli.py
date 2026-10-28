"""Optional local batch entry point, with the same engine as the desktop app."""
import argparse
import sys
from pathlib import Path

from .demo import create_demo
from .engine import RULE_NAMES, scan
from .loader import load_file
from .model import Settings
from .report import export_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="本地表格核验；不上传数据，不修改源文件")
    parser.add_argument("files", nargs="*")
    parser.add_argument("--output", required=True, help=".html / .json / .csv")
    parser.add_argument("--window", type=int, default=6)
    parser.add_argument("--rules", nargs="+", choices=list(RULE_NAMES), default=list(RULE_NAMES))
    parser.add_argument("--within-sheet", action="store_true")
    parser.add_argument("--include-parameters", action="store_true")
    parser.add_argument("--demo", action="store_true", help="生成合成演示文件到报告旁的 demo-data 文件夹")
    args = parser.parse_args(argv)
    try:
        files = args.files
        if args.demo:
            files = create_demo(Path(args.output).resolve().parent / "demo-data")
        sheets = [s for filename in files for s in load_file(filename)]
        settings = Settings(window=args.window, rules=args.rules,
                            filter_parameters=not args.include_parameters,
                            cross_sheet=not args.within_sheet)
        result = scan(sheets, settings)
        export_report(result, args.output)
        print(f"{'完成' if result.complete else '部分结果'}：{len(sheets)} 个工作表，{len(result.evidence)} 条证据；{args.output}")
        return 0 if result.complete else 2
    except Exception as error:
        print(f"核验失败：{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
