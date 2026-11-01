---
title: How to Keep MCP Agents in the Worktree
description: Keep MCP-backed editors and agents pointed at the active Spec Kitty worktree instead of the repository root.
doc_status: active
updated: '2026-06-12'
type: how-to
related:
- guides/how-to/missions/implement-work-package
- guides/how-to/collaboration/parallel-development
audience:
- profile: external/tech-lead-evaluator
  guidance_text: Written for the External Tech Lead Evaluator reader.
---
# How to Keep MCP Agents in the Worktree

Use this guide when an MCP-backed editor or agent keeps opening the repository root instead of the active Spec Kitty worktree.

This is a workspace configuration issue, not a Spec Kitty workflow bug. Spec Kitty creates the worktree for implementation, but the MCP server or editor still has to follow that new workspace root.

## What Goes Wrong

For code-change work packages, `spec-kitty` creates an execution worktree under `.worktrees/` and prints its path; your shell, editor, and MCP server must follow it.
If your MCP-backed editor keeps its own repository root, it can keep editing files in the main checkout while Spec Kitty thinks you are inside the worktree.

That mismatch is the whole problem:

- Spec Kitty is operating in the worktree
- the editor or MCP agent is still attached to the repository root
- edits land in the wrong place

## Recommended Pattern

1. Start implementation with `spec-kitty agent action implement WP01 --agent <name>`.
2. Use the path printed by the command as the workspace root in your editor.
3. Restart the MCP server or agent after switching into that worktree.
4. Keep one editor session per worktree.

If you are using tools such as Serena MCP or OpenCode, the same rule applies: open the worktree path as the workspace, not the repository root.

## If the Agent Still Points at the Root

If the agent keeps finding files in the root checkout:

1. Close the MCP-backed editor or agent session.
2. Reopen it from inside the worktree directory.
3. Confirm the shell and file tree now point at the worktree path.

If that still does not stick, treat the current session as attached to the wrong root and start a fresh one in the worktree.

## Good Habits

- Do not keep the root checkout and the active worktree open in the same MCP session.
- Treat the printed worktree path as authoritative for implementation.
- Use a separate session for each active worktree.

## See Also

- [Implement a work package](../missions/implement-work-package.md)
- [Git Worktrees Explained](../../../architecture/git-worktrees.md)
- [Parallel Development](parallel-development.md)
