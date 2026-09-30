---
work_package_id: WP01
title: Validated ownership fact and gate harness
dependencies: []
requirement_refs:
- FR-001
- NFR-006
- C-003
planning_base_branch: claude/sleepy-hamilton-5lelee
merge_target_branch: claude/sleepy-hamilton-5lelee
branch_strategy: Planning artifacts for this mission were generated on claude/sleepy-hamilton-5lelee. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/sleepy-hamilton-5lelee unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Foundation
history:
- at: '2026-09-28T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/mission_runtime/
create_intent:
- src/mission_runtime/owned_checkout.py
- tests/mission_runtime/test_owned_checkout.py
- tests/architectural/_owned_checkout_scan.py
- tests/architectural/test_owned_checkout_gate_selftest.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/mission_runtime/owned_checkout.py
- src/mission_runtime/__init__.py
- tests/mission_runtime/test_owned_checkout.py
- tests/architectural/_owned_checkout_scan.py
- tests/architectural/test_owned_checkout_gate_selftest.py
- tests/architectural/test_mission_runtime_surface.py
- .github/workflows/ci-windows.yml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Validated ownership fact and gate harness

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`, and read `.kittify/charter/charter.md` if this session has not read it yet.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

This WP lays the foundation every later WP builds on. It adds **no behaviour change** to any command.

1. A new value object `mission_runtime.OwnedCheckout` exists. It is the *validated ownership fact* of spec §Key Entities and data-model.md §OwnedCheckout. It can only be constructed through a private `OwnedCheckout._mint(...)`; direct construction raises `TypeError`.
2. `OwnedCheckout` carries the transitional legacy property names (`primary`, `root`, `directory`, `slug`, `target`), each marked `# TRANSITIONAL(WP18): <reason>`, so the object that WP02's transitional `OwnedMission` legacy factory function mints satisfies the ~104 attribute read sites untouched. WP18 deletes these properties (plan §Staging Strategy: the six shared seams plus every other function marked TRANSITIONAL(WP18)).
3. `OwnedCheckout` is on the `mission_runtime` package root (`__all__`) and pinned in `_PUBLIC_SURFACE` of `tests/architectural/test_mission_runtime_surface.py` (MR-1/MR-2 forbid submodule imports).
4. Carrier unit tests cover the invariants, `files()` containment (including symlink escape and symlink loops), one explicit symlink identity case and one case-variant identity case (NFR-006). The case-variant test is marked `windows_ci` and its file is added to the `ci-windows.yml` path filter.
5. A reusable AST scanner, `tests/architectural/_owned_checkout_scan.py`, implements every rule of `contracts/architectural-gate.md` (G1–G6). WP18 builds the live-tree gate on it.
6. Self-mutation tests in `tests/architectural/test_owned_checkout_gate_selftest.py` prove each rule flags its synthetic offender and passes a clean synthetic source. **They never scan the live `src/` tree for offenders** (the tree is full of offenders until WP18; see Context).

7. **Error-code registry (S7).** `src/mission_runtime/owned_checkout.py` defines `class OwnedRefusalCode(StrEnum)` with one member per row of the data-model registry (the four claim-primitive codes, `OWNED_MISSION_PATH_REFUSED`, `OWNED_TOPOLOGY_UNSUPPORTED`, `OWNED_BRANCH_REFUSED`, `OWNED_INDEX_REFUSED`, `OWNED_CHECKOUT_IS_REPOSITORY_ROOT`, `OWNED_CHECKOUT_IS_MISSION_WORKTREE`, `OWNED_ACTION_UNSUPPORTED`, `OWNED_REVIEW_BASE_UNAVAILABLE`, `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`, `WORK_PACKAGE_UNRESOLVED`); each member's value equals its name (the strings are `do_not_change`). It is exported from the `mission_runtime` root with `OwnedCheckout`. Every later WP and test imports codes from it instead of repeating literals (Sonar S1192); existing literal sites are converted by the WP that owns their file.

**`TRANSITIONAL(WP18)` markers added by this WP (exact list):** `src/mission_runtime/owned_checkout.py` **5** (the legacy properties `primary`, `root`, `directory`, `slug`, `target`) and `tests/mission_runtime/test_owned_checkout.py` **1** (`test_legacy_properties_mirror_canonical_fields`); `grep -c "TRANSITIONAL(WP18)"` gives 5 and 1. WP18 T096 fails on any marker no WP lists.

**Dead-symbol gate (S3).** `tests/architectural/test_no_dead_symbols.py` is judged at the **mission tip** (WP18), not here. Expected transient red from this WP: `OwnedCheckout` (and `OwnedRefusalCode`) have no `src/` importer until WP02. That red is **not** this WP's failure: record it in the Activity Log, never allowlist it.

**Done means**: all new tests green; `tests/architectural/test_mission_runtime_surface.py` green; `tests/architectural/test_layer_rules.py` green with the `mission_runtime` outbound ledger unchanged; ruff check, ruff format and mypy `--strict` clean on every touched file; `make test-fast` green.

## Context & Constraints

Read before starting:

- `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/spec.md`: FR-001, NFR-006, C-001, C-003, C-008.
- `plan.md`: §Staging Strategy, §Test Layout and Markers, §IC-01, §IC-11.
- `research.md`: R-01 (carrier location and shape), R-03 (census), R-16 (gate rewrite, path safety).
- `data-model.md`: §OwnedCheckout (fields, invariants, `files()`, lifecycle).
- `contracts/owned-checkout-carrier.md` (sole construction, consumers list §7) and `contracts/architectural-gate.md` (G1–G6, self-mutation list, commit discipline).
- `occurrence_map.yaml`: this WP only *adds* the new name. `code_symbols` / `import_paths` rename happens in later WPs; `serialized_keys` and `logs_telemetry` are `do_not_change`.

Constraints:

- **Layer rule (C-003).** `src/mission_runtime/owned_checkout.py` may import only the standard library, `kernel.*`, and `mission_runtime.*` siblings. No `specify_cli` import at any scope. The shrink-only `mission_runtime` outbound ledger (`tests/architectural/_baselines.yaml`, enforced by `tests/architectural/test_layer_rules.py`) must not grow.
- **Terminology (C-008).** Docstrings and messages say "owned checkout" and "repository root checkout". Never bare "primary" as a checkout alias, never "feature". The *legacy property* `primary` is the one exception, and its docstring must say it is a transitional alias for `repository_root`, deleted by WP18.
- **Staging (plan §Staging Strategy).** The legacy properties are transitional and ship only inside the mission branch; reviewers must not reject them. The PR contains the final state after WP18.
- **Gate floors on the live tree are forbidden in this WP.** The G1–G6 *assertions* over `src/` are committed red as the first commit of WP18. If WP01 asserted "≥1 offender on the live tree" as a floor, that assertion would go red the moment WP18 converts everything. Non-vacuity here comes only from self-mutation over synthetic sources.
- **No suppressions.** No blanket `# noqa` / `# type: ignore`. Complexity ≤ 15 (aim ≤ 11 for new code).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `claude/sleepy-hamilton-5lelee`; completed changes merge back into `claude/sleepy-hamilton-5lelee`.
- **Planning base branch**: `claude/sleepy-hamilton-5lelee`
- **Merge target branch**: `claude/sleepy-hamilton-5lelee`
- **Lane**: assigned by `spec-kitty agent mission finalize-tasks` in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/lanes.json` (not present yet at prompt-generation time). Use `spec-kitty implement WP01` to obtain the workspace; never reconstruct the worktree path.

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – `OwnedCheckout` value object

- **Purpose**: Introduce the one validated ownership fact that every owned read will consume (FR-001, C-001, C-003). It replaces `specify_cli.core.owned_mission.OwnedMission` (`src/specify_cli/core/owned_mission.py:17-38`), which lives in the CLI application layer where `runtime` and `mission_runtime` cannot import it (research R-01; `tests/architectural/test_layer_rules.py`).
- **Steps**:
  1. Create `src/mission_runtime/owned_checkout.py` with a `@dataclass(frozen=True)` class `OwnedCheckout` and these fields, in this order (data-model.md):
     - `repository_root: Path`
     - `owned_root: Path`
     - `mission_dir: Path`
     - `mission_slug: str`
     - `topology: MissionTopology` (import from `mission_runtime.context`, defined at `src/mission_runtime/context.py:43`)
     - `target_branch: str`
     - a private construction token, e.g. `_token: object = field(default=None, repr=False, compare=False)`.
  2. Add a module-private sentinel `_MINT_TOKEN = object()`. In `__post_init__`, raise `TypeError("OwnedCheckout is minted only by specify_cli.core.owned_mission")` when `self._token is not _MINT_TOKEN`.
  3. Add `@classmethod _mint(cls, *, repository_root, owned_root, mission_dir, mission_slug, topology, target_branch) -> OwnedCheckout`. It canonicalises the three paths with `kernel.resolution.resolve_rejecting_loops` (`src/kernel/resolution.py:50`), so symlink aliases collapse to one identity (spec §Edge Cases "Path aliases"). It then constructs with the sentinel. `_mint` is the only I/O in the module.
  4. `__post_init__` checks the pure invariants (no I/O, data-model.md §Invariants), raising `ValueError` with a message naming the violated invariant:
     - `owned_root` and `repository_root` are not the same checkout;
     - `mission_dir` is inside `owned_root / "kitty-specs"`;
     - `mission_dir.name == mission_slug`.
     Compare through one helper `_same_path(a, b)` / `_is_within(path, ancestor)`. On Windows (`kernel.paths.is_windows()`, `src/kernel/paths.py:46`) compare `os.path.normcase(str(p))`; elsewhere compare the `Path` values. Do not import `mission_runtime.checkout_identity._is_within` (a private name); re-express the two-line predicate locally, or promote it in a way that keeps MR-2 clean.
  5. Add `files(self, paths: list[Path]) -> list[Path]`, moved from `OwnedMission.files` (`owned_mission.py:27-38`) and kept behaviour-identical:
     - a relative path is joined to `owned_root`;
     - any `..` part is refused;
     - each candidate is resolved with `resolve_rejecting_loops` and must be inside `mission_dir`; a symlink loop is refused too.
     Refusals raise `OwnedCheckoutPathRefused`, a new subclass of `mission_runtime.resolution.ActionContextError` (`src/mission_runtime/resolution.py:116`) whose `code` is the existing `"OWNED_MISSION_PATH_REFUSED"`. Subclassing keeps every existing `except ActionContextError` caller working (logs_telemetry: `do_not_change`).
  6. Add the **transitional legacy properties**. Each is a read-only `@property` carrying a `# TRANSITIONAL(WP18): legacy OwnedMission attribute name` comment on its `def` line, and a docstring saying "Transitional alias (WP01); deleted by WP18". WP18 T096 deletes exactly what `grep -rn "TRANSITIONAL(WP18)" src tests` finds, so an unmarked property would survive:
     - `primary` → `repository_root`
     - `root` → `owned_root`
     - `directory` → `mission_dir`
     - `slug` → `mission_slug`
     - `target` → `target_branch`
  7. Add `class OwnedRefusalCode(StrEnum)` (`from enum import StrEnum`; Python 3.11+) listing every data-model registry code, value == name. `OwnedCheckoutPathRefused` uses `OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED` as its `code`. Pin in T003: `{c.value for c in OwnedRefusalCode}` equals the registry set, and `OwnedRefusalCode.OWNED_BRANCH_REFUSED == "OWNED_BRANCH_REFUSED"` (StrEnum compares equal to the string, so existing `error_code` string assertions keep passing).
  8. Module `__all__ = ["OwnedCheckout", "OwnedCheckoutPathRefused", "OwnedRefusalCode"]`. Module docstring: what the fact proves, who mints it, and that it is never persisted.
- **Files**: `src/mission_runtime/owned_checkout.py` (new).
- **Parallel?**: No. T002–T005 depend on the class existing.
- **Validation checklist**:
  - [ ] `OwnedCheckout(...)` with all six fields and no token raises `TypeError`.
  - [ ] `dataclasses.replace(fact, owned_root=...)` also goes through `__post_init__`, so invariants still hold. Test it.
  - [ ] Two facts minted from a symlink path and its target compare equal.
  - [ ] `python -c "import mission_runtime.owned_checkout"` imports no `specify_cli` module. Assert `"specify_cli" not in sys.modules` in a subprocess, or rely on `test_layer_rules.py`.
  - [ ] mypy `--strict` clean, with no `Any` leaking from the classmethod.
- **Edge cases**:
  - Importing `ActionContextError` from `mission_runtime.resolution` at module scope is an intra-package edge and is allowed. If `resolution.py` later imports `OwnedCheckout` for annotations (WP04), it must do so under `TYPE_CHECKING` or lazily, to avoid a cycle. Say so in the module docstring.
  - Do **not** put `resolve()` in `__post_init__`: the data model says invariants are pure path logic, and the `_mint` step already canonicalised.
  - `topology` is the enum, never the raw string. `_mint` does not parse strings; the minter (WP02) does.
  - A fact is hashable (frozen). Downstream caches (WP05) may key on it; the token is `compare=False`, so hashing ignores it.

### Subtask T002 – Re-export plus the `mission_runtime` public-surface gate

- **Purpose**: `runtime` and `specify_cli` consume `OwnedCheckout` from the package root only. MR-1 (pytestarch) and MR-2 (AST scan) in `tests/architectural/test_mission_runtime_surface.py` forbid submodule imports from outside the package, so the type must be on the root (research R-01).
- **Steps**:
  1. In `src/mission_runtime/__init__.py` (imports at `:37-84`, `__all__` at `:85-135`), add `from mission_runtime.owned_checkout import OwnedCheckout, OwnedRefusalCode` and add `"OwnedCheckout"` and `"OwnedRefusalCode"` to `__all__` in sorted position. Add a short comment in the local style: `# owned-checkout-lifecycle-authority WP01 (FR-001/C-003): the validated ownership fact …`.
  2. Do **not** export `OwnedCheckoutPathRefused`. It subclasses `ActionContextError`, which is already public, so consumers catch that. Keep the surface lean (FR-014 of dead-port-disposition).
  3. In `tests/architectural/test_mission_runtime_surface.py`, add `"OwnedCheckout"` and `"OwnedRefusalCode"` to `_PUBLIC_SURFACE` (`:49-170`) with a comment naming this mission and WP. `test_public_surface_is_exactly_all` (`:191-199`) asserts list equality with `__all__`, so both edits land in the same commit.
  4. Update the package docstring's surface paragraph (`__init__.py:22-29`) with one sentence: the validated ownership fact is on the root because the runtime layers consume it (ADR 2026-06-07-1; WP03 amends that ADR).
- **Commit sequence**:
  1. Red: add `"OwnedCheckout"` to `_PUBLIC_SURFACE` alone. `test_public_surface_is_exactly_all` goes red: the surface list and `__all__` disagree.
  2. Green: add the import and the `__all__` entry.

  This two-step is the non-vacuity evidence that the surface pin actually covers the new symbol.
- **Import-order check**: `mission_runtime/__init__.py` imports `context` before `resolution`, and `owned_checkout.py` imports from both. Place the new import **after** the `mission_runtime.resolution` import block (`:59-72`). Confirm with `python -c "import mission_runtime; print(mission_runtime.OwnedCheckout)"` in a fresh interpreter. Also run `python -X importtime -c "import mission_runtime" 2>&1 | grep owned_checkout` to confirm the module loads once and adds no heavy dependency.
- **Out of scope**: do not touch `_COMPAT_ATTRS` (`__init__.py:137-143`). `OwnedCheckout` is a real `__all__` member, not a compatibility attribute.
- **Files**: `src/mission_runtime/__init__.py`, `tests/architectural/test_mission_runtime_surface.py`.
- **Parallel?**: Yes with T003 once T001 exists.
- **Validation checklist**:
  - [ ] `pytest tests/architectural/test_mission_runtime_surface.py -q` is green.
  - [ ] `test_ast_scan_no_external_internal_imports` (`:306`) is still green: nothing outside the package imports `mission_runtime.owned_checkout`. Tests may import it; MR-2 scans `src/` only.
  - [ ] `pytest tests/architectural/test_layer_rules.py -q` is green, and the `mission_runtime` outbound ledger count is unchanged.
  - [ ] `pytest tests/architectural/test_no_dead_symbols.py -q`: see Edge cases.
- **Edge cases**:
  - **Dead-symbol gate (judged at the mission tip, WP18; expected transient red here).** `tests/architectural/test_no_dead_symbols.py` fails an `__all__` member that has no `src/` importer. The re-export from the parent package counts for the `owned_checkout` module declaration, but `mission_runtime.__all__` itself may be flagged until WP02 imports `OwnedCheckout` in `specify_cli/core/owned_mission.py`. If it goes red, do **not** add an allowlist entry. Record the finding in the Activity Log and tell the reviewer. WP02's T006 is the first `src/` consumer; WP18 asserts the gate green at the mission tip. The expected transient reds across the mission are: `OwnedCheckout` until WP02, `resolve_owned_create_root` until WP10, `adopt_owned_checkout` until WP08. Do not treat them as this WP's failure.
  - MR-2 ignores `TYPE_CHECKING` imports (`test_ast_scan_ignores_type_checking_imports`, `:373`). A runtime import is still required here, because consumers use the class at runtime.
  - Consumers outside the package import the type as `from mission_runtime import OwnedCheckout`, never from `mission_runtime.owned_checkout`. Tests may import the submodule directly (for `OwnedCheckoutPathRefused` or the sentinel), because MR-1/MR-2 scan `src/` only. Say this in the `owned_checkout.py` module docstring, so later WPs do not "fix" a test import.
  - The package docstring already claims that "The root surface is exactly what `src/` consumers outside the package import". Until WP02 lands, `OwnedCheckout` has no such consumer. That is the same transient condition as the dead-symbol note above; do not reword the docstring to hide it.

### Subtask T003 – Carrier unit tests, identity cases, `ci-windows.yml` filter

- **Purpose**: Pin every invariant and behaviour of the fact, including cross-platform identity (NFR-006).
- **Steps**:
  1. Create `tests/mission_runtime/test_owned_checkout.py` with `pytestmark = [pytest.mark.unit, pytest.mark.fast]` for the pure tests. Build the paths on `tmp_path` and mint through `OwnedCheckout._mint(...)`. Tests may call `_mint` (contract §1 "or a `tests/` helper"); gate G3 scans `src/` only.
  2. Tests (one behaviour per test, names describe the behaviour):
     - direct construction raises `TypeError`, and so does `OwnedCheckout.__new__` plus `__init__` with a forged `_token=object()`;
     - `_mint` happy path: all fields resolved, and the legacy properties equal the canonical fields;
     - `owned_root == repository_root` raises `ValueError`;
     - `mission_dir` outside `owned_root/kitty-specs` raises `ValueError`;
     - `mission_dir.name != mission_slug` raises `ValueError`;
     - `dataclasses.replace` re-runs the invariants;
     - `files()`: relative path inside is accepted; `..` is refused; an absolute path outside is refused; a symlink inside `mission_dir` pointing outside is refused; a symlink loop (`a -> b`, `b -> a`) is refused with code `OWNED_MISSION_PATH_REFUSED`, and the error `isinstance` `ActionContextError`;
     - equality and hashing: two mints of the same inputs are equal and hash equal.
  3. **Symlink identity case (NFR-006)**: create `real/` (a directory tree with `kitty-specs/<slug>`) and `link -> real`. Mint with `owned_root=link` and `mission_dir=link/kitty-specs/<slug>`. Assert `fact.owned_root == real.resolve()` and that it equals a fact minted from `real`. Skip only if `os.symlink` raises `OSError` on the platform (Windows without developer mode), with a reason string. Never skip silently.
  4. **Case-variant identity case (NFR-006)**: mark it `@pytest.mark.windows_ci` (plus `unit`). Mint with `repository_root=R` and `owned_root=Path(str(R).swapcase())`, and assert `ValueError` (the same checkout) on Windows. On non-Windows, monkeypatch `kernel.paths.is_windows` to return True **and** use paths that differ only by case, so the normcase branch is exercised on Linux CI too. Keep one test that runs natively on `windows-latest`.
  5. Add `tests/mission_runtime/test_owned_checkout.py` to the `dorny/paths-filter` list in `.github/workflows/ci-windows.yml` (entries at `:25-45`, alphabetical within `tests/`). The Windows job selects files by `git grep -l "@pytest.mark.windows_ci"` (`:137`) and runs `-m windows_ci`, so the marker and the filter entry are both required.
  6. A small helper at the top of the test module keeps each test short:
     ```python
     def _layout(tmp_path: Path, slug: str = "owned-01M1A900") -> tuple[Path, Path, Path]:
         repo = tmp_path / "repo"; owned = tmp_path / "owned"
         mission = owned / "kitty-specs" / slug
         mission.mkdir(parents=True); repo.mkdir()
         return repo, owned, mission

     def _mint(repo: Path, owned: Path, mission: Path, **over: object) -> OwnedCheckout:
         kwargs = dict(repository_root=repo, owned_root=owned, mission_dir=mission,
                       mission_slug=mission.name, topology=MissionTopology.SINGLE_BRANCH,
                       target_branch="codex/owned")
         kwargs.update(over)
         return OwnedCheckout._mint(**kwargs)
     ```
  7. Pin the transitional legacy names in **one** test (`test_legacy_properties_mirror_canonical_fields`), marked `# TRANSITIONAL(WP18): pins the legacy properties`. WP18 deletes that single test together with the properties, and its docstring must say so.
- **Files**: `tests/mission_runtime/test_owned_checkout.py` (new), `.github/workflows/ci-windows.yml`.
- **Parallel?**: Yes with T002.
- **Validation checklist**:
  - [ ] `pytest tests/mission_runtime/test_owned_checkout.py -q` is green.
  - [ ] `pytest tests/mission_runtime/test_owned_checkout.py -m windows_ci -q` selects ≥ 1 test.
  - [ ] YAML stays valid: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci-windows.yml'))"`.
  - [ ] Mutation sanity: temporarily delete the sentinel check. The construction test must fail. Revert.
- **Edge cases**:
  - `tests/mission_runtime/` has no `__init__.py` (verified). Keep module names unique across the repository (`test_owned_checkout.py` is unique today).
  - `resolve_rejecting_loops` raises `OSError(ELOOP)`. `files()` must translate it into `OwnedCheckoutPathRefused`, never let it escape.
  - Do not assert git-dependent behaviour here. The fact is git-free.

### Subtask T004 – AST gate scanner module

- **Purpose**: Provide the scanner that enforces the single-authority rules. It is built now so its self-tests are green from the start. WP18 wires it to the live tree with an empty allowlist (FR-001, SC-004, `contracts/architectural-gate.md`).
- **Steps**:
  1. Create `tests/architectural/_owned_checkout_scan.py`. Parse every source through `tests/architectural/_ast_scan.parse_file` / `parse_source` (`_ast_scan.py:67-75`), which fails closed. Never write `except SyntaxError: continue`: `test_scanner_parse_fail_closed.py` bans it.
  2. Expose a small, typed API. Each function takes `(tree: ast.Module, rel_path: str)` and returns `list[Offender]`, where `Offender` is a frozen dataclass `(rule, rel_path, lineno, detail)`:
     - `claim_references(...)` (**G1**): every reference to `resolve_ownership_claim`: `ast.alias.name` including `import … as x`, `Name.id`, `Attribute.attr`, and a `Constant` string passed to `getattr` / `importlib.import_module` / `__import__`.
     - `validator_calls(...)` (**G2**): calls to `resolve_owned_mission(` / `adopt_owned_checkout(` in any reference form.
     - `mint_references(...)` (**G3**): any `Attribute(attr="_mint")` whose value names `OwnedCheckout`, including via an alias.
     - `effective_root_identifiers(...)` (**G4**): the identifier `effective_root` as a function argument (every arg kind), a `keyword.arg`, a class-body or local `AnnAssign` target, an `Attribute.attr` read or store, a `Name`, and a string `Constant == "effective_root"` used as a dict key, subscript or TypedDict key. **Docstrings and comments never count**: skip the first-statement `Expr(Constant(str))` of modules, classes and functions.
     - `bare_owned_root_paths(...)` (**G5**): parameters and class-body fields named `owned_root`, `owned_checkout`, `checkout_root` or `effective_root` whose annotation is `Path`, `pathlib.Path`, `Path | None`, `None | Path`, `Optional[Path]`, `Union[Path, None]`, `os.PathLike`, `os.PathLike[str]`, or the string form of any of these. Unwrap `Annotated[X, …]` to `X` so a typer option cannot evade the rule (see Risks).
     - `owned_signature_pins(tree, rel_path, required: Mapping[str, str])` (**G6**): for each required qualname (a function or class), assert a parameter or field `owned` annotated `OwnedCheckout | None` (either spelling order, or the string form). A missing pin is an offender. The consumer list is `contracts/owned-checkout-carrier.md` §7; the topology-agnostic review-base helper `claim_commit_for_wp(mission_dir: Path, wp_id: str)` is **not** in it.
  3. Encode the **exemptions** as named, documented rules, never as path lists of offenders (`contracts/architectural-gate.md`):
     - `ORG_PACK_MODULE_RULE`: one module-scoped rule, reason "`effective_root` here is the org-pack root `OrgPackConfig.effective_root` (`src/charter/offering/drg/org_pack_config.py:374`), a different concept". It covers exactly `src/charter/**`, `src/specify_cli/doctrine/**`, `src/specify_cli/cli/commands/_doctrine_collect.py` and `src/specify_cli/analysis_inputs.py`, and takes them out of G4/G5 scope. `src/specify_cli/charter_runtime/lint/checks/org_layer.py` is deliberately **not** covered: its walrus local is renamed by WP18 T097.
     - `ORG_PACK_METHOD_RULE`: a `Call` whose `func` is `Attribute(attr="effective_root")` (the `OrgPackConfig.effective_root(repo_root)` method) is exempt from G4 anywhere. An `effective_root` **attribute read that is not called** is still flagged.
     - `CARRIER_FIELD_RULE`: the fields of the class whose fully-qualified name is `mission_runtime.owned_checkout.OwnedCheckout` are exempt from G5. Key on module path plus class name, never on field name alone.
     - `CLI_CLAIM_INPUT_RULE`: a parameter whose annotation is the name `OwnedCheckoutOption` (the CLI claim-input alias WP08 defines in `specify_cli/cli/commands/_owned_checkout.py`) is exempt from G5. Reason: it carries the raw, unvalidated `--owned-checkout` input to the minter, never an owned root. Also covered: the help-preserving form `Annotated[Path | None, owned_checkout_option(help=...)]` (an `Annotated` whose metadata is a `Call` to `owned_checkout_option`). Match the alias name (or `_owned_checkout.OwnedCheckoutOption`) or that exact call, never an arbitrary `Annotated[...]` or `typer.Option(...)`.
     - `MIGRATIONS_CHECKOUT_ROOT_RULE`: modules under `src/specify_cli/upgrade/migrations/**` are excluded from G5's `checkout_root` name check (historical migrations; an unrelated sense). The other G5 names and G4 still apply there.
  4. Provide `iter_python_sources(root: Path) -> Iterator[tuple[Path, str]]` for WP18, yielding sorted `(path, rel_path)` pairs and skipping `__pycache__`. The live-tree traversal is **not** called by any WP01 test that asserts offenders.
  5. Add a module docstring that maps G1–G6 to `contracts/architectural-gate.md`, states the commit discipline (self-tests green here; assertions red-first in WP18), and lists the exemption rules with reasons.
  6. Suggested public surface (keep the names stable; WP18 imports them):
     ```python
     @dataclass(frozen=True)
     class Offender:
         rule: str          # "G1".."G6"
         rel_path: str      # repo-relative, posix
         lineno: int
         detail: str        # e.g. "keyword effective_root=" / "param owned_root: Path | None"

     def claim_references(tree: ast.Module, rel_path: str) -> list[Offender]: ...
     def validator_calls(tree: ast.Module, rel_path: str) -> list[Offender]: ...
     def mint_references(tree: ast.Module, rel_path: str) -> list[Offender]: ...
     def effective_root_identifiers(tree: ast.Module, rel_path: str) -> list[Offender]: ...
     def bare_owned_root_paths(tree: ast.Module, rel_path: str) -> list[Offender]: ...
     def owned_signature_pins(tree: ast.Module, rel_path: str, required: Mapping[str, str]) -> list[Offender]: ...
     def iter_python_sources(root: Path) -> Iterator[tuple[Path, str]]: ...
     ```
     The G1/G2/G3 functions report every reference. **Where** a reference is allowed (the owned_mission module, the `_owned_checkout.py` helper, the definition site in `checkout_ownership.py`) is the caller's decision, expressed in WP18 as a module allowlist constant. Keeping the allow decision out of the visitors lets the self-tests exercise the visitors without any path context.
  7. Annotation classification lives in one helper, `_is_bare_path_annotation(node: ast.expr | None) -> bool`. It handles `Name`/`Attribute` (`Path`, `pathlib.Path`, `os.PathLike`), `Subscript` (`Optional[...]`, `Union[...]`, `Annotated[...]`, `os.PathLike[str]`), `BinOp(BitOr)`, and `Constant(str)`, which it parses with `ast.parse(value, mode="eval")` and recurses into. Unit-test this helper directly with a table of 12+ spellings in T005.
- **Files**: `tests/architectural/_owned_checkout_scan.py` (new).
- **Parallel?**: No (T005 depends on it).
- **Validation checklist**:
  - [ ] `ruff check` and `ruff format --check` are clean, and mypy `--strict` is clean on the module.
  - [ ] Each public function is ≤ 11 complexity: `.venv/bin/ruff check --isolated --select C901 --config 'lint.mccabe.max-complexity=11' tests/architectural/_owned_checkout_scan.py`.
  - [ ] Visitors are pure (no filesystem I/O except in `iter_python_sources`).
- **Edge cases**:
  - A local walrus `(effective_root := pack.effective_root(repo_root))` exists in `src/specify_cli/charter_runtime/lint/checks/org_layer.py:328-330`. The *method call* is exempt, but the *walrus target name* is not, and the module is not under `ORG_PACK_MODULE_RULE`. WP18 T097 **renames** the local (for example to `pack_root`); it is never exempted.
  - `checkout_root: Path` in `src/specify_cli/upgrade/migrations/m_4_0_0rc5_heal_template_set_provenance.py:104,133` is a non-owned sense covered by `MIGRATIONS_CHECKOUT_ROOT_RULE`.
  - Unparseable input must raise `UnparseableSourceError`, never return an empty list.

### Subtask T005 – Gate self-mutation tests (green)

- **Purpose**: Prove every rule has teeth before any live assertion exists (DIRECTIVE_043, "self-mutation non-vacuity"). These are the non-vacuity evidence for SC-004; the live floors come in WP18.
- **Steps**:
  1. Create `tests/architectural/test_owned_checkout_gate_selftest.py` with `pytestmark = pytest.mark.architectural`. Every test parses a **synthetic** source string via `parse_source(src, display="synthetic/<name>.py")` and calls the scanner functions directly.
  2. One parametrised case per self-mutation item in `contracts/architectural-gate.md`. Each case must be flagged by the named rule:
     - a stray claim call `resolve_ownership_claim(p, resolved_primary=r)` (G1);
     - `from specify_cli.core.checkout_ownership import resolve_ownership_claim as r` (G1, via the alias);
     - `mod.resolve_ownership_claim` attribute access (G1);
     - `getattr(mod, "resolve_ownership_claim")` (G1, string constant);
     - `def f(effective_root: "Path | None" = None): ...` (G4 and G5);
     - `def f(effective_root: Optional[Path]): ...` (G4 and G5);
     - `class T(TypedDict, total=False): effective_root: Path` (G4);
     - `f(**{"effective_root": x})` (G4, string key);
     - `def f(checkout_root: Path | None): ...` (G5, renamed parameter);
     - `OwnedCheckout._mint(...)` outside the minter (G3), including via `from mission_runtime import OwnedCheckout as OC; OC._mint(...)`;
     - a second class `class Other: owned_root: Path` (G5; the carrier exemption does not leak to other classes);
     - `def cmd(owned_checkout: Annotated[Path | None, typer.Option("--owned-checkout")] = None)` (G5, via the `Annotated` unwrap; the paired negative control below pins `CLI_CLAIM_INPUT_RULE`);
     - `def f(checkout_root: Path | None): ...` with `rel_path="src/specify_cli/core/fake.py"` (G5), paired with the migrations negative control below;
     - `(effective_root := pack.effective_root(repo_root))` with `rel_path="src/specify_cli/charter_runtime/lint/checks/org_layer.py"` (G4 on the walrus target; the call itself is not flagged);
     - `resolve_owned_mission(r, p, h)` in a non-allowed module (G2);
     - a G6 pin miss: a function `placement_seam(repo_root, mission_slug)` with no `owned` parameter.
  3. Negative controls (each must produce **zero** offenders):
     - a clean module that uses `owned: OwnedCheckout | None`;
     - a docstring that mentions `effective_root` and `resolve_ownership_claim`;
     - `pack.effective_root(repo_root)` (the org-pack method rule);
     - the carrier fields when the synthetic `rel_path` is `src/mission_runtime/owned_checkout.py` and the class is `OwnedCheckout`;
     - an `effective_root` parameter when `rel_path` is under `src/charter/`, `src/specify_cli/doctrine/`, or is `src/specify_cli/cli/commands/_doctrine_collect.py` or `src/specify_cli/analysis_inputs.py` (`ORG_PACK_MODULE_RULE`, one parametrised case per covered path);
     - `def cmd(owned_checkout: OwnedCheckoutOption = None)` and `def cmd(owned_checkout: Annotated[Path | None, owned_checkout_option(help="x")] = None)` (`CLI_CLAIM_INPUT_RULE` self-mutation: the same parameter with the `typer.Option(...)` spelling is flagged above);
     - `def f(checkout_root: Path | None): ...` with `rel_path` under `src/specify_cli/upgrade/migrations/` (`MIGRATIONS_CHECKOUT_ROOT_RULE`);
     - a G6 hit: `def placement_seam(repo_root, mission_slug, *, owned: OwnedCheckout | None = None)`.
  4. A **carrier-exemption self-mutation**: the same `OwnedCheckout` class body with `rel_path="src/specify_cli/core/fake.py"` **is** flagged. This pins that the exemption is by fully-qualified name.
  5. A fail-closed test: a syntactically broken synthetic source raises `UnparseableSourceError`.
  6. **Do not** add any test that scans `src/` and asserts offender counts. Add a module docstring sentence explaining why (the WP18 red-first commit owns the live assertions).
- **Files**: `tests/architectural/test_owned_checkout_gate_selftest.py` (new).
- **Parallel?**: No.
- **Validation checklist**:
  - [ ] `pytest tests/architectural/test_owned_checkout_gate_selftest.py -q` is green, with ≥ 16 positive and ≥ 10 negative cases.
  - [ ] Mutation sanity: comment out the `Annotated` unwrap in the scanner. The typer case must go red. Revert.
  - [ ] Mutation sanity: remove the docstring skip. The docstring control must go red. Revert.
- **Edge cases**:
  - Parametrise IDs explicitly (`ids=[...]`) so a failure names the case.
  - The G6 helper takes the required-consumer map as input. Do not hard-code the §7 consumer list in the scanner; WP18 supplies it.

## Test Strategy

**Red-first discipline for this WP.** WP01 adds new types and a test harness and changes no existing behaviour, so there is no pre-existing entry point to reproduce a defect through. The binding red-first evidence is:

- the construction test in T003, committed **before** the sentinel check exists. Commit `test_owned_checkout.py` with the construction test first, watch it fail (the class accepts direct construction or does not exist), then add the sentinel;
- the self-mutation cases in T005, committed before the corresponding scanner function. Each fails with an `AttributeError`/assertion first, then goes green. What makes them non-vacuous: every positive case asserts the *specific rule id* and line number, and the negative controls prove the rule is not simply "flag everything".

Markers (plan §Test Layout and Markers):
- `tests/mission_runtime/test_owned_checkout.py`: `unit` and `fast`; the case-variant test also has `windows_ci`.
- `tests/architectural/test_owned_checkout_gate_selftest.py`: `architectural`.

Commands (run all, record commands and pass counts in the Activity Log and later the PR "Tests run" section):

```bash
cd <workspace from `spec-kitty implement WP01`>
uv run --frozen pytest tests/mission_runtime/test_owned_checkout.py -q
uv run --frozen pytest tests/architectural/test_owned_checkout_gate_selftest.py -q
uv run --frozen pytest tests/architectural/test_mission_runtime_surface.py tests/architectural/test_layer_rules.py -q
uv run --frozen pytest tests/architectural/test_no_dead_symbols.py tests/architectural/test_scanner_parse_fail_closed.py -q
make test-fast
uv run --frozen ruff check src/mission_runtime/owned_checkout.py src/mission_runtime/__init__.py tests/mission_runtime/test_owned_checkout.py tests/architectural/_owned_checkout_scan.py tests/architectural/test_owned_checkout_gate_selftest.py tests/architectural/test_mission_runtime_surface.py
uv run --frozen ruff format --check src/mission_runtime/owned_checkout.py src/mission_runtime/__init__.py tests/mission_runtime/test_owned_checkout.py tests/architectural/_owned_checkout_scan.py tests/architectural/test_owned_checkout_gate_selftest.py tests/architectural/test_mission_runtime_surface.py
uv run --frozen mypy --strict src/mission_runtime/owned_checkout.py src/mission_runtime/__init__.py tests/architectural/_owned_checkout_scan.py
```

Do **not** run `make test-full` or the bare `tests/architectural/` directory (`NO_FULL_HEAVY_SUITES_IN_MISSION`). Only the specific gate files above.

## Risks & Mitigations

- **Dead-symbol gate red until WP02.** See T002 Edge cases. Mitigation: record it, do not allowlist, and keep WP01→WP02 in one lane.
- **Annotated typer parameters.** Unwrapping `Annotated` means every existing `owned_checkout: Annotated[Path | None, typer.Option(...)]` CLI parameter (for example `src/specify_cli/cli/commands/accept.py:763`, `agent/mission_finalize.py:3237`, `agent/tasks.py:782,916`) is a G5 offender. This is intended: each is migrated onto WP08's `OwnedCheckoutOption` alias or its help-preserving form `owned_checkout_option(help=...)`, both exempt by the named `CLI_CLAIM_INPUT_RULE`. Renaming the parameter to dodge the name list is a gate evasion. The user-visible flag `--owned-checkout` is set explicitly in `typer.Option`, so `cli_commands` stay unchanged.
- **Legacy-property drift.** The legacy names must return exactly the canonical fields. The T003 happy-path test pins all five.
- **Scanner false negatives.** Mitigated by the per-form self-mutation list and explicit negative controls.

## Review Guidance

- The sentinel makes direct construction impossible from `src/`, and `_mint` is the only I/O.
- `owned_checkout.py` imports nothing from `specify_cli`; the layer ledger is unchanged.
- `__all__` and `_PUBLIC_SURFACE` changed together; `OwnedCheckoutPathRefused` is not exported.
- The scanner covers every reference form in `contracts/architectural-gate.md`. The exemptions are named rules with reasons (`ORG_PACK_MODULE_RULE` over its four paths, the `OrgPackConfig.effective_root` method call, the carrier FQN, `CLI_CLAIM_INPUT_RULE`, `MIGRATIONS_CHECKOUT_ROOT_RULE`), each pinned by a self-mutation pair. No path list of offenders exists, and `org_layer.py` is not exempted.
- **No live-tree offender assertion exists anywhere in this WP.**
- The Windows marker and path filter are both present.
- The implementer ran mypy `--strict` in addition to pytest, and diagnostics passed.
- The legacy properties are transitional by design (plan §Staging Strategy). Do not reject them; confirm that each carries `# TRANSITIONAL(WP18)` and its docstring names WP18.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Initial entry**:

- 2026-09-28T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-09-28T17:24:14Z – claude – shell_pid=4411 – T001-T005 implemented and green. Two expected/non-blocking findings recorded per prompt: (1) tests/architectural/test_no_dead_symbols.py flags mission_runtime.owned_checkout::OwnedCheckoutPathRefused as an unimported public symbol -- expected transient red (contract: nothing catches it by name outside ActionContextError until a future WP; judged at the mission tip, WP18, per contracts/architectural-gate.md commit discipline). Not allowlisted, per instruction. (2) tests/specify_cli/runtime/test_agent_commands.py::TestFreshnessShortCircuitOSErrorFallthrough::test_destination_health_check_oserror_falls_through_to_render fails on this branch, deterministically, unrelated to this WP's diff (agent_commands.py freshness precheck, no owned-checkout code touched) -- pre-existing/baseline red, not caused by WP01.
- 2026-09-28T18:03:24Z – unknown – Review-cycle-1 findings addressed (blocking 1-7 + should-fix items). Key fixes: is_windows() now called through the kernel_paths module attribute (not a bound-name import) so monkeypatching actually reaches _same_path/_is_within; replaced os.path.normcase (a no-op on POSIX regardless of is_windows()) with str.casefold() so the Windows branch is genuinely forceable/testable on Linux CI; G4 docstring-Constant double-yield fixed; ORG_PACK_MODULE_RULE applied to G5; G2/G3 now catch import-as aliases, package-root attribute chains, and dynamic getattr lookups; G6 docstring/code reconciled (per-file-silent-absence) with a WP18 hand-off note; TRANSITIONAL(WP18) marker count fixed to exactly 5; both type:ignore suppressions removed via proper typing; a genuine AnnAssign double-count bug found and fixed while adding lineno assertions. Full re-verification: tests/mission_runtime/test_owned_checkout.py + tests/architectural/test_owned_checkout_gate_selftest.py 84 passed/1 skipped; tests/architectural/test_mission_runtime_surface.py + test_layer_rules.py + test_scanner_parse_fail_closed.py + test_no_dead_symbols.py 148 passed/1 failed (the same accepted transient OwnedCheckoutPathRefused dead-symbol red the reviewer already flagged as expected -- not allowlisted). Two commits: 909d153 (red-first strengthened tests, verified 15 failed against pre-fix code) then 659e814 (the fix, green).
- 2026-09-28T18:18:00Z – unknown – Review-cycle-2 narrow finding addressed: str.casefold() does full Unicode folding (ß->ss), unlike Windows/NTFS/PureWindowsPath/ntpath.normcase, causing _is_within to fail open (a file in sibling dir 'strasse/' accepted as inside mission dir 'straße/'). Replaced with ntpath.normcase in both _same_path and _is_within -- pure-Python, OS-independent (keeps the forced-is_windows Linux test genuinely exercising it), and exactly os.path.normcase on real Windows. Red-first: 8cdf128 (regression test fails against str.casefold() code: 'assert not True' on the ß/ss case) then 835f280 (fix, green). Re-ran the six targeted files: pytest 92 passed/1 skipped; ruff check/format clean; mypy --strict clean (3 src files + 2 test files); TRANSITIONAL(WP18) count still exactly 5+1; no type:ignore anywhere.
