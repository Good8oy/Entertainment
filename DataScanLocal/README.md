# DataScan Local

本地运行的科研原始数据核验桌面工具，依据 DataScan 官网公开功能说明独立实现。包含可运行的核验引擎、中文界面、原表定位、复核备注及报告导出。没有原产品源码或私有算法，不承诺与其检测结果一致。

## Windows 直接使用

双击交付目录中的 `DataScanLocal.exe`，无需安装 Python、Excel 或联网。首次解包启动需要数秒。

1. 点击“载入演示数据”可体验完整流程。演示文件全部为合成数据。
2. “导入数据文件”可多选 `.xlsx`、`.xlsm`、`.xls`、`.csv`、`.tsv`，也可将文件拖入窗口。
3. 勾选左侧工作表，可配置片段长度、检测规则、参数过滤和跨 Sheet 比较。
4. 点击“开始核验”，选择证据查看逐项数值；点击“原表定位”或对照单元格跳转到原始坐标。
5. 填写复核状态与备注，导出 HTML、JSON 或 CSV。HTML 报告可使用浏览器打印成 PDF。

数据和复核记录保存在当前进程内存中；关闭前请导出报告。导入时读取文件快照，核验期间不重新读取源文件。重新导入、改变范围或规则会清除旧结果。不会修改源文件。

## 功能与边界

| 规则 | 实现方式与范围 |
| --- | --- |
| 完全重复 | 行、列连续片段逐项完全一致；同一关系尽量归并多组位置 |
| 错位、稀疏、重排 | 跨坐标连续片段、间隔为 2 的数列、窗口内数值多重集合重排；保留实际对应坐标 |
| 小数尾一致 | 至少三位小数的绝对值小数部分一致，整数部分发生变化 |
| 差值、比例、线性派生 | 归一化指纹筛选，逐项验证 `y = a × x + b`；浮点相对及绝对容差均为 `1e-9` |
| Replicate | 仅匹配表头含 `rep1` / `Replicate 1` / `重复1` 等编号的列；至少三个样本有固定线性关系 |
| 差值循环 | 相邻差值周期长度 2–6，完整循环至少三次 |
| 矩形块复用 | 不重叠的 2 × 3 数值块重复 |
| 数字质量 | 至少 50 个非整数值；按最常见存储精度统一舍入（最多 12 位），末位对均匀分布的 χ² > 27.88 时提示，报告末位与精度计数 |

参数过滤按明确的时间、剂量、浓度、波长、温度、频率、编号等表头识别。常数和低辨识度片段不会进入多数关系检测。它是启发式过滤，可关闭复查。

**方法限制：**所有规则都是筛查规则，不是造假判定。正常共享对照、归一化、校准、单位换算和周期设计都可能命中。未命中不代表数据真实。未实现任意稀疏间距、其他尺寸矩形或穷举近似线性。浮点指纹存在舍入边界；数值文本按浮点解析，存储尾零与 Excel 显示精度不等于测量精度。

`.xlsx` / `.xlsm` 中公式以文本显示，不计算、不使用可能过期的缓存，报告明确列出跳过数量；需要检查公式结果时请先另存为数值。宏不运行。`.xls` 只能读取已保存的数值缓存，不能确定公式来源，报告会注明。日期、布尔值和 Excel 错误值不作为测量值。

### 保护上限

- 单文件最大 50 MB、200,000 个单元格；Excel 解压后最大 256 MB。
- 最多 100,000 个候选片段或矩形，超过后要求缩小范围，不生成部分结果。
- 达到 2,000 条证据或 500,000 次关系比较时，结果与报告明确标注“部分核验”。
- 对照面板显示前 100 对数值；源表和报告保留全部命中坐标。

报告带文件导入时的 SHA-256、所选范围、规则参数、方法边界和复核记录。JSON 还包括本地源文件路径。请自行保管报告中的数据。

## 源码运行

要求 Python 3.12+。Windows 推荐使用已有的 `uv`：

```powershell
.\setup.ps1
.\.venv\Scripts\python.exe run.py
.\.venv\Scripts\python.exe run.py --demo
```

也可以双击 `start.cmd`；它会在首次运行时调用 `setup.ps1` 建立项目内环境。只有环境初始化需要联网下载依赖，应用运行没有网络调用。`setup.ps1` 检查 Python 版本，避免系统默认的旧版 Conda Python；显式采用复制模式，兼容依赖缓存与工作区处于不同磁盘的情况。

macOS / Linux 可使用 Python 3.12+ 建立虚拟环境，安装 `requirements.txt` 后运行 `python run.py`；本次交付只验证 Windows，未打包其他系统。

### 批量命令行

```powershell
.\.venv\Scripts\python.exe -m datascan.cli a.xlsx b.csv --output result.html
.\.venv\Scripts\python.exe -m datascan.cli --demo --output demo-report.json
.\.venv\Scripts\python.exe -m datascan.cli a.xlsx --within-sheet --window 8 --output result.json
```

完整筛查退出码为 0；失败为 1；达到上限的部分结果为 2。

### 测试和打包

```powershell
uv pip install --python .venv\Scripts\python.exe --link-mode=copy -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\build.ps1
```

输出 `dist/DataScanLocal.exe`。运行时只需要 PySide6 Essentials、openpyxl、xlrd；不需要模型、后端服务、账号、API key 或数据库。Qt 原生界面在 Windows 上直接检查；如在 CI 中使用 `offscreen`，需额外配置中文字体，不能用缺字的截图评判实际排版。

## 目录

```text
datascan/
  app.py       中文桌面工作台与异步任务
  engine.py    八类确定性筛查规则
  loader.py    本地表格读取与数据类型处理
  model.py     表格、坐标、证据和核验结果
  report.py    HTML / JSON / CSV 导出
  demo.py      合成演示数据
  cli.py       批量核验入口
tests/         算法、文件及 Qt 集成测试
run.py         桌面入口
setup.ps1      项目环境初始化
build.ps1      测试并生成 Windows 单文件程序
```
