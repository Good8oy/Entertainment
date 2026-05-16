# Codex Bilibili Focus

> Generated with Codex assistance.
>
> 本项目由 Codex 辅助生成。

## 中文说明

`codex-bilibili-focus` 是一个 Windows 本地 Codex 插件辅助包。它的目标是在用户提交 Codex 指令后打开 Bilibili，并在 Codex 完成任务、准备给出最终回复前，把窗口焦点切回 Codex 桌面端。

### 文件结构

- `.codex-plugin/plugin.json`: Codex 插件元数据。
- `skills/bilibili-focus/SKILL.md`: 插件技能说明，定义 Codex 应如何执行打开和切回流程。
- `scripts/Open-BilibiliBreak.ps1`: 打开 `https://www.bilibili.com/`。
- `scripts/Focus-Codex.ps1`: 查找正在运行的 Codex 桌面窗口并切回焦点。
- `scripts/Invoke-BilibiliBreak.ps1`: 组合脚本，可在指定延迟后自动切回 Codex。

### 使用方式

从仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\plugins\codex-bilibili-focus\scripts\Open-BilibiliBreak.ps1
powershell -ExecutionPolicy Bypass -File .\plugins\codex-bilibili-focus\scripts\Focus-Codex.ps1
```

测试延迟返回：

```powershell
powershell -ExecutionPolicy Bypass -File .\plugins\codex-bilibili-focus\scripts\Invoke-BilibiliBreak.ps1 -ReturnDelaySeconds 10
```

### 重要边界

当前本地 Codex 插件规范没有暴露稳定的全局客户端生命周期事件，例如“用户刚按下发送”或“模型回复刚完成”。因此，本插件采用可执行脚本加技能说明的方式实现：在任务开始时打开 Bilibili，在最终回复前切回 Codex。

## English

`codex-bilibili-focus` is a Windows-focused local helper plugin for Codex. It opens Bilibili after a user submits a Codex task and returns focus to the Codex desktop app before Codex sends the final response.

### Project Structure

- `.codex-plugin/plugin.json`: Codex plugin metadata.
- `skills/bilibili-focus/SKILL.md`: Skill instructions describing the open-and-return workflow.
- `scripts/Open-BilibiliBreak.ps1`: Opens `https://www.bilibili.com/`.
- `scripts/Focus-Codex.ps1`: Finds the running Codex desktop window and focuses it.
- `scripts/Invoke-BilibiliBreak.ps1`: Combined helper that can return to Codex after a delay.

### Usage

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\plugins\codex-bilibili-focus\scripts\Open-BilibiliBreak.ps1
powershell -ExecutionPolicy Bypass -File .\plugins\codex-bilibili-focus\scripts\Focus-Codex.ps1
```

Test delayed return:

```powershell
powershell -ExecutionPolicy Bypass -File .\plugins\codex-bilibili-focus\scripts\Invoke-BilibiliBreak.ps1 -ReturnDelaySeconds 10
```

### Limitation

The available local Codex plugin specification does not expose stable global client lifecycle hooks such as "user pressed send" or "assistant finished responding". This plugin therefore implements the workflow through helper scripts and skill instructions: open Bilibili at task start and focus Codex before the final answer.
