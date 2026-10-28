# Capability Gap Decision

- Decision: improve
- Form: runtime_detection / runbook_or_solution_note
- Landing place: `setup.ps1`、`build.ps1`、README

## Observed Detour

| Evidence | Intended path | Gap | Fallback | Impact |
| --- | --- | --- | --- | --- |
| `python` 默认指向 Conda 3.7.1 | 使用现代 Qt 与 Python 工具链 | 默认解释器过旧 | 发现已安装的 uv Python 3.12，建立项目虚拟环境 | 避免解析到旧版依赖和混用全局环境 |
| uv 缓存与项目位于不同盘符 | 快速硬链接依赖 | 跨卷不能硬链接 | 显式 `--link-mode=copy` | 初始化路径稳定，日志更清楚 |
| Windows Qt offscreen 渲染缺字 | 截图验证中文排版 | offscreen 字体枚举不完整 | Qt 原生平台检查与截图 | 避免把缺字截图误认为产品问题 |

## Recommended Improvement

项目启动脚本固定创建 Python 3.12 环境，已有环境预检版本；依赖安装显式复制。
GUI 验证优先使用原生平台；CI 使用 offscreen 时显式加载字体。
已有初始化脚本足够承载修复，不需要新技能或全局环境改动。

## Verification Signals

- 项目解释器为 Python 3.12，运行完整测试通过。
- 演示数据五张表覆盖八类规则，得到 12 条证据。
- 原生窗口正确显示中文与数值对应坐标。

## Out of Scope

不修改全局 Python、PATH、Shell 配置或现有技能；不修复与此项目无关的桌面工具。
