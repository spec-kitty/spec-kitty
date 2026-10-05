---
work_package_id: WP05
title: Pure decision cores, wired in place
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-003
- FR-009
- NFR-001
- NFR-003
- C-001
- C-003
planning_base_branch: issue-5634-mission-creation-degod
merge_target_branch: issue-5634-mission-creation-degod
branch_strategy: Planning artifacts for this mission were generated on issue-5634-mission-creation-degod. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5634-mission-creation-degod unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
- T022
- T023
- T024
- T025
phase: Phase 2 - Decision cores and the split
history:
- at: '2026-10-04T20:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/core/
create_intent:
- tests/core/test_mission_creation_probe_order.py
- src/specify_cli/core/mission_creation_decisions.py
- tests/core/test_mission_creation_decisions.py
- tests/core/test_mission_creation_purity.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/core/mission_creation.py
- src/specify_cli/core/mission_creation_decisions.py
- tests/core/test_mission_creation_decisions.py
- tests/core/test_mission_creation_purity.py
- tests/core/test_mission_creation_probe_order.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – Pure decision cores, wired in place

## ⚡ Do This First: Load Agent Profile

Run `spec-kitty agent profile show python-pedro` (skill `spk-doctrine-profile-load` / `/ad-hoc-profile-load`) and `spec-kitty charter context --action implement --json`, then apply them. Also load the refactoring tactics: `spec-kitty charter context --include tactic:refactoring-extract-first-order-concept` and `--include tactic:refactoring-strangler-fig`.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log and the Activity Log for returned feedback.

---

## Objectives & Success Criteria

Introduce `src/specify_cli/core/mission_creation_decisions.py`, the **only pure module** of the family, and make the existing functions in `mission_creation.py` delegate to it **in place**, using the strangler pattern. No function moves to another module in this WP; that is WP06.

Done means:

- Every core listed in `data-model.md` exists as a pure function over frozen dataclass inputs, and each is **called from the production path**.
- The cores delegate rule content to the existing authorities (`ProtectionPolicy.is_protected_target`, `topology_mints_coordination_branch`, `mission_branch_name`, `classify_topology`) and never re-encode them (spec FR-003, doctrine finding).
- The coordination-routed predicate has **one** definition, and its three former copies (~:1312 `_scaffold_mission_dir`, ~:1874 `_build_create_result`, ~:2020 `_seed_coord_surface_for_create`) call it (FR-009).
- Unit tests in `tests/core/test_mission_creation_decisions.py` pin every branch of every core with plain inputs. They use **no git repo, no tmp files, no monkeypatch**.
- A purity check in `tests/core/test_mission_creation_purity.py` AST-scans `mission_creation_decisions.py` and fails on any import of, or attribute use from:
  - `subprocess`, `os`, `shutil`, `pathlib.Path` I/O methods (`read_text`, `write_text`, `exists`, `iterdir`, `glob`, `rglob`, `mkdir`, `unlink`, `open`);
  - `kernel.clock`, `ulid`, `datetime.now`, `time`;
  - `specify_cli.core.git_ops`, `kernel.git`, `specify_cli.git.commit_helpers`, `specify_cli.git.ref_advance`, and any other `specify_cli.git` module at **runtime**. Type-only imports under `if TYPE_CHECKING:` are allowed (for example the `ProtectionPolicy` type).

  It has a planted positive control (an in-memory source containing `import subprocess` is flagged).
- **Error timing is unchanged (C-001).** Every probe that can raise runs at the same point and in the same order as today. The golden matrix from WP01 (including the malformed-protection-config cell) and WP02 pass with **0 edits** to their files, as do the WP03 tests.
- One planted break per core (for example flipping a comparison inside it) turns at least one golden, WP03 or end-to-end test red. This is recorded in the Activity Log and proves each core is wired.
- `mypy` and `ruff` are clean, complexity ≤ 15, and no new `noqa`.

## Context & Constraints

- Design: `kitty-specs/mission-creation-degod-01M44467/data-model.md` (types and signatures), `research.md` R-4 (error timing), `research/code-grounding.md` Appendix A §1.1 (decision inputs, line refs).
- **Message text is byte-identical.** Move the f-strings into the core verbatim, or keep them in the adapter and have the core return a reason enum. Choose one per core and stay consistent. The golden matrix compares messages exactly.
- **Error class identity is unchanged.** `MissionBranchExistsError` stays raised for the branch-exists refusal (its `error_code = "MISSION_BRANCH_EXISTS"`). The decision returns a `Refuse(kind=...)` value, and the adapter maps it to the existing class. Do not import the error classes into the pure module unless they are plain classes with no I/O (they are; importing them from `mission_creation` would create a cycle, so in this WP define the mapping in `mission_creation.py`).
- Protected-mint facts must be **gathered in today's probe order and stop at the first fact that decides a refusal**. Use `None` for "not reached" in the facts dataclass:
  1. applies (protection resolution)
  2. target has a commit
  3. dirty-outside-scaffold (`status_entries`; it may raise `GitCommandError`, which must still propagate at that point)
  4. branch exists

  The decision function must treat `None` as "not evaluated, so a refusal is decided earlier". Write a unit test for each prefix.
- `_target_is_protected` keeps resolving `ProtectionPolicy.resolve(write_root)` and `resolve_primary_branch(write_root, bias=False)` in the adapter. The core `target_is_protected(policy, target_branch, primary_branch)` only calls `policy.is_protected_target(...)`. Name the parameter `primary_for_protection` (follow-up: #5707).
- `_protected_mint_applies` keeps its signature (tests may call it) and delegates to `protected_mint_applies(topology, commit_to_target, target_protected)`.
- **Keep both `commit_to_target` sources** (spec edge case): the recreate guard reads the parameter; the mint reads `read_commit_to_target(meta)`. Do not unify them.
- Meta flag patch: `meta_flag_patch(...)` returns only the True keys. The caller inserts them **at the same point and in the same order** as today, because key order in `meta.json` is captured by the golden matrix (`meta_key_order`).
- Duplicates: the adapter loads candidates (`_list_mission_scaffolds`, `load_meta_fail_closed`, abandonment probes) **lazily in today's order**, because `_prior_mission_is_abandoned` runs only for type-matching candidates. Keep that laziness: either the core takes an iterator of candidates whose abandonment is computed lazily, or the adapter loop stays and calls small pure predicates per candidate (`candidate_matches(...)`). Prefer the second; it is the smaller change.
- `_failure_is_disposable_create_refusal` is already pure. Move it into the decisions module and keep the old name in `mission_creation.py` as a thin delegate, because tests patch or import it.
- C-003 / strangler: existing private function names and signatures in `mission_creation.py` stay, because tests import 15 private symbols. Only their bodies delegate.
- Do not touch the CLI module, `implement` modules or any test file outside `owned_files`.

## Branch Strategy

- **Strategy**: populated by finalize-tasks · **Planning base**: `issue-5634-mission-creation-degod` · **Merge target**: `issue-5634-mission-creation-degod`

## Subtasks & Detailed Guidance

### Subtask T018 – Decisions module skeleton + protection cores

- Create `mission_creation_decisions.py` with a module docstring stating "Pure. No git, filesystem, subprocess, environment, clock or ULID access (spec FR-003). Guarded by tests/core/test_mission_creation_purity.py." Declare `__all__`.
- Add `target_is_protected(policy, target_branch, primary_for_protection) -> bool` and `protected_mint_applies(topology, commit_to_target, target_protected) -> bool`.
- Wire `_target_is_protected` and `_protected_mint_applies` to delegate.
- Unit tests: a truth table for `protected_mint_applies` (all 4 topologies × commit_to_target × protected). For `target_is_protected`, build a real `ProtectionPolicy` value: read `src/specify_cli/git/protection_policy.py` for a constructor that needs no I/O.

### Subtask T019 – Protected-mint facts and decision

- Types: `ProtectedMintFacts` (fields per `data-model.md`, with `None` meaning "not reached"), and `NoMint | Refuse | Mint`.
- `decide_protected_mint(facts) -> ProtectedMintDecision`.
- Restructure `_mint_protected_single_branch_mission_branch` into gather (probes in order, stopping early), then decide, then apply (raise the mapped error, or run `checkout -b` and record `meta["mission_branch"]`). The `checkout -b` failure path (WP03 row 2) stays in the adapter with its message unchanged.
- Unit tests: every prefix of the facts sequence, plus the exact message strings (copy them from the source).

### Subtask T020 – Coordination-routed predicate

- `is_coordination_routed(topology, *, owned: bool, ...)`. Read the three copies first. If they differ (for example one also checks a skip flag), the core takes the union of inputs and each call site passes what it has. **Prove** that each call site's result is unchanged: write a small table test per call site's input domain.
- It wraps `topology_mints_coordination_branch` (from `specify_cli.missions._create`; check that module for import-time I/O first, and if it has any, import the function lazily inside the core is **not** allowed; instead pass the bool in).

### Subtask T021 – Meta flag patch

- `meta_flag_patch(pr_bound, retain_branches, retain_worktrees, commit_to_target) -> dict[str, bool]` with insertion order preserved. Wire it into `_build_create_meta` where those keys are written today (~:1452-1461), keeping the position relative to the other keys.

### Subtask T022 – Duplicate match + abandonment

- `is_abandoned(*, wp_lanes: Mapping[str, str], event_count: int, spec_tracked: bool) -> bool`. The read-failure case stays in the adapter: `StoreError` maps to "live", as today.
- `candidate_name_matches(name, base_slug) -> tuple[bool, str]` (match, candidate_mid8), using the same regex as today. Move `_MID8_DIR_SUFFIX_PATTERN` usage there, verbatim.
- `is_same_mission_type(candidate_meta, mission_type)` with today's default of `"software-dev"`.
- The adapter loop in `_find_live_duplicate_mission` keeps its order and its fail-closed returns.

### Subtask T023 – Rollback cores

- `plan_orphan_scaffold_removal(*, post_names, pre_names, mission_slug, tracked: frozenset[str]) -> tuple[str, ...]`. Keep the neighbour regex verbatim. The adapter computes `tracked` for the candidate names only, in sorted order. To keep the exact git calls, the adapter may query tracking per candidate exactly as today, then pass the results in.
- `coord_rollback_action(*, created, pre_seed_tip, current_tip) -> Delete | CasReset | Noop`. Wire `_rollback_coordination_surface` so its effects (rmtree, teardown, prune, then delete or CAS reset) run in the same order.
- `is_disposable_create_refusal(exc)` needs the `specify_cli.git.commit_helpers` exception types. It stays in the **adapter**. If you want a pure part, the adapter maps the exception to an enum and the core decides on the enum.

### Subtask T024 – Scaffold-commit outcome + file sets

- `classify_scaffold_commit_failure(kind: CommitFailureKind) -> Literal["skip", "already_exists", "raise"]` mirrors the except-ladder in `_commit_create_scaffold`; the **adapter** maps exception types to `CommitFailureKind` (exception types live in `specify_cli.git`, which is banned at runtime in the pure module). The adapter still catches the same exception types in the same order. Simplest: keep the `except` clauses and call the classifier inside one `except (A, B, C)`, only if that preserves behaviour exactly. Otherwise keep the ladder and extract only the bootstrap-skip reason mapping.
- `created_file_sets(...)`: the pure part of `_build_create_result` (~:1874-1890).

### Subtask T025 – Purity check + per-core wiring evidence

- `tests/core/test_mission_creation_purity.py`: the AST ban list from the objectives, plus a planted positive control (parse a source string containing `import subprocess` and `Path("x").read_text()` and expect 2 findings).
- Planted break per core (in your worktree, never committed): flip one condition per core, run the golden, WP03 and decisions tests, confirm at least one red outside `test_mission_creation_decisions.py`, and revert. Record core → failing test ids in the Activity Log.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_purity.py -q
PWHEADLESS=1 .venv/bin/python -m pytest tests/core/test_mission_creation_golden_*.py tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py \
  tests/specify_cli/cli/commands/agent/test_mission_create_topology_fallback.py tests/core/test_mission_creation_branch_coverage.py tests/core/test_mission_creation_invariants.py -n 4 --dist loadfile -q
git diff <lane-base> -- tests/core/golden tests/core/test_mission_creation_golden_* tests/core/_mission_create_golden.py tests/specify_cli/cli/commands/agent/golden tests/specify_cli/cli/commands/agent/test_mission_create_golden_cli.py   # must be empty
PWHEADLESS=1 .venv/bin/python -m pytest $(grep '^tests/' <(sed -n '/^## Appendix — covering test set/,/^```$/p' kitty-specs/mission-creation-degod-01M44467/research/test-remediation.md)) -n 4 --dist loadfile -q
uv run --frozen ruff check src/specify_cli/core/mission_creation*.py tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_purity.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/core/mission_creation*.py tests/core/test_mission_creation_decisions.py tests/core/test_mission_creation_purity.py
uv run --frozen ruff check --select C901 src/specify_cli/core/mission_creation*.py
.venv/bin/mypy src/specify_cli/core/mission_creation.py src/specify_cli/core/mission_creation_decisions.py
.venv/bin/python -m pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_single_mission_surface_resolver.py tests/architectural/test_no_write_side_rederivation.py -q
make test-fast
```

Baseline reds to classify, not chase: baseline-red #5705, #5706.

## Risks & Mitigations

- **Message drift**: the golden matrix catches it. Never edit the golden files.
- **Earlier probe = different residue** (#5704 shape): gather lazily and stop early.
- **Dead-symbol gate**: a new public name in `__all__` with no caller in `src/` is reported dead. Every core must have a production caller. Keep helper-only functions private (leading underscore) or remove them.
- **Import cycle**: `mission_creation_decisions` must not import `mission_creation`.

## Review Guidance

- AST-check the decisions module yourself (`rg -n "^import|^from" src/specify_cli/core/mission_creation_decisions.py`).
- Each core's planted break is listed with the failing test ids. Re-run two.
- The golden and WP02/WP03 files are byte-identical to the lane base.
- No re-encoded authority: grep for `protected_branches`, `kitty/mission-` and `COORD`/`LANES_WITH_COORD` literals inside the decisions module. Each must be absent or justified.

## Post-tasks squad folds (binding; they supersede conflicting text above)

1. **Purity ban scope**: runtime imports of I/O-bearing modules are banned (see the list in Objectives). `TYPE_CHECKING` type imports are allowed. Exception classification stays in adapters. The `target_is_protected` core takes the policy as a structural `Protocol` exposing the real `is_protected_target` signature (check it), or as a `TYPE_CHECKING`-only type.
2. **Dead-symbol gate** (`tests/architectural/test_no_dead_symbols.py` scans all of `src/`): every public name in the decisions module needs an importer in `src/`. The decision variants (`NoMint`/`Refuse`/`Mint`/`Delete`/`CasReset`/`Noop`) must be imported by the adapter, which uses them in `isinstance`/`match`; otherwise keep them private and out of `__all__`. Run the gate.
3. **Probe-order proof** (new file `tests/core/test_mission_creation_probe_order.py`, owned by this WP): for each protected-mint refusal cell (target without commit, dirty, branch exists) and the success cell, run the create on a real repo with `GIT_TRACE=<tmpfile>` (`monkeypatch.setenv` is an environment change, not a module patch). Assert the ordered sequence of git subcommands on the mint path **stops at the deciding probe**. Capture the sequence on the WP05 lane base first and assert equality after wiring. This proves "today's order, stopping early".
4. **T020 correction**: only ~:1312 (`_scaffold_mission_dir`) and ~:2020 (`_seed_coord_surface_for_create`) are topology-based copies. ~:1874 (`_build_create_result`) keys on `status_log_path`/owned. FR-009's "one definition" applies to the topology-based predicate; the ~:1874 site keeps its own condition unless a table test proves it identical over its input domain.
5. Record planted breaks as `git diff` patch blocks in the Activity Log.

## Activity Log

- 2026-10-04T20:00:00Z – system – Prompt created
