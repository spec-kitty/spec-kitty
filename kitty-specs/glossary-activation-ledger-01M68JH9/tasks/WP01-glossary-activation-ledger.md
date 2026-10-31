---
work_package_id: WP01
title: Glossary entries, pack re-pin and code pointers
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Glossary accuracy
history:
- at: '2026-10-31T08:55:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .kittify/glossaries/
create_intent:
- tests/glossary/test_activation_ledger_terms.py
execution_mode: code_change
model: deepseek-v4.1-flash-1017
owned_files:
- .kittify/glossaries/spec_kitty_core.yaml
- packs/built-in.source.yaml
- docs/guides/how-to/governance/troubleshoot-charter.md
- docs/changelog/CHANGELOG.md
- src/charter/activation/activation_ledger.py
- src/charter/activation/resolver.py
- tests/glossary/test_activation_ledger_terms.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Glossary entries, pack re-pin and code pointers

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

## Objectives & Success Criteria

- Add the `activation ledger` term and refresh the `active charter` definition in `.kittify/glossaries/spec_kitty_core.yaml`.
- Author the identical entries in `spec-kitty-open-packs` and re-pin `packs/built-in.source.yaml`, so the fetched pack matches the seed.
- Add `docs/context/charter.md` glossary anchors to the `activation_ledger.py` and `ActiveCharterService` module docstrings.
- Correct the stale `active charter` location in `docs/guides/how-to/governance/troubleshoot-charter.md`.
- Add one `[Unreleased]` changelog entry.
- Prove the change red-first with `tests/glossary/test_activation_ledger_terms.py`, then keep the standing parity gate and the named docs gates green.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6562. Mission: `glossary-activation-ledger-01M68JH9`.
- Wording authority: `docs/context/charter.md` "Active charter" and "Activation ledger" (updated by #6496) and ADR `docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md`.
- Style bar: `spec-kitty charter context --include styleguide:kitty-glossary-writing`. One concept per definition; no circular wording; no source paths or issue numbers in the definition body; the `active charter` entry keeps the ADR `2026-10-06-1` §1 "never call the tree active" guard.
- **C-001**: `packs/built-in/` is fetched from `spec-kitty-open-packs`; never edit or commit it here. Change the upstream pack, then `spec-kitty charter pack vendor --pack built-in --ref <commit>` and `make sync-packs`.
- **C-002**: no behavioural code change; docstrings, data and docs only.
- **NFR-001**: seed and pack stay byte-identical; never relax `tests/architectural/test_glossary_pack_parity.py`.
- **C-004**: observe the focused test fail before changing the data.
- Two files, two key orders: seed uses `surface, definition, confidence, status`; pack uses `confidence, definition, status, surface` (keep `synonyms_to_avoid` on `active charter`). Compare against the existing neighbouring entries.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: `kitty/mission-glossary-activation-ledger-01M68JH9`
- **Merge target branch**: `kitty/mission-glossary-activation-ledger-01M68JH9`

## Subtasks & Detailed Guidance

### Subtask T001 – Write the failing glossary test

- **Purpose**: Pin the two definitions before changing data, so the fix has a red-first proof.
- **Steps**: Create `tests/glossary/test_activation_ledger_terms.py`. Load the seed with `ruamel.yaml` (see `tests/architectural/test_glossary_pack_parity.py` for the loader pattern). Assert:
  1. a term with `surface: activation ledger` exists, `status == "active"`, `confidence >= 0.9`;
  2. its definition names `.kittify/charter/activation.yaml`, `deactivated_`, and "Migration Ledger";
  3. the `active charter` definition names `activation ledger` and `deactivated_`, and no longer presents `.kittify/config.yaml` as the current home (it may mention it only as the legacy surface for an unmigrated project).
- **Files**: `tests/glossary/test_activation_ledger_terms.py` (new).
- **Notes**: Keep it one focused test module; no fixtures beyond the seed path. Run it on the pre-change tree and record the RED output in the commit message or PR notes.

### Subtask T002 – Add and refresh the seed terms

- **Purpose**: Make the published glossary (`kitty-specs/glossary.html`, generated from this seed) correct.
- **Steps**: In `.kittify/glossaries/spec_kitty_core.yaml`:
  - replace the `active charter` definition with the ledger-aware wording;
  - add a new `activation ledger` entry immediately after it (the glossary order is alphabetical, so place it after `activation registry`/before the next term if that reads better; keep the file's existing ordering convention).
- **Definition content** (condense, do not paste the table cell wholesale):
  - **activation ledger**: the git-tracked `.kittify/charter/activation.yaml`; single authority for what a project has activated; holds `activated_kinds`, `mission_type_activations`, the three-state `activated_<kind>` allow state and the `deactivated_<kind>` exclusions; effective set of a kind = allow minus exclusions, and an exclusion never removes an org-required id; written by `spec-kitty init`, and `spec-kitty upgrade` / `spec-kitty migrate activation-ledger` moves an older project's keys in; not the Migration Ledger (`.kittify/migration-ledger.jsonl`). Cite ADR `2026-10-19-1` and the Activation ledger entry in `docs/context/charter.md`.
  - **active charter**: the project's activated set as a whole — `activated_<kind>`, `activated_kinds` and `mission_type_activations`, plus the `deactivated_<kind>` exclusions — held in the activation ledger (ADR `2026-10-19-1`); a project not yet upgraded to 4.0.0rc8 still keeps the allow keys in `.kittify/config.yaml` or the `charter.yaml` it points to; listed by `spec-kitty charter list --json`; "active"/"inactive" alone still describe one artifact, and the `.kittify/charter/` tree is never called "active" (ADR `2026-10-06-1` §1). See the Active charter entry in `docs/context/charter.md`.
- **Files**: `.kittify/glossaries/spec_kitty_core.yaml`.
- **Notes**: Keep `confidence` and `status` (`active`) consistent with the neighbouring canonical terms.

### Subtask T003 – Author the pack entries upstream

- **Purpose**: The shipped built-in pack is the consumer copy; the seed must mirror it.
- **Steps**: Clone/enter `spec-kitty-open-packs`, branch from its `main`, and add the same two entries (pack key order) to `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`. Add an open-packs `CHANGELOG.md` `[Unreleased]` entry. Run the open-packs validation (`scripts/ci/validate-packs.sh` or the repo's documented check) and open a PR. Record the PR link and head commit.
- **Files** (upstream): `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml`, `CHANGELOG.md`.
- **Notes**: Do not merge the upstream PR. The core pin references its head commit; note the merge ordering in the core PR `## Deferred`.

### Subtask T004 – Re-pin and sync

- **Purpose**: Make `make sync-packs` fetch the updated pack.
- **Steps**: From the core repo root, run
  `spec-kitty charter pack vendor --pack built-in --ref <upstream-head-commit>`.
  Then `make sync-packs` and confirm `packs/built-in/glossary_packs/spec-kitty-core.glossary-pack.yaml` carries both entries. Re-run the focused test and `tests/architectural/test_glossary_pack_parity.py`.
- **Files**: `packs/built-in.source.yaml`.
- **Notes**: The vendoring command writes the commit, tree digest and snapshot hash; never hand-edit a digest.

### Subtask T005 – Add the docstring glossary pointers

- **Purpose**: Join the code vocabulary to the canonical glossary entry.
- **Steps**: Add one sentence to the `src/charter/activation/activation_ledger.py` module docstring: `Glossary: docs/context/charter.md#activation-ledger.` Add one to the `ActiveCharterService` module docstring in `src/charter/activation/resolver.py`: `Glossary: docs/context/charter.md#active-charter.` Match the plain `Glossary:` style used in `src/specify_cli/state/contract.py`.
- **Files**: `src/charter/activation/activation_ledger.py`, `src/charter/activation/resolver.py`.
- **Parallel?**: yes, disjoint files.

### Subtask T006 – Fix the stale guide line

- **Purpose**: The guide currently says `charter activate --preset` writes `.kittify/config.yaml`; after #6496 it writes the activation ledger.
- **Steps**: In `docs/guides/how-to/governance/troubleshoot-charter.md`, replace the parenthetical location with the activation ledger (`.kittify/charter/activation.yaml`), keeping the sentence's meaning and the existing link targets intact.
- **Files**: `docs/guides/how-to/governance/troubleshoot-charter.md`.
- **Parallel?**: yes.

### Subtask T007 – Add the changelog entry

- **Purpose**: User-visible documentation fix.
- **Steps**: Under `[Unreleased]` in `docs/changelog/CHANGELOG.md`, add one entry: bold impact-first lead with `(#6562)`, then before/after, under 1,200 characters. Follow the existing style (see the #6496 entries).
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Parallel?**: yes.
- **Notes**: Run `uv run python -m scripts.docs.check_changelog_style` if available.

### Subtask T008 – Run the gates

- **Purpose**: Prove the change and keep the docs gates green.
- **Steps**:
  - `uv run --frozen pytest -q tests/glossary/test_activation_ledger_terms.py`
  - `uv run --frozen pytest -q tests/architectural/test_glossary_pack_parity.py`
  - `uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py`
  - `uv run python -m scripts.docs.docs_index --write` (only if the diff adds a doc page; it does not, so a `--check` is enough)
  - `uv run python -m scripts.docs.freshen_adr_inventory --check`
  - `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`)
- **Files**: no new files; record the commands and counts in the PR `## Tests run`.
- **Notes**: Do not run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION). If a gate is red for a reason outside this diff, reproduce on pristine `origin/main` and cite the existing issue (#6798/#6801/#6816/#5927) rather than weakening the gate.

## Test Strategy

- **Red first**: `tests/glossary/test_activation_ledger_terms.py` fails before T002 and passes after it.
- **Standing gate**: `tests/architectural/test_glossary_pack_parity.py` fails on a seed-only change and passes after T003/T004.
- **Docs**: the named docs gates in T008.
- No compiler/typecheck change: the only Python edits are docstrings and a test module; still run `uv run --frozen ruff check` on the touched Python files.

## Risks & Mitigations

- **Pin to an unmerged upstream commit**: the operator must merge the open-packs PR first; record the ordering and the commit in `## Deferred`. If GitHub keeps the PR head reachable, the pin resolves either way.
- **Seed/pack key order**: compare with neighbouring entries before saving; a key-order change is harmless to the model but creates diff noise.
- **Glossary page churn**: the seed drives a generated page; do not hand-edit `kitty-specs/glossary.html` (it is generated, untracked).

## Review Guidance

- Verify the two definitions against `docs/context/charter.md` and ADR `2026-10-19-1`; check the `active charter` entry no longer presents the legacy location as current.
- Verify the seed and pack definitions are identical (parity test is the machine proof).
- Verify no behavioural file changed beyond docstrings.
- Verify the changelog entry is under 1,200 characters and impact-first.

## Progress & Status

- Start: record the RED test output before T002.
- After T002: focused test green; parity still red until T004.
- After T004: parity green.
- After T008: all named gates recorded; hand off to review.
