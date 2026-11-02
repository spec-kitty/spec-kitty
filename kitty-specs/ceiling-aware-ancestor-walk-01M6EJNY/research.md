# Discovery research — #7056 one ceiling-aware ancestor walker

Created 2026-11-02. Extends into the plan step; nothing here is regenerated.

## D-1 — The defect reproduces on current `main`, in every walk the issue names

Ran against `origin/main` at `9aed3a8012` (the tree this mission branched from):

```
ceiling        = /tmp/repro7056-.../
checkout_ident = (/tmp/repro7056-.../outer, /tmp/repro7056-.../outer)   # crossed the ceiling
meta_no_git_anchor = False                                             # crossed the ceiling
env_file_root  = /tmp/repro7056-.../outer                              # crossed the ceiling
```

Setup: `<tmp>/outer/.git` (ambient repo), `<tmp>/outer/work` (start), and
`GIT_CEILING_DIRECTORIES=<tmp>`. Each walk returned the ambient repository above
the ceiling. #7022/PR #7058 did not touch these files for this purpose:
`git log --oneline -- src/specify_cli/core/checkout_identity.py
src/specify_cli/mission_metadata.py src/specify_cli/core/ledger_posture.py` shows no
ceiling work.

## D-2 — The census: which ancestor walks are root walks

An AST scan of `src/` for the hand-rolled idioms (`[p, *p.parents]`, `(p,
*p.parents)`, `[p] + list(p.parents)`, `for x in p.parents`) found 41 sites. They
split into three classes:

**Root walks — migrate to the primitive** (start directory → ancestors, first
directory satisfying a repository/project marker wins):

| Site | Marker | Note |
| --- | --- | --- |
| `core/paths.py::locate_project_root` | `.git` / `.kittify` | #7022, migrate onto the primitive |
| `core/paths.py::resolve_canonical_root` | `.git` | #7022, same |
| `core/paths.py::get_status_read_root` | `.git` file/dir | found by the census, not in the issue list |
| `core/paths.py::is_worktree_context` | `.git` pointer file | found by the census |
| `task_utils/support.py::find_repo_root` | `.git` / `.kittify` | #7022 fallback, migrate |
| `core/checkout_identity.py::_resolve_invocation` | `.git` | issue item |
| `core/ledger_posture.py::_walk_up_to_kittify_marker` | `.kittify` | issue item |
| `context/middleware.py::_find_repo_root` | `.kittify` | issue item |
| `mission_metadata.py::_has_no_git_anchor` | `.git` | issue item |
| `migration/legacy_charter_gate.py::find_checkout_root` | `.git` | issue item |
| `coordination/legacy_resolution.py` (worktree walk) | `.git` | issue item |
| `gitignore_manager.py::_has_git_control_path` | `.git` | issue item |
| `bootstrap/env_file.py::_find_repo_root` | `.kittify` / `.git` | issue item; stdlib-only module (see D-5) |
| `charter_runtime/lint/checks/org_layer.py::_find_repo_root_from_drg` | `.kittify` | issue item |
| `runtime/next/_internal_runtime/planner.py::_infer_project_root` | `.kittify` / `kitty-specs` | issue item |
| `charter/activation/context_renderers/catalog_diagnosis.py` (project layer) | `.kittify` | issue item |
| `charter/activation/neutrality/lint.py::_find_repo_root` | `pyproject.toml` | census addition |
| `cli/commands/regen.py::_repo_root` | templates + `tests/specify_cli` | census addition; dev-checkout root |

**Not root walks — exempt with a reason** (path-shape or membership checks, marker
walks over a file rather than a directory, package-sibling probes, asset
bookkeeping): `analysis_inputs.py` (symlink check on the home directory),
`kernel/paths.py::_find_relocated_missions_ancestor` (missions-asset probe on a
caller-supplied template root), `kernel/sibling_paths.py`, `coordination/
surface_resolver.py`, `workspace/root_resolver.py`, `core/vcs/detection.py` (both
walks classify a path against `.worktrees`/`kitty-specs` segments),
`status/views.py`, `policy/risk_scorer.py`, `consolidation/bookkeeping_projection.py`,
`runtime/asset_preparation.py`, `tool_surface/bundles/projection.py`,
`tool_surface/providers/managed_skills.py`, `compat/_detect/install_method.py`,
`upgrade/skill_update.py`, `charter/activation/activation_engine.py`,
`charter/offering/pack_paths.py`, `skills/command_installer.py`, `skills/installer.py`,
`task_metadata_validation.py`, `template/renderer.py`.

**Frozen historical migrations — exempt**: `upgrade/migrations/m_0_6_7`,
`m_0_9_2`, `m_0_14_0` walk the cwd for a dev-checkout fallback. They are version
frozen; a ceiling there changes what an already-released migration does on an
operator's machine, which this mission must not do. They are named in the gate's
exemption list with that reason.

## D-3 — Item 2 (exact git semantics) is decided as a contract, not a change

git does not examine a ceiling directory unless the search starts there, and it
leaves entries after an empty entry unresolved. `git_ceiling_dirs` (#7022) does
examine it and resolves every absolute entry. Matching git exactly would change
`resolve_canonical_root`'s shipped behaviour for every consumer (the entry point
many write paths use), and the gap only shows up when a walk starts *at* a ceiling
directory — which the harness never does (it starts at `tmp_path`, below basetemp).
Decision: keep the shipped reading, state it as the primitive's contract, and pin it
with tests (FR-006). A behaviour change to `resolve_canonical_root` needs its own
decision and mission; recorded here so it is not silently inherited.

## D-4 — The primitive belongs at the `kernel` floor

`src/charter` and `src/runtime` must not import `specify_cli`
(`tests/architectural/test_layer_rules.py`, landscape
`kernel <- charter <- glossary/runtime/mission_runtime <- specify_cli`). Both need
the walk (catalog diagnosis, charter lint, next planner). `kernel` already hosts the
shared path/environment primitives (`kernel/paths.py` reads an env var at the floor
on the same reasoning, "so neither package needs to import from the other"), so the
walk joins them. `specify_cli.core.paths.git_ceiling_dirs` keeps its name as a
delegating shim (C-003) because #7022's tests and the migration contract reference
it.

## D-5 — `bootstrap/env_file.py` is deliberately stdlib-only

Its module docstring says the richer resolver is "not importable here" because the
loader runs at bare `import specify_cli` time and must emit no stderr
(`tests/specify_cli/bootstrap/test_env_file_loader.py::test_bare_import_emits_no_stderr`).
`kernel.ancestor_walk` will be stdlib-only and import-cheap, so the walk can be
shared, but the loader must keep its narrow behaviour and must not acquire a
`specify_cli.core.paths` dependency. Verified by that existing test plus
`tests/architectural/test_bootstrap_import_purity.py`.

## D-6 — What the gate can and cannot see

The proposed gate ("ban hand-rolled `[p, *p.parents]` root walks") is a static AST
check. It sees the two idiom shapes (`*<expr>.parents` inside a list/tuple, and
`[x] + list(x.parents)`), not the intent behind a bare `for x in p.parents:` loop —
that shape is also how non-root walks are written (D-2's exempt class), so banning it
outright would either fail on 20 legitimate sites or need an exemption list longer
than the census. Decision: the gate bans the starred/concat shapes (the idiom the
issue names), and the migrated bare-`for` walkers (`org_layer`, `neutrality/lint`)
are migrated because they are root walks, not because the gate forces them. The
exemption list is file+function keyed, shrink-only, and fails when an entry no longer
matches a scan hit (FR-008).

## D-7 — Test-harness items 3 and 4

- Item 3, `no_git_ancestry_inside_tmp_path` (`tests/unit/workspace/
  test_root_resolver.py`): it builds `tmp_path/.git` inside the test's own tree — that
  marker is *below* the ceiling, so it is not the redundant mechanism the issue
  suspects. What it protects is `tmp_path`'s *ancestors*, which the harness ceiling
  already covers. Re-read on implementation and only remove it if the tests still
  pass and a control proves the protection.
- Item 3, the test-only `stop=` parameter: removing it touches `locate_project_root`
  and `find_repo_root` signatures plus their callers and tests. Out of scope (C-005).
- Item 4, `TMPDIR`/`TEMP` pointed under basetemp and the from-scratch child
  environments: broad, suite-wide hermeticity change with its own validation risk.
  Out of scope (C-005), follow-up issue named in the PR.

## Open questions resolved during plan

None outstanding. Mission boundary: issue items 1 and 2 (as a contract); items 3/4
reduced to the one safe cleanup (FR-009) plus a follow-up issue.
