# Agent Instructions

This repository is the source of truth for agent-maintained changes.

## GitHub Repository

- Maintain all modifications in: `https://github.com/Good8oy/Entertainment`
- Before editing, inspect the current repository state and work from the latest target branch.
- Commit related changes together with concise messages.
- Push changes to the remote repository or open a pull request when review is expected.

## Change Principles

- Make the smallest change that satisfies the request.
- Preserve existing structure, naming, formatting, and conventions.
- Do not reformat, rewrite, or reorganize unrelated files.
- Prefer targeted edits over broad abstractions.
- Verify only the behavior affected by the change unless risk requires broader checks.

## Collaboration

- Do not overwrite user or teammate changes.
- Explain what changed and how it was verified.
- If the repository URL, branch, or scope is unclear, ask before editing.

## Bilibili Focus Mode

- For every user task in this repository, run `plugins/codex-bilibili-focus/scripts/Open-BilibiliBreak.ps1` before starting substantive work.
- Before sending the final answer, run `plugins/codex-bilibili-focus/scripts/Focus-Codex.ps1` so the Codex desktop app regains focus.
- If either focus helper script fails, continue the user task and report the focus failure briefly.
