---
title: 3.2 CLI Reference Methodology
description: 'Methodology note for the 3.2 docs mission (WP05 / FR-006): the recovered procedure for generating the spec-kitty CLI reference from the live Typer surface.'
doc_status: deprecated
updated: '2026-08-12'
---

> ⚠ **Retired 2026-08-12 (`doc_status: deprecated`).** Working note for the 3.2 documentation mission `spec-kitty-3-2-docs-01KS4KSZ` (14/14 WPs done 2026-05-21); the docs are published (now 3.2.6). Content preserved as an audit-trail record.

# 3.2 CLI Reference Methodology

**Status**: Methodology note for mission `spec-kitty-3-2-docs-01KS4KSZ`, WP05.
**Authority**: Spec FR-006 (recover prior CLI reference methodology from git history).
**Companion artifacts**:
- Workspace audit: `cli-audit-3-2.md` (192 visible / 5 hidden / 2 deprecated paths; 113 of 192 visible covered today).
- Builder contract: [`contracts/build_cli_reference.md`](../../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/contracts/build_cli_reference.md).
- Deferred decision: `01KS4KTM69EG2KVX5MQ54FQ939` (hand vs hybrid vs generated mode).

This note is a curator's evidence record. It does not pick the builder mode. It documents how the existing reference was produced so WP06 (builder) and WP07 (rebuilt reference) can proceed with traceable rationale.

---

## Findings from prior commits

Four commits were inspected. All four were present in the lane worktree (`git show` exit 0 in each case).

### 1. `a14769e7a` — Add command reference docs

- **Date / author**: 2026-01-16, Robert Douglass.
- **Stat**: `docs/api/cli-commands.md` created (+362 lines); also created `docs/api/agent-subcommands.md` (+433), `docs/api/slash-commands.md` (+313), `docs/toc.yml` (+10).
- **Script / test / hook added to maintain freshness**: none. `git show --stat` lists only `docs/api/*.md` and `docs/toc.yml`; no entries under `scripts/`, `tools/`, `tests/`, or `.github/`.
- **Hand-authored vs script-generated**: hand-authored. The diff is the initial creation of the reference as a from-scratch markdown file. The prose mixes Markdown tables (`| Flag | Description |`) with hand-curated `**Examples**` and `**See Also**` cross-references — not a uniform machine template. The "Commands" overview list at top is written as a short hand-curated summary, not a verbatim dump of `--help`.
- **Representative lines from the diff** (file `docs/api/cli-commands.md`):

  ```
  +# CLI Command Reference
  +This reference lists the user-facing `spec-kitty` CLI commands and their flags exactly as surfaced by `--help`. For agent-only commands, see `docs/api/agent-subcommands.md`.
  +**See Also**: `docs/non-interactive-init.md`
  ```

### 2. `81b3d6c3e` — docs: Update CLI reference with agent subcommands

- **Date / author**: 2026-01-23, Robert Douglass (Co-Authored-By: Claude Opus 4.5).
- **Stat**: `docs/api/cli-commands.md` only (+324 lines, no other paths touched).
- **Script / test / hook added to maintain freshness**: none. Stat shows only `docs/api/cli-commands.md`.
- **Hand-authored vs script-generated**: hand-authored (LLM-assisted, per the `Co-Authored-By: Claude` trailer). The added section uses a different sectional style from the original (`### spec-kitty agent config` with `#### spec-kitty agent config list` etc., plus extended "**Behavior**", "**Side Effects**", "**Warning**" subheadings) — i.e. the structure varies from the original commit's tables, which is inconsistent with what a deterministic generator would emit.
- **Representative lines from the diff**:

  ```
  +### spec-kitty agent config
  +> **Note**: Starting in 0.12.0, agent configuration is config-driven. `.kittify/config.yaml` is the single source of truth, and migrations respect your configuration choices.
  +**Warning**: Directory deletion is permanent. Ensure you don't have custom modifications in template files before removing.
  ```

### 3. `514106af2` — docs(WP01): Add auth and sync CLI reference entries

- **Date / author**: 2026-02-05, Robert Douglass (Co-Authored-By: Claude Opus 4.5).
- **Stat**: `docs/api/cli-commands.md` only (+187 lines, no other paths).
- **Script / test / hook added to maintain freshness**: none.
- **Hand-authored vs script-generated**: hand-authored (LLM-assisted). The diff layers in three new `## spec-kitty auth …` subsections and two `## spec-kitty sync …` subsections using yet another table dialect (`| Flag | Type | Default | Description |`, four columns instead of the earlier two). The drift in column structure across commits is direct evidence that there is no single generator template.
- **Representative lines from the diff**:

  ```
  +- `auth` - Authentication commands for the sync service
  +| `--username`, `-u` | TEXT | (prompt) | Your username or email |
  +> **Note**: This command reference is based on the planned interface. Verify against `spec-kitty sync now --help` when the command is available.
  ```

The third line is especially telling: the human author explicitly notes the section is documentation of a planned interface rather than verified `--help` output. A generator would have refused to write the section at all.

### 4. `deee8d7f3` — docs: refresh site for 1.0 release and current CLI (#170)

- **Date / author**: 2026-02-25, Robert Douglass (PR #170).
- **Stat**: `docs/api/cli-commands.md` (-281 / +many) plus `docs/guides/install-and-upgrade.md`, `docs/guides/install-spec-kitty.md`, `docs/index.md`. No `docfx.json` change is present in this commit; the truncated stat shows only docs/* files, no `scripts/`, `tools/`, `tests/`, or `.github/` entries.
- **Script / test / hook added to maintain freshness**: none.
- **Hand-authored vs script-generated**: hand-authored. The diff manually inserts `## spec-kitty specify`, `## spec-kitty plan`, `## spec-kitty tasks`, and `## spec-kitty context`, while manually deleting the `## spec-kitty auth*` and `## spec-kitty sync now|status` sections that were added only 20 days earlier in commit 3 — exactly the kind of brittle, drift-prone editing a generator would have made unnecessary. The "Commands" overview list at the top is also edited by hand (additions interleaved among existing bullets, one bullet removed).
- **Representative lines from the diff**:

  ```
  -- `auth` - Authentication commands for the sync service        (removed)
  +- `specify` - Create a feature scaffold in `kitty-specs/`       (added)
  +- `context` - Query workspace context information               (added)
  -**Synopsis**: `spec-kitty sync now [OPTIONS]`                   (entire section removed)
  ```

---

## Classification

**Hand-authored** (LLM-assisted from commit 2 onward).

Justification, citing the four commits:

1. **No generator script ever shipped.** Across all four commits the `--stat` output mentions only `docs/api/*.md`, `docs/toc.yml`, and other prose markdown files. No path under `scripts/`, `tools/`, `tests/`, or `.github/workflows/` is touched by any of the four commits. A test-validated or generated approach would have required a checked-in producer or validator.
2. **Structural drift across commits.** Three different table shapes appear across the four commits (two-column "Flag | Description" in commit 1; expanded "Synopsis / Description / Behavior / Side Effects / Warning" prose in commit 2; four-column "Flag | Type | Default | Description" in commit 3). A deterministic generator does not emit three layouts for the same artifact.
3. **Manual deletion of stale content.** Commit 4 removes the entire `spec-kitty auth*` and `spec-kitty sync now|status` sections by hand — sections that were added only 20 days earlier in commit 3. A generator would have re-derived the surface; the human had to chase the drift.
4. **Explicit "planned interface" caveat.** Commit 3 includes the line `> **Note**: This command reference is based on the planned interface. Verify against spec-kitty sync now --help when the command is available.` That is direct prose evidence of speculative hand authorship, not generator output.
5. **The `cli-audit-3-2.md` author's independent conclusion.** The workspace audit (read-only, no opinion of this curator) states: *"The old CLI reference methodology appears to have been hand-authored from `--help` output. The commits above add or modify markdown directly; I did not find a checked-in generator that rebuilds `docs/api/cli-commands.md` from the Typer app."*

The methodology is therefore **hand-authored**, not "semi-generated", "generated", or "test-validated".

---

## Existing freshness checks

Search commands run from the lane worktree root:

```bash
grep -rn "cli-commands" tests/
grep -rn "cli-commands" .github/
grep -rn "reference/cli" scripts/
grep -rn "cli-commands" scripts/
grep -rn "agent-subcommands" tests/ .github/ scripts/
```

**Findings**:

- `tests/contract/test_terminology_guards.py:279` references `docs/api/cli-commands.md`.
- `tests/contract/test_terminology_guards.py:283` references `docs/api/agent-subcommands.md`.
- `.github/`: **none found**.
- `scripts/`: **none found** for either `reference/cli` or `cli-commands`.

**Scope of the one check that exists** (read-only inspection of `tests/contract/test_terminology_guards.py` lines 270–310, function `test_reference_examples_match_runtime_requirements`):

The test asserts only **negative invocation patterns** — specific forbidden example lines that must NOT appear in the reference (e.g. `spec-kitty next --json`, `bare call (no --agent)`, and ~25 forbidden `spec-kitty agent ...` example strings). Its docstring reads: *"Reference docs must not teach invocation patterns that now hard-fail. Authority: spec.md FR-010, FR-013, FR-022."*

It is **not** a coverage check: it does not enforce that any particular command appears, does not compare against the live Typer surface, and would pass on a file that omitted 100% of the CLI as long as no forbidden example string was present.

**Conclusion**: there is exactly **one** check guarding the reference today, and its scope is anti-regression for ~27 forbidden example strings — not freshness or coverage. The reference can drift arbitrarily out of sync with the Typer app without any current test failing.

---

## Why the 3.2 builder is justified

From `cli-audit-3-2.md` (workspace audit):

- 192 visible command/group paths exist in the live Typer surface (run with `SPEC_KITTY_ENABLE_SAAS_SYNC=1 SPEC_KITTY_NO_UPGRADE_CHECK=1`).
- 113 of 192 visible paths are covered by existing reference headings or inline command mentions.
- **79 visible paths are not explicitly covered.** That is a 41% gap.

Combined with the findings above — no generator, no coverage check, three drifting table shapes, manual deletion of stale sections, and a single negative-pattern test — the existing methodology cannot close that 41% gap or prevent the next round of drift. A deterministic builder that walks the Typer app and emits coverage proportional to the live surface is the minimum mechanism needed to satisfy FR-006/FR-007/FR-008.

The builder does not eliminate prose: the deferred decision `01KS4KTM69EG2KVX5MQ54FQ939` keeps the choice between `hand`, `hybrid`, and `generated` modes open. Even in `hand` mode the builder still emits the deprecation/internal classification table, which is the smallest unit of mechanical coverage that the four prior commits did not produce.

---

## Builder design summary

The builder design is fully specified in [`contracts/build_cli_reference.md`](../../../../kitty-specs/spec-kitty-3-2-docs-01KS4KSZ/contracts/build_cli_reference.md). Key points for this methodology note (no re-documentation of the contract):

- Entry point: `scripts/docs/build_cli_reference.py`.
- Walks `specify_cli.app` (Typer) read-only with `SPEC_KITTY_ENABLE_SAAS_SYNC=1` and `SPEC_KITTY_NO_UPGRADE_CHECK=1` set before import.
- Per-path `--help` capture via subprocess for isolation.
- `--mode {generated, hybrid, hand}` flag (default `hybrid`) lets WP06/WP07 implement the deferred decision without re-touching the builder.
- Refuses to overwrite files with uncommitted edits (`exit code 3`), preventing accidental loss of in-flight reviewer prose.

See the contract for inputs, outputs, exit codes, guarantees, non-guarantees, test fixtures, and error taxonomy.

---

## Decision-defer note

The choice between `hand`, `hybrid`, and `generated` modes is deferred decision **`01KS4KTM69EG2KVX5MQ54FQ939`**. The plan default is `hybrid`.

This methodology supports any of the three modes:

- **`hand`** — the methodology shows that hand authorship has been the practice from 2026-01-16 onward and produced a 41% coverage gap plus three table-style dialects. If the decision is `hand`, the builder still adds the deprecation/internal classification table (the one piece of mechanical coverage the prior workflow never had).
- **`hybrid`** — generated block for the command tree, hand-authored prose preserved outside the block. This mode is consistent with the existing reference's mixed prose-and-table character while closing the 79-path coverage gap.
- **`generated`** — full generation between `<!-- BEGIN GENERATED -->` / `<!-- END GENERATED -->` markers, no hand prose inside. This mode would require migrating the existing hand-authored prose (examples, behavior notes, warnings) into adjacent files or accepting their deletion.

WP06 implements the builder against all three modes. WP07 picks the mode used to rebuild `docs/api/cli-commands.md` and `docs/api/agent-subcommands.md`. This methodology note does not pick.
