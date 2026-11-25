# Implementation Plan: Skill surfaces converge

**Branch**: `kitty/mission-skill-surfaces-converge-01M7VRS0` → lands on `issue-7700-skill-surfaces-converge` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/skill-surfaces-converge-01M7VRS0/spec.md`

## Summary

One proof source (a frozen list of every skill render Spec Kitty shipped) feeds every install surface: the user-global skill sync, the project skill installer and the retirement paths. Files proven by it are refreshed or retired; everything else is kept and reported. The user-global ownership record stops depending on a moving anchor. `doctor skills` judges command skills against the canonical render and `doctor tool-surfaces` verification sees retired-but-hash-clean entries. Leftover old-root copies are reported. The first-mission skill is renamed.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing stack only (typer, rich, ruamel.yaml, pytest); no dependency is added, upgraded or removed, so DIRECTIVE_051 has nothing to check.
**Storage**: files — `~/.kittify/cache/<owner>-assets.json` (global ownership record), `.kittify/skills-manifest.json` (project), a new package-data file `src/specify_cli/skills/data/historical_skill_renders.json`.
**Testing**: pytest, red-first per FR (C-005); fixtures use an isolated `HOME` (`tmp_path`) and real files, never the developer's home.
**Target Platform**: Linux, macOS, Windows (path handling must survive drive letters).
**Project Type**: single (CLI package under `src/`).
**Performance Goals**: NFR-001 — one JSON read per process for the render list (memoized), no git at runtime.
**Constraints**: C-001..C-005; complexity ceiling 15 per function; no new suppressions.
**Scale/Scope**: ~45 shipped skills, ~118 historical skill paths, ~560 historical blobs (~1,000 digests with SKILL.md projections).

## Charter Check

- **Single canonical authority (DIRECTIVE_044)**: one proof module (`skills/historical_renders.py`) is read by the global sync, the project installer and the retirement paths; `doctor --fix`, `upgrade` and the startup sync already share `assess_global_agent_skills` / `assess_project_skills`, so adding the proof there gives one verdict (FR-011). `doctor skills --fix` keeps using `command_installer.install` (the same `prepare_commands` the tool-surfaces provider uses); only `verify` learns the canonical render. PASS.
- **User Customization Preservation**: proof is byte equality with a shipped render or an ownership record; no name heuristic. Doctor reporting writes nothing. PASS.
- **ATDD-first / red-first**: each WP starts with a failing test committed alone (C-005). PASS.
- **Terminology**: the rename removes the last public `feature` skill id. PASS.
- **Architectural gates**: no new allowlist. The new data file ships in the wheel (built-in package data, not a pack); the packaging guard is unaffected. PASS.
- **No heavy suites in mission**: targeted dirs + `make test-fast` only. PASS.

## Project Structure

### Documentation (this mission)

```
kitty-specs/skill-surfaces-converge-01M7VRS0/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── occurrence_map.yaml     # #7725 rename (bulk-edit gate)
└── tasks/
```

### Source Code (repository root)

```
scripts/skills/build_historical_skill_digests.py     # NEW generator (git history -> JSON), union-only
src/specify_cli/skills/data/historical_skill_renders.json   # NEW frozen data
src/specify_cli/skills/historical_renders.py         # NEW reader: is_historical_render(skill, rel, sha256)
src/specify_cli/runtime/agent_skills.py              # proof in global sync; no stamp while canonical preserved; kept-file classifier
src/specify_cli/runtime/asset_preparation.py         # retire() accepts a byte proof; inventory keyed by absolute path (schema 2) + one-time schema-1 migration
src/specify_cli/skills/installer.py                  # project path: historical render counts as canonical predecessor (#2527)
src/specify_cli/skills/verifier.py                   # VerifyResult.retired (#2460)
src/specify_cli/tool_surface/providers/managed_skills.py  # _delegate_repair runs on retired entries
src/specify_cli/skills/command_installer.py          # verify(): canonical-render staleness (#5281)
src/specify_cli/cli/commands/_command_surface_doctor.py   # doctor skills / command-files: leftover old-root report; skills repair trigger
src/specify_cli/runtime/doctor.py                    # old-root leftover discovery (#7723)
src/specify_cli/tool_surface/service.py + findings.py     # global kept-skill findings in doctor tool-surfaces
src/charter/offering/skills/spk-start-first-mission/ # renamed (#7725)
src/specify_cli/skills/retired.py                    # retire spk-start-first-feature
RELEASE_CHECKLIST.md                                 # regenerate-and-commit step
docs/changelog/unreleased/                           # fragments
```

**Structure Decision**: single project; changes stay inside the existing skill/runtime/tool-surface modules.

## Complexity Tracking

No charter violations to justify.

## Implementation Concern Map

### IC-01 — Historical-render proof source

- **Purpose**: give the CLI a frozen, reviewed record of every skill render it shipped, so byte-equal old output is provably ours (#7700 ruling a, Q1=A).
- **Relevant requirements**: FR-001, C-001, NFR-001
- **Affected surfaces**: `scripts/skills/build_historical_skill_digests.py`, `src/specify_cli/skills/historical_renders.py`, `src/specify_cli/skills/data/historical_skill_renders.json`, `RELEASE_CHECKLIST.md`.
- **Sequencing/depends-on**: none
- **Risks**: data shape is per `<skill>/<relative path>` → sorted sha256 list; for `SKILL.md` it also holds today's shared and native frontmatter projection of each historical source, so a projected install matches. The generator unions with the existing file (append-only); a test fails if any current render is missing (so a skill-edit PR re-runs the generator). Reader fails closed on a missing/malformed file (no proof, never an exception at startup).

### IC-02 — Use the proof in every install surface; never certify a kept canonical file

- **Purpose**: refresh/retire proven files in the user-global sync and the project installer, and stop stamping `agent-skills.lock` while a canonical destination is preserved (#7700 a+b, #2527).
- **Relevant requirements**: FR-001, FR-002, FR-004 (retire half), FR-011, FR-012
- **Affected surfaces**: `runtime/agent_skills.py` (`_prepare_skill_tree` passes `canonical_predecessor` on a historical match; retired dirs use `retire(..., proof=...)`; stamp withheld), `runtime/asset_preparation.py` (`retire` byte proof), `skills/installer.py` (`_preserve_project_path` treats a historical render as canonical; managed drift whose bytes are a shipped render is refreshed with backup).
- **Sequencing/depends-on**: IC-01
- **Risks**: a historical render of a *different* path never counts (keyed by path). Symlinks/directories never proven. The project installer keeps its backup-before-replace.

### IC-03 — Report what was kept (doctor)

- **Purpose**: no silent keep. `doctor tool-surfaces` lists kept canonical global skill files (stale) and kept edited retired copies with reason + remedy (#7700 b, #5983); the #2527 "skipped" surfaces name why.
- **Relevant requirements**: FR-003, FR-004, FR-012
- **Affected surfaces**: `runtime/agent_skills.py` (one classifier over the assessment's dispositions: `kept_global_skill_files`), `tool_surface/findings.py` (two new append-only codes `global-skill-kept-stale`, `retired-skill-kept-edited`), `tool_surface/service.py` (append findings; severity warning).
- **Sequencing/depends-on**: IC-02
- **Risks**: finding codes are public JSON API (append-only). User-owned custom skills (non-canonical names) are not reported as stale.

### IC-04 — Repair commands agree (verify side)

- **Purpose**: `doctor skills --fix` repairs a self-consistent corrupted command skill (#5281); verification reports a hash-clean retired managed entry so the drain runs (#2460).
- **Relevant requirements**: FR-005, FR-006, FR-011
- **Affected surfaces**: `skills/command_installer.py` (`VerifyReport.outdated`: manifest hash == disk but != `canonical_digest`), `_command_surface_doctor.py` (repair trigger + payload key), `skills/verifier.py` (`VerifyResult.retired`, counted in `ok`), `providers/managed_skills.py` (`_delegate_repair` requests retired paths; outcome count).
- **Sequencing/depends-on**: none
- **Risks**: `outdated` widens the `doctor skills --json` payload (new key, additive). The `VerifyResult.ok` widening is the contract change #2460 named; `m_2_1_1.detect` inherits it (desired: it now detects the orphan).

### IC-05 — Ownership record survives a moved root

- **Purpose**: inventory entries stay valid when `CLAUDE_CONFIG_DIR` / `OPENCODE_CONFIG_DIR` / `XDG_CONFIG_HOME` moves one root outside home (#7722).
- **Relevant requirements**: FR-007, FR-008
- **Affected surfaces**: `runtime/asset_preparation.py` only (`AssetPreparation.__init__` load + `finish` store). Schema 2 stores absolute POSIX paths; in memory entries are still keyed relative to the current anchor, so `asset`/`retire`/`prune_missing` are unchanged. Entries outside the current anchor are carried through untouched.
- **Sequencing/depends-on**: none (touches the same module as IC-02's `retire`; keep edits in separate functions).
- **Risks**: schema-1 records carry no anchor. One-time migration resolves each entry against the ancestors of `$HOME` (deepest first) and takes the first whose result lies under home, the kittify home or a current root; unresolvable entries are dropped from proof (kept on disk, reported by the normal unproven path). Stated in research R-3.

### IC-06 — Leftover old-root copies are reported

- **Purpose**: with a redirected config root, list proven Spec Kitty copies under `~/.claude/{commands,skills}` with a removal hint; write nothing (#7723, Q2=A; opt-in removal is #7758).
- **Relevant requirements**: FR-009
- **Affected surfaces**: `runtime/doctor.py` (`find_old_root_leftovers(kind)`), `_command_surface_doctor.py` (`doctor command-files`, `doctor skills` print/JSON).
- **Sequencing/depends-on**: IC-01 (skills proof), IC-05 (records under the old root resolve)
- **Risks**: proof for commands = inventory record matching bytes, equality with today's render, or a canonical-predecessor marker (#4609 rule); for skills = record, today's render, or historical render. JSON for `doctor command-files` is a list today: leftovers are added as issue rows with severity `info`, so the exit code is unchanged (doctor stays advisory for them).

### IC-07 — Rename the first-mission skill

- **Purpose**: `spk-start-first-feature` → `spk-start-first-mission` (#7725), bulk-edit gated.
- **Relevant requirements**: FR-010
- **Affected surfaces**: per `occurrence_map.yaml`; `retired.py`, `test_retired_skill_completeness.py`, `tests/charter_offering/test_spk_skill_pack.py`, skill README, `spk-start-here` ("New feature" → "New Mission"), `spk-meta-skill-map` reference, `docs/api/skills/{README,spk-start-here}.md`, changelog fragment. The historical-render JSON keeps the old path as shipped history and gains the new one.
- **Sequencing/depends-on**: IC-01 (the generator must run after the rename so the new path's current render is present)
- **Risks**: `docs/development/docs-retrieval-index.yaml` is generated; never hand-edited (C-004).

## Non-goals and overlaps

#6471, #6472, #2904, #5993 are out of scope; any overlap found is noted in the PR, not fixed. No packs pin change.
