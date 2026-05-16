---
name: bilibili-focus
description: Use when the user wants Codex to open Bilibili after they submit a task and return focus to the Codex desktop app when the task is complete.
---

# Bilibili Focus

This skill is Windows-focused and relies on the helper scripts in `../../scripts/`.

## Boundary

Codex plugins in this environment do not expose a reliable global client lifecycle hook for "composer submitted" or "assistant response completed". Use this skill as the practical workflow: run the open script as the first action after receiving the user request, complete the requested work, then run the focus script immediately before the final answer.

## Workflow

1. At the start of the task, run:

```powershell
powershell -ExecutionPolicy Bypass -File "<plugin-root>\scripts\Open-BilibiliBreak.ps1"
```

2. Complete the user's actual request.

3. Immediately before the final response, run:

```powershell
powershell -ExecutionPolicy Bypass -File "<plugin-root>\scripts\Focus-Codex.ps1"
```

4. If either script fails, continue the requested work and mention the focus failure briefly in the final response.

## Notes

- Run each script at most once per user task unless the user asks to retry.
- Do not wait for Bilibili or inspect the user's browser activity.
- The focus script only targets an existing Codex desktop window; it does not start Codex if the app is closed.

