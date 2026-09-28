---
work_package_id: WP06
title: Line-ending-safe skill rendering (#4998)
dependencies:
- WP01
requirement_refs:
- FR-015
- FR-016
- FR-017
- FR-018
- FR-019
- NFR-001
- NFR-002
- NFR-006
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-exit-zero-data-intact-01M3KDAS
base_commit: 45785d2ddc06e9cc4b11d3b806fb7a4b0ce606ac
created_at: '2026-09-28T11:26:22.162760+00:00'
subtasks:
- T030
- T031
- T032
- T033
- T034
- T035
phase: Phase 3 - Encoding-dependent fixes
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- tests/specify_cli/skills/test_crlf_skill_render_4998.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/skills/command_renderer.py
- src/specify_cli/skills/installer.py
- src/specify_cli/skills/verifier.py
- .gitattributes
- tests/specify_cli/skills/test_crlf_skill_render_4998.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Line-ending-safe skill rendering (#4998)

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`. C-006: edit shipped sources, never generated agent copies.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Issue #4998 (P0, Windows): on a source checkout with CRLF line endings, skill install prepends a second bogus frontmatter block to every `SKILL.md`; `doctor` reports ~275 drifts and `upgrade`/`--fix` cannot repair them. Root cause: two frontmatter regexes in `skills/command_renderer.py` match `\n` only — `_RE_FRONTMATTER = r"^\s*---\n(.*?)---\n?"` (~:46, used by `_strip_frontmatter`) and `_RE_LEADING_FRONTMATTER = r"^---\n.*?\n---\n?"` (~:59, used by `ensure_skill_frontmatter`). The installer decodes raw bytes (keeps CRLF: `installer.py:~329, ~733`, `src/specify_cli/runtime/agent_skills.py:~131`) while the verifier uses `read_text` (universal newlines, `verifier.py:~190-213`), so the two sides disagree and the frontmatter is not found → a new one is prepended.

Done means (FR-015–FR-019):
- FR-015: doctrine skills installed from CRLF sources are byte-identical to LF-source installs with exactly one frontmatter block.
- FR-016: command skills rendered from CRLF command templates are byte-identical to LF-template renders (separate fixture; red when only FR-015's fix is applied).
- FR-017: an install corrupted by the old behaviour whose files still match the manifest-recorded hash is restored by `spec-kitty upgrade` and by the doctrine-skill repair `spec-kitty doctor tool-surfaces --kind doctrine-skill --fix` (`managed_skills.py:~80` repair hint); for command skills (Codex/Vibe/Pi/Letta) the repair is `spec-kitty doctor skills --fix`. A second run reports nothing.
- FR-018 (ratchet): a corrupted file the user edited since install (hash ≠ manifest) stays `consent_required` (`installer.py:~894`), not silently overwritten.
- FR-019: `.gitattributes` pins `src/charter/offering/skills/**` and `packs/built-in/missions/mission-steps/**` to `eol=lf`; a test asserts `git check-attr eol` for a sample file under each tree.

## Context & Constraints

- Plan design decision **D5**; research **R5**.
- Use `kernel.text_decode.normalize_newlines` (WP01). Precedent: `template/renderer.py:29` already strips `\r` for the 13 slash-command agents.
- **Normalise at the decode, not at the strip**: in the command-skill render (~:434-447) `raw_text = raw_bytes.decode("utf-8")` then `apply_spdd_blocks_for_project(raw_text, ...)` (~:442) and later `_extract_frontmatter_description(raw_text)` (~:366) all see CRLF. Normalise `raw_text` right after decoding. Note `source_hash = sha256(raw_bytes)` (~:435) is computed on raw bytes. `RenderedSkill.source_hash` has **no production consumer** (only `tests/.../test_command_renderer.py:~463` reads it), so hashing the normalised bytes is low-risk and makes CRLF/LF renders indistinguishable — do that and record it.
- **Repair convergence precondition**: `--fix`/upgrade rewrites a file only when its on-disk hash equals the manifest-recorded hash (`installer.py:~795-800` `unchanged_owned`); otherwise `consent_required`. Test fixtures must seed a manifest recording the corrupted bytes' hash (the realistic state after the buggy install). If convergence does not happen even then, find why (e.g. `installer.py:~328-332` comparing against its own rendering before deciding) and fix within these owned files.
- Skill sources: `src/charter/offering/skills/**` (55 `SKILL.md`). No env override for the source root: tests monkeypatch `SkillRegistry.from_package` to a tmp dir of CRLF copies.
- `tests/architectural/test_merge_reconciliation_class_guard.py` parses `.gitattributes` — run it after T034.

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. Depends on WP01; `spec-kitty implement WP06`.

## Subtasks & Detailed Guidance

### Subtask T030 – Campsite (separate commit)

- Fix pre-existing mypy findings in touched functions: `skills/installer.py:529, 538` (`no-any-return`), `:1040` (subclass of `Any` — likely an untyped import of `SkillRegistry`; fix with a proper import/type or a narrowly-justified, commented ignore only if the base truly is untyped third-party), `skills/verifier.py:190`. Behaviour-preserving.

### Subtask T031 – Red-first repros (`tests/specify_cli/skills/test_crlf_skill_render_4998.py`)

Mark `@pytest.mark.regression`; confirm FAIL; record.

1. FR-015: pick 3 real skill sources, write CRLF copies (`text.replace("\n", "\r\n").encode()`) + a mixed-line-ending variant into tmp; monkeypatch `SkillRegistry.from_package`; run the install entry the CLI uses (prefer the CLI: `spec-kitty upgrade` or the installer function the CLI calls, in a scratch project with `.claude` configured). Compare each installed `SKILL.md` to an LF-source install: byte-identical; exactly one leading `---` block (count `^---$` lines in the first block region).
2. FR-016: CRLF copy of a command template (e.g. `packs/built-in/missions/mission-steps/software-dev/specify/prompt.md`) rendered via the command-skill render path → byte-identical to the LF render; description extracted correctly.
3. FR-017 (**keep the monkeypatched CRLF `SkillRegistry` active during the repair run** — with LF package sources today's code already converges, so the test would be vacuous): seed a corrupted install — `SKILL.md` = bogus block + real block (reproduce by running the unfixed `ensure_skill_frontmatter` on CRLF input, or hand-build the doubled shape from the issue) — and a manifest whose recorded hash is the corrupted bytes' hash; run `spec-kitty upgrade` (CLI) and `spec-kitty doctor tool-surfaces --kind doctrine-skill --fix`; assert restored bytes equal the **LF-source render** and a second run is a no-op. Record the red run on unmodified code.
4. FR-018: same but user-edited (hash ≠ manifest) → still `consent_required`, file untouched.

### Subtask T032 – `ensure_skill_frontmatter`

- Normalise the input text with `normalize_newlines` at the top of `ensure_skill_frontmatter` (~:59 region) before `_RE_LEADING_FRONTMATTER` matching. This covers installer (both call sites), verifier and `runtime/agent_skills.py`. Update the docstring.

### Subtask T033 – Command-skill render

- Normalise `raw_text` immediately after `raw_bytes.decode("utf-8")` (~:436), before `apply_spdd_blocks_for_project`, `_strip_frontmatter`, and `_extract_frontmatter_description`. Apply the `source_hash` decision from the Context section. Keep the `_RE_FRONTMATTER` regex unchanged (input is now LF).

### Subtask T034 – `.gitattributes`

- Add, near related rules, with a comment citing #4998:
  ```
  src/charter/offering/skills/** text eol=lf
  packs/built-in/missions/mission-steps/** text eol=lf
  ```
  Check existing `.gitattributes` for conflicting rules (`merge=` drivers on the same paths must be preserved — attributes combine per line). Add a test that runs `git check-attr eol -- <sample path>` for one file under each tree and asserts `lf`. Run `test_merge_reconciliation_class_guard.py`.

### Subtask T035 – Convert and gate

- **Half-by-half proof (tactic non-vacuity)**: temporarily revert T033 alone → the FR-016 test goes red; revert T032 alone → the FR-015 test goes red. Record both in the Activity Log, then restore.
- At least one install in T031 runs through the real CLI (`spec-kitty upgrade`), not only the installer/render function.

```bash
uv run --frozen pytest tests/specify_cli/skills/ -q
uv run --frozen pytest $(grep -rl "ensure_skill_frontmatter\|command_renderer\|SkillRegistry" tests --include=*.py | sort -u) -q
uv run --frozen pytest tests/architectural/test_merge_reconciliation_class_guard.py tests/cross_cutting/packaging/test_packaging_safety.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check <changed>
uv run --frozen mypy --strict src/specify_cli/skills/command_renderer.py src/specify_cli/skills/installer.py src/specify_cli/skills/verifier.py
make test-fast
```

Remove regression markers after green.

## Risks & Mitigations

- Changing `source_hash` semantics could mark every existing LF install as drifted: verify with an LF install before/after (hash must be unchanged for LF sources — normalising LF input is a no-op, so hashing normalised bytes keeps LF hashes identical).
- Don't touch generated `.claude/`/`.agents/` copies (C-006).

## Review Guidance

- Both surfaces (doctrine skills, command skills) proven separately.
- Convergence proven for manifest-matching corrupted installs; consent path preserved.
- LF install hashes unchanged.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
