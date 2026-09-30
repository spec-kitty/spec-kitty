---
title: 'Research Notes: Session Presence — Harness Capability Gaps'
description: Open research notes by Architect Alphonso on session-presence harness capability gaps that require investigation before implementation.
doc_status: draft
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# Research Notes: Session Presence — Harness Capability Gaps

**Status:** Open — items below require investigation before implementation  
**Owner:** Architect Alphonso  
**Last updated:** 2026-06-07  
**Related ADR:** `adr/2026-06-07-1-session-presence-multi-harness-architecture.md`  
**Related issue:** https://github.com/spec-kitty/spec-kitty/issues/1760

---

These harnesses are classified as **Pattern E (Unknown / stub)** in the ADR. Each has a `NullWriter` placeholder in the implementation. Before each harness can be promoted to Pattern B, C, or D, the question below must be answered and the finding recorded here.

When a question is resolved, update the entry: fill in the finding, set status to `resolved`, and open a follow-on issue to implement the writer.

---

## Qwen Code (`qwen`, `.qwen/`)

**Question:** Does Qwen Code read a project-level persistent instruction file analogous to `.cursorrules` or `AGENTS.md`? If so, what is the path and format?

**What we know:**
- Spec-kitty deploys commands to `.qwen/commands/` (TOML format with `{{args}}` placeholders)
- Skills root: `.qwen/skills/` (`SKILL_CLASS_NATIVE`)
- Qwen Code is a CLI agent — it likely has a context/rules file, but the path is undocumented in public sources as of 2026-06-07

**Workaround candidates:**
- If Qwen reads `AGENTS.md` (common among CLI agents), promote to Pattern C — no new class needed
- If Qwen has a `.qwenrules` or `.qwen/instructions.md`, promote to Pattern B with `MarkdownRulesWriter`

**Status:** `open`  
**Research required:** Read Qwen Code CLI docs or source; test with a sample project

---

## Kilocode (`kilocode`, `.kilocode/`)

**Question:** Does Kilocode have a persistent instruction file? Kilocode is architecturally derived from Roo Cline — does it inherit `.kilocode/rules/` or `.clinerules`?

**What we know:**
- Spec-kitty deploys to `.kilocode/workflows/`
- Skills root: `.kilocode/skills/` (`SKILL_CLASS_NATIVE`)
- Roo (the upstream) reads `.roo/rules/*.md` and `.clinerules`
- Kilocode may read `.kilocode/rules/` by analogy, but this is unverified

**Workaround candidates:**
- If `.kilocode/rules/` is confirmed, promote to Pattern B — same `MarkdownRulesWriter` as Roo with `rules_path=".kilocode/rules/spec-kitty.md"`
- If it reads `.clinerules` (shared with Roo), a single `.clinerules` file would need a section for both agents — risky for projects running both

**Status:** `open`  
**Research required:** Check Kilocode documentation or source for context-file loading

---

## Augment Code (`auggie`, `.augment/`)

**Question:** What is the path and format of Augment Code's workspace-level persistent instructions? The VS Code extension has a "workspace instructions" concept but the file path is unclear.

**What we know:**
- Spec-kitty deploys to `.augment/commands/`
- Skills root: `.agents/skills/`, `.augment/skills/` (`SKILL_CLASS_SHARED`)
- Augment Code (VS Code extension) is documented to support workspace context — the file may be `.augment/instructions.md` or injected via workspace settings

**Workaround candidates:**
- If `.augment/instructions.md` is confirmed, promote to Pattern B
- If instructions are only configurable via VS Code workspace settings JSON, static injection is not viable — mark as `no-mechanism` and document

**Status:** `open`  
**Research required:** Inspect Augment Code VS Code extension settings or VSIX; check for any CLI companion

---

## Amazon Q (`q`, `.amazonq/`)

**Question:** Does Amazon Q Developer read a project-level instruction file from `.amazonq/`? The `.amazonq/prompts/` directory receives spec-kitty command prompts, but it is unclear if Amazon Q reads any file unconditionally at session start.

**What we know:**
- Spec-kitty deploys to `.amazonq/prompts/`
- `SKILL_CLASS_WRAPPER` (no skill_roots — Amazon Q uses a wrapper pattern, not native skills)
- Amazon Q Developer (IDE extension) is documented to support "workspace context" but the mechanism is through the IDE, not a file path

**Workaround candidates:**
- Amazon Q CLI (`q chat`) may read `AGENTS.md` — if so, promote to Pattern C
- If context is only available through IDE workspace settings, static injection is not viable

**Status:** `open`  
**Research required:** Test `q chat` in a directory containing `AGENTS.md`; check if content is included in context

---

## Mistral Vibe (`vibe`, `.agents/skills/`)

**Question:** Does Mistral Vibe read a persistent project-level instruction file? The `.vibe/config.toml` configures skill routing but it is unclear if any file is loaded into the LLM context unconditionally.

**What we know:**
- Spec-kitty deploys skills to `.agents/skills/` (shared with Codex, Pi, Letta)
- Config: `.vibe/config.toml`
- Skills class: `SKILL_CLASS_SHARED`

**Workaround candidates:**
- If `.vibe/rules.md` or a `system_prompt` field in `.vibe/config.toml` exists, promote to Pattern B/D
- If Vibe reads `AGENTS.md`, promote to Pattern C — same `AgentsMdWriter` as Codex/OpenCode

**Status:** `open`  
**Research required:** Read Mistral Vibe documentation; inspect `.vibe/config.toml` schema

---

## Pi (`pi`, `.agents/skills/`, `.pi/skills/`)

**Question:** Does the Pi agent have a persistent instruction/context file that is loaded at session start?

**What we know:**
- Spec-kitty deploys to `.agents/skills/` and `.pi/skills/`
- Runtime state in `.pi/` (auth, logs, session state)
- Skills class: `SKILL_CLASS_SHARED`

**Workaround candidates:**
- If Pi reads `AGENTS.md`, promote to Pattern C
- If Pi has a `.pi/instructions.md` or similar, promote to Pattern B

**Status:** `open`  
**Research required:** Check Pi agent documentation or source

---

## Letta Code (`letta`, `.agents/skills/`)

**Question:** Does Letta Code have a project-level persistent instruction file loaded into agent memory/context at session start?

**What we know:**
- Spec-kitty deploys to `.agents/skills/`
- Runtime state in `.letta/` (auth, memory — Letta has persistent memory architecture)
- Skills class: `SKILL_CLASS_SHARED`

**Workaround candidate:**
- Letta's memory architecture is agent-side (the agent stores context internally), not file-side. A static file injection may not be the right model — Letta may need a one-time "remember this" injection via the Letta API at project init rather than a file write.
- This is architecturally different from all other patterns and may warrant its own Pattern F.

**Status:** `open — possible new pattern`  
**Research required:** Confirm whether Letta reads any file at session start vs relying solely on agent-internal memory; if memory-only, design Pattern F (API injection at init)

---

## Session Hook Gaps (all harnesses except Claude Code)

**Question:** Is there any harness other than Claude Code that exposes a session-start hook (i.e., the ability to run a shell command at the start of each AI session)?

**Known:**
- Claude Code: `SessionStart` in `.claude/settings.json` ✅
- All others: no documented hook mechanism as of 2026-06-07

**Impact:** For harnesses without a hook, the upgrade check can only be delivered as static text in the orientation file — e.g., "run `spec-kitty upgrade --cli` to check for updates." This is a soft hint, not a live check.

**Future candidates to monitor:**
- Cursor: VS Code extension hooks may become available
- Windsurf: Windsurf IDE may expose session hooks in future versions
- OpenCode: Open-source; could accept a PR to add hook support

**Status:** `open — monitoring`  
**Action:** When a new harness gains hook support, implement `HookRegistrar` for it and update the ADR.

---

## How to Resolve an Entry

1. Research the question (docs, source inspection, or live test)
2. Update the entry: add **Finding**, change **Status** to `resolved` or `no-mechanism`
3. If resolved with a viable mechanism: open a follow-on issue to implement the writer and update the registry in `src/specify_cli/session_presence/writers/registry.py`
4. If `no-mechanism`: the `NullWriter` stub remains; document the limitation in user-facing docs
