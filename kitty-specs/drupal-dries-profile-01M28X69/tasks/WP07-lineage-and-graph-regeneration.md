---
work_package_id: WP07
title: Lineage and graph regeneration
dependencies:
- WP02
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- FR-005
- NFR-002
- NFR-003
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
created_at: '2026-09-11T19:28:35+00:00'
subtasks:
- T034
- T035
- T036
- T037
- T038
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/
create_intent: []
execution_mode: code_change
owned_files:
- src/charter/offering/drg/migration/extractor.py
- packs/built-in/agent_profile.graph.yaml
- packs/built-in/styleguide.graph.yaml
- packs/built-in/toolguide.graph.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Lineage and graph regeneration

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objective

The integration package. Add the one Python entry that mints Dries's lineage, regenerate every graph
fragment, prove freshness, and turn WP01's failing tests green.

This WP is the **sole owner** of `*.graph.yaml` and of `extractor.py`. Every other package was
forbidden from regenerating precisely so that this diff is attributable.

## Context

- **Spec**: FR-005, NFR-002, C-002
- **Research**: R-001 (why lineage is Python), R-002 (why fragments are generated), R-003 (the wrong-pack trap)
- **Data model**: [data-model.md](../data-model.md) E3 and E7, invariants I3.1–I3.3, I7.1–I7.3
- **Contract**: [contracts/profile-contract.md](../contracts/profile-contract.md) C-P2, C-P3, C-P4, C-P5

### Why this exists as its own package

`specializes_from` for a built-in profile cannot be declared in YAML. The extractor's own comment is
explicit — the per-profile `specializes-from` field "has been retired (and is rejected by the profile
model), so these edges are the single source of lineage truth." The table is the only mechanism.

Touching `src/charter/offering/` pulls **both** `tests/charter/` and `tests/doctrine/` into the blast
radius, per CLAUDE.md's blast-radius rule — the doctrine test tree did not move when the package
absorbed `src/doctrine/`.

### Expected inbound state

`regenerate-graph --check` will report **stale** when you begin. That is correct: WP02–WP06 added
source artifacts and were forbidden from regenerating. Your job is to make it fresh again, with the
fragments reflecting all of it.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP07`.

---

### Subtask T034: Add the lineage entry

**Purpose**: FR-005. Six lines of Python that make Dries inherit implementer discipline.

**Steps**:

1. Open `src/charter/offering/drg/migration/extractor.py` and find `_CURATED_ARTIFACT_EDGES`
   (around line 267). Read the comment above it before editing — it explains the cutover.
2. Add the entry beside the four existing specialists, matching their formatting exactly:

   ```python
   (
       "agent_profile:drupal-dries",
       _AGENT_PROFILE_IMPLEMENTER_IVAN,
       Relation.SPECIALIZES_FROM,
   ),
   ```

3. Place it adjacent to the `frontend-freddy` entry so the four specialists stay grouped (I3.3). Do
   not reorder existing entries.
4. Confirm the endpoint form is `<kind>:<id>` (I3.1). Anything else is refused at merge with
   `unresolved_edge_endpoint` — and CLAUDE.md records a case where a wrongly-shaped endpoint was
   dropped *in silence*, leaving a documented declaration inert.

**Files**: `src/charter/offering/drg/migration/extractor.py` (+6 lines)

**Validation**:
- [ ] Entry added, formatting matches its neighbours
- [ ] No existing entry reordered or modified
- [ ] `uv run ruff check src/charter/offering/drg/migration/extractor.py` clean
- [ ] `uv run ruff format --check src/charter/offering/drg/migration/extractor.py` clean

---

### Subtask T035: Regenerate the fragments

**Purpose**: R-002. Fragments are generated output.

**Steps**:

1. **Run through the repository's code.** A globally installed `spec-kitty` regenerates the pack
   inside its own venv and will report success while changing nothing here:
   ```bash
   uv run spec-kitty doctrine regenerate-graph
   ```
2. Read the output path. It must be `/Users/nicolas/Projects/spec-kitty/packs/built-in`. If it names
   a `pipx` or site-packages path, stop — you ran the wrong binary and the repository is untouched.
3. Run it a second time. Regeneration is deterministic: the second run must produce byte-identical
   output and leave `git status` unchanged after the first.

**Validation**:
- [ ] Output path is the repository's pack
- [ ] Second run produces no further diff (determinism)

**Edge case**: if the run reports dropped or unresolved endpoints, do **not** hand-patch the
fragments. The source artifact is wrong — fix the profile's `directive-references` or
`tactic-references` in WP02's file and regenerate. Note that as an out-of-map edit with a one-line
rationale.

---

### Subtask T036: Prove freshness and review the diff

**Purpose**: C-P4, I7.1. The gate that makes the whole scheme trustworthy.

**Steps**:

1. ```bash
   uv run spec-kitty doctrine regenerate-graph --check
   ```
   Must exit 0, against the repository's pack.
2. Review the fragment diff deliberately — this is a generated diff, and generated diffs are exactly
   where unrelated drift hides:
   ```bash
   git diff --stat packs/built-in/*.graph.yaml
   git diff packs/built-in/agent_profile.graph.yaml
   ```
3. Confirm the diff contains **only**:
   - 4 new nodes: `agent_profile:drupal-dries`, `styleguide:drupal-conventions`,
     `styleguide:drupal-security-performance`, `toolguide:drupal-review-checks`
   - the lineage edge to `implementer-ivan`
   - 6 `requires` edges to directives, 4 to tactics
   - 3 `suggests` edges from the styleguides (C-S7)
4. Anything else in the diff is either drift that predates you — compare against WP01's recorded
   baseline — or a side effect worth understanding before committing. Do not wave it through.

**Validation**:
- [ ] `--check` exits 0
- [ ] Diff contains only the expected nodes and edges
- [ ] Any unexpected line explained in the WP notes

---

### Subtask T037: Confirm zero skipped profiles

**Purpose**: NFR-002, C-P1.

**Steps**:

1. ```bash
   uv run spec-kitty doctor doctrine --json > /tmp/doctrine-after.json
   ```
2. Diff against WP01's `/tmp/doctrine-baseline.json`. Skipped count must still be 0, and the profile
   total must have risen by exactly 1.
3. If Dries appears in `skipped_profiles`, the profile YAML is malformed — read the reported reason
   rather than guessing. That diagnostic is exactly what FR-013 exists to provide.

**Validation**:
- [ ] 0 skipped profiles
- [ ] Profile total +1
- [ ] Dries resolvable via the profile listing

---

### Subtask T038: Turn WP01's tests green

**Purpose**: Close the red-first loop.

**Steps**:

1. ```bash
   uv run pytest tests/doctrine/agent_profiles/test_drupal_dries_profile.py \
                 tests/doctrine/drg/test_drupal_dries_lineage.py \
                 tests/doctrine/styleguides/test_drupal_styleguide_presence.py -q
   ```
   All must pass.
2. Run the blast radius that touching `src/charter/offering/` requires:
   ```bash
   uv run pytest tests/doctrine/ tests/charter/ -q
   ```
3. Baseline:
   ```bash
   make test-fast
   ```
4. Classify any failure against CLAUDE.md's baseline-red categories before recording it. A failure
   that is red on your branch **and** green on the base is yours; nothing else is.
5. Record every command and its pass/fail counts — WP08 needs them for the PR's *Tests run* section.

**Validation**:
- [ ] Three WP01 test files green
- [ ] `tests/doctrine/` and `tests/charter/` green, or every failure classified
- [ ] `make test-fast` green, or failures classified
- [ ] Commands and counts recorded

---

## Definition of Done

- [ ] One lineage entry added; no existing entry disturbed
- [ ] Fragments regenerated from repository source, deterministically
- [ ] `regenerate-graph --check` exits 0 against the repository pack
- [ ] Fragment diff contains only this mission's 4 nodes and their edges
- [ ] 0 skipped profiles; total +1
- [ ] WP01's three test files green
- [ ] `tests/doctrine/` + `tests/charter/` + `make test-fast` green or classified
- [ ] `ruff check` and `ruff format --check` clean on the touched Python
- [ ] Commands and counts recorded for WP08

## Risks

| Risk | Mitigation |
|------|-----------|
| Running a global `spec-kitty` — regenerates the wrong pack, reports success | T035 requires reading the output path. Verified to happen; see R-003 |
| Hand-patching a fragment to fix an endpoint error | Fix the source artifact and regenerate. A hand-edit fails `--check` identically to staleness |
| Unrelated drift riding in on a generated diff | T036 compares against WP01's baseline rather than trusting the diff |
| Missing `tests/charter/` because the change "looks like doctrine" | The blast-radius rule names both trees for `src/charter/offering/**` |

## Reviewer Guidance

The Python diff should be six lines. If it is larger, ask why. Then read the fragment diff and count
the new nodes — exactly four, no more. Confirm the WP notes record the `--check` output **including
the path**, since a green check against a pipx pack is worthless. Verify the recorded test commands
were run through `uv run` and not a stale global binary.
