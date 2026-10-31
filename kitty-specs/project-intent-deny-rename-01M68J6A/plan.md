# Implementation Plan: The project-intent rename carries a deny entry with it

**Branch**: `kitty/mission-project-intent-deny-rename-01M68J6A` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: `kitty-specs/project-intent-deny-rename-01M68J6A/spec.md` (issue #6565)

## Summary

Extend the one project-intent rename authority
(`src/charter/activation/synthesizer/legacy_rename.py`) so its activation-token step also rewrites
stem tokens in the **deny** lists — but only on the activation ledger, and only through the ledger's
one writer, with a single new sanctioned authority `DenyListChoice.RENAME`. Then pin that origin in
the deny-list gate (`tests/architectural/test_deny_list_survives_upgrade.py`) in both directions, add
a positive control that the allowance is used, and document the fifth path (ADR `2026-10-19-1`
Decision 4, `AGENTS.md`, `docs/api/charter-commands.md`) plus an `[Unreleased]` changelog entry.

## Technical Context

**Language/Version**: Python 3.11 (`uv`, `uv.lock` pinned)
**Primary Dependencies**: `ruamel.yaml` (round-trip ledger writes), `pydantic` (synthesis manifest),
`typer` (CLI). No new dependency.
**Storage**: `.kittify/charter/activation.yaml` (the activation ledger, ADR `2026-10-19-1`); the
legacy surfaces `.kittify/config.yaml` / pointed `charter.yaml` are read-only for deny entries.
**Testing**: `pytest` (unit/regression/architectural markers). The two suites this mission answers to:
`tests/charter/synthesizer/test_legacy_rename.py` (the rename contract) and
`tests/architectural/test_deny_list_survives_upgrade.py` (the deny-list gate). `diff-cover` needs
≥90% on changed lines — the change is small and every branch gets a test.
**Target Platform**: Linux/macOS developer machines and CI (`ubuntu`, `windows` upgrade matrix).
**Project Type**: single Python package (`src/charter`, `src/specify_cli`, `src/kernel`).
**Performance Goals**: no measurable cost; the token step adds one list-key comparison per activation
write the rename already performs.
**Constraints**: the rename must stay idempotent and refuse-and-write-nothing in preflight; no raw
YAML write of a deny list; no second slug/alias mapping (C-001, C-002).
**Scale/Scope**: one helper module, one enum, one gate test module, three docs surfaces, one new
test module section. ~120 changed source lines including tests.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | The old→new stem mapping stays in `legacy_rename` (`_rename_stem` / `_target_filename`); the deny write stays in `activation_ledger.prepare_ledger_write`. Nothing new owns either fact. |
| Single canonical authority (activation) | The only writer for activation state remains `resolve_activation_write_target` → `prepare_ledger_write`; the mission adds no second write path (C-002). |
| ATDD-first | The defect is reproduced first through the pre-existing public entry point (`rename_legacy_project_intent_directive`) on a real ledger fixture, then the fix removes the red. |
| Locality of change (DIRECTIVE_024) | Four source files and their tests; no adjacency refactors. |
| Smallest viable diff | One enum member, one key-set predicate, one conditional choice, one docs paragraph per surface. |
| Tiered rigour / proportionate squad | A P2 defect in one seam: two reviewers per round (correctness + gate integrity), not the full adversarial sweep. |
| Glossary / terminology | Uses the ledger's own vocabulary: *deny entry*, *exclusion*, *activation ledger*, *write target*, `DenyListChoice`. Never bare "the ledger". |
| No fake green | Pre-existing reds are cited (#6798, #6801, #6816, #5927), never skipped. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/project-intent-deny-rename-01M68J6A/
├── spec.md              # done
├── plan.md              # this file
├── issue-matrix.json    # #6565 -> terminal verdict at wrap-up
├── traces/              # approach / design-decisions / tooling-friction
├── tasks/               # WP files (from /spec-kitty.tasks)
└── tasks.md
```

### Source Code (repository root)

```
src/charter/activation/
├── activation_ledger.py            # DenyListChoice gains RENAME (the sanctioned authority)
└── synthesizer/
    ├── legacy_rename.py            # token step: deny keys join the stem-token rewrite, one save
    └── ...                         # unchanged
src/specify_cli/upgrade/migrations/
└── m_4_0_0rc8_project_intent_directive_rename.py   # unchanged (it calls the helper)
tests/charter/synthesizer/test_legacy_rename.py     # behaviour of the deny rename
tests/architectural/test_deny_list_survives_upgrade.py  # pins + positive control
tests/specify_cli/upgrade/migrations/test_m_4_0_0rc8_project_intent_directive_rename.py  # migration-level proof
docs/adr/4.x/2026-10-19-1-activation-ledger-persists-deactivation.md  # Decision 4 + amendment
docs/api/charter-commands.md      # what the rename does to an exclusion
AGENTS.md                         # activation-ledger bullet: the fifth path
docs/changelog/CHANGELOG.md       # [Unreleased] entry
```

**Structure Decision**: single Python project; the change lands in the charter activation layer
(`src/charter/activation/**`), which may not import `specify_cli` (C-001 layer ratchet). The upgrade
migration and the CLI are callers only and stay untouched, which is what "reuse the rename authority"
means here.

## Design

### 1. The deny rename is the token step, widened by one predicate

`legacy_rename._check_tokens` / `_apply_tokens` already rewrite stem tokens of every key in
`ACTIVATION_YAML_KEYS` (the allow lists) through the resolved write target. The change:

- `_renamable_keys(data, *, include_deny)` returns the allow keys holding a legacy stem, plus — when
  `include_deny` — the `DENY_KEYS` holding one.
- `include_deny` is true only when the resolved write target **is** the activation ledger
  (`activation_ledger_path(repo_root)`), because a legacy surface's deny key is never applied
  (ADR `2026-10-19-1` Amendment 2026-10-20) and its save refuses a deny change (C-003 → C-004 in the
  spec).
- `_apply_tokens` computes `choice = DenyListChoice.RENAME if any deny key is rewritten else None`
  and hands it to the same single `save(target_path, data, deny_change=choice)` call. One write, one
  choice, no second save and no raw YAML.

`_renamed_tokens` already de-duplicates and preserves order, so "both spellings denied" collapses to
one target entry, and `prepare_ledger_write` normalises the set (sorted, unique, empty removes the
key) — no extra logic.

### 2. `DenyListChoice.RENAME` is one member, not a new mechanism

`DenyListChoice(StrEnum)` gains `RENAME = "rename"`. It is already re-exported by
`charter.activation.api`, so no public-surface change beyond the member (C-005). The docstring keeps
its "the explicit choices that may change a deny-list" statement, with the rename named as the
fifth, narrowing path (it moves an entry between two spellings; it never adds or removes a denial).

### 3. The gate pins the origin, and proves the allowance is used

`tests/architectural/test_deny_list_survives_upgrade.py`:

- `CHOICE_ORIGINS` += `("src/charter/activation/synthesizer/legacy_rename.py", "_apply_tokens", "RENAME")`.
- `DENY_CHANGE_FORWARDS` += `(same module, "_apply_tokens", "choice")`.
- `DENY_KEY_MODULES` += the same module (it names `DENY_KEYS`).
- The docstring's "no migration … changes a deny entry" becomes "no migration changes a deny entry
  except the pinned rename", with the reason.
- New positive control: the rename migration on a fixture whose deny list names the legacy stem
  changes **exactly** the expected deny entry (old → target) and leaves the other fixture entries
  alone. This is the non-vacuity pairing for the allowance: if the helper stops renaming, this fails;
  if another module mints `RENAME`, the pin fails.

The existing dynamic half (every activation-touching migration leaves deny entries unchanged) stays
as-is and keeps its own throwaway-offender test: the rename's own builder fixture has no legacy deny
entry, so it still passes unchanged, and the allowance is exercised only by the new control.

### 4. Entry points need no change

`spec-kitty charter synthesize` / `resynthesize` and the `4.0.0rc8_project_intent_directive_rename`
migration all call `rename_legacy_project_intent_directive`, so the fix reaches every window the
issue lists (migration retry, `synthesize`, `resynthesize`) without touching them. Inside the upgrade
scope a ledger project still resolves `LEDGER` (`kernel.activation_ledger_store._one_mode`:
`ledger_exists` wins over the scope), so the deny rename is not suppressed during an upgrade.

### 5. Red-first proof

New tests in `test_legacy_rename.py` fail on the current tree:

```python
def test_the_rename_carries_a_deny_entry(tmp_path):        # red on main: deny keeps the old stem
def test_a_legacy_surface_deny_key_is_left_alone(tmp_path):  # green on main, must stay green
def test_a_second_run_does_not_rewrite_the_deny_entry(tmp_path):  # idempotence
def test_other_deny_entries_are_untouched(tmp_path):       # declared id, tactic, skill
def test_a_dry_run_reports_the_deny_rewrite_and_writes_nothing(tmp_path):
```

Record the pre-fix failure of the first one in the PR body's `## Tests run`.

## Complexity Tracking

No charter violations.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Implementation Concern Map

### IC-01 — The rename authority carries the exclusion

- **Purpose**: Make the activation-token step rewrite a legacy deny stem, through the one ledger
  write, with one new sanctioned choice.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-005; NFR-001, NFR-002; C-001, C-002, C-004.
- **Affected surfaces**: `src/charter/activation/synthesizer/legacy_rename.py`,
  `src/charter/activation/activation_ledger.py` (`DenyListChoice`).
- **Sequencing/depends-on**: none.
- **Risks**: touching the legacy surface path (must stay a no-op there); the architectural pins go red
  until IC-02 lands (expected, reconciled at the tip).

### IC-02 — The gate pins the allowance and proves it is used

- **Purpose**: Keep the denial invariant absolute everywhere else, and make the one allowance
  non-vacuous.
- **Relevant requirements**: FR-004; C-003.
- **Affected surfaces**: `tests/architectural/test_deny_list_survives_upgrade.py`.
- **Sequencing/depends-on**: IC-01 (the pins name its origin).
- **Risks**: a pin added in only one direction weakens the gate; the positive control must use the
  same fixture family as the dynamic half.

### IC-03 — Contract docs and changelog

- **Purpose**: State the fifth path, its exact limit, and the user-visible fixed behaviour.
- **Relevant requirements**: FR-006.
- **Affected surfaces**: ADR `2026-10-19-1` (Decision 4 + a dated amendment),
  `docs/api/charter-commands.md`, `AGENTS.md`, `docs/changelog/CHANGELOG.md`.
- **Sequencing/depends-on**: IC-01 (the code decides the wording).
- **Risks**: the ADR is normative — it must say the rename moves an entry between spellings and never
  adds or removes a denial; AGENTS.md must not read as "synthesis can now clear a deny".
