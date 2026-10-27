---
work_package_id: WP01
title: Doctor reports escaping fragment body_path
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-004
- C-003
- SC-001
- SC-002
planning_base_branch: issue-6418-doctor-body-path-containment
merge_target_branch: issue-6418-doctor-body-path-containment
branch_strategy: Planning artifacts for this mission were generated on issue-6418-doctor-body-path-containment. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6418-doctor-body-path-containment unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-body-path-containment-01M5ZD3C
base_commit: 5514470ce339154cf80408df752568fa16da0fae
created_at: '2026-10-27T19:33:03.581391+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
history:
- at: '2026-10-27T19:40:00Z'
  actor: claude
  action: created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/drg/
create_intent:
- tests/charter_offering/drg/test_org_body_path_escapes.py
execution_mode: code_change
owned_files:
- src/charter/offering/drg/org_pack_loader.py
- src/charter/activation/drg_activation.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/_profile_health_render.py
- tests/charter_offering/drg/test_org_body_path_escapes.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Doctor reports escaping fragment body_path

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load the assigned profile with the `/spk-charter-profile-load` skill:
**`python-pedro`** (implementer). Act within that profile's boundaries for the whole WP. The review runs under a different profile (`reviewer-renata`).

## Objective

`spec-kitty doctor charter-packs` must report an org pack unhealthy (exit 1) when a node **declared in the pack's `drg/fragment.yaml`** has a `body_path` that escapes the pack root (absolute, a `..` part, or a symlink resolving outside it). Each escape must be named in `org_drg.errors`, in a new always-present `org_drg.body_path_escapes` list, and in the human org-layer section. A contained `body_path`, existing or not, stays healthy. Spec: FR-001…FR-005, NFR-001…003, C-001, C-002, C-004.

## Context

- The defect is reproduced on `origin/main` 143a39fc; see `../research/phase0-grounding.md`.
- Exit code: `doctor.py` → `_collect_profile_health` → `CharterPackHealthReport.healthy`, which is false iff `org_drg["errors"]` is non-empty. Writing to `errors` is enough to flip RC; do **not** edit `_charter_pack_health.py`.
- Containment authority (C-001): `charter.offering.drg.org_pack_config.resolve_relative_path_within_root(root, rel)`, which raises `OrgPackSubdirEscapeError`. Never write a second escape check.
- Authored vs discovered: `OrgDRGFragment.authored_nodes` (subclass-based). Call it only on the fragment `load_org_drg` returned.
- Pack root: `load_pack_registry(repo_root).packs[i].effective_root(repo_root)`, the same join `load_org_drg` performs (`drg_activation.py` ~l.159–163).
- Both doctor halves must agree: the JSON collector `_collect_org_layer_data` (`_charter_pack_collect.py`) and the human renderer `_render_org_layer_section` (`_profile_health_render.py`). The renderer may **not** import the collect layer (an architectural boundary). Both call the same charter function.

## Branch Strategy

Planning base: `issue-6418-doctor-body-path-containment`. Merge target: `issue-6418-doctor-body-path-containment`. The execution worktree is allocated per computed lane from `lanes.json`. Run:

```bash
spec-kitty agent action implement WP01 --agent claude --mission doctor-body-path-containment-01M5ZD3C
```

## Subtasks

### T001 — Red-first tests for the charter predicate

**File**: `tests/charter_offering/drg/test_org_body_path_escapes.py` (new; `pytestmark = [pytest.mark.unit, pytest.mark.fast]`).

Build fragments with `load_org_pack(name, pack_root, 1)` on a `tmp_path` pack (`drg/fragment.yaml`, optional `pack.yaml`; check what `load_org_pack` needs by reading `org_pack_loader.load_org_pack`). Cases:

1. `body_path: ../../../../etc/hostname` → one `BodyPathEscape` (pack, node, kind `assets`, body_path verbatim, reason mentions `..`).
2. `body_path: /etc/hostname` → one escape (reason: absolute).
3. `C:\\Windows\\x` and `..\\x` → escape on every OS (the primitive's PureWindowsPath rule).
4. A symlink `inside.md` → `/etc` (skip when `os.symlink` is unavailable) → escape (resolves outside).
5. `bodies/x.md` (file absent) → no escape. `bodies/x.md` present → no escape.
6. A node with no `body_path` → no escape.
7. A discovered artifact node (for example `directives/foo.directive.yaml` carrying `body_path: ../../x`) → **not** reported (authored-only).
8. Several escaping nodes → one entry each, in authored order.
9. `find_org_body_path_escapes(repo_root, fragments)`: a repo with `.kittify/config.yaml` registering two packs, one escaping and one clean → escapes only for the first, naming its pack. A pack with `subdir` set → checked against the effective root.

Run them before writing the code and record the red (ImportError counts as red; then make the asserts meaningful).

### T002 — `BodyPathEscape` + `find_body_path_escapes`

**File**: `src/charter/offering/drg/org_pack_loader.py`.

- `@dataclass(frozen=True) class BodyPathEscape:` with `pack: str`, `node: str`, `kind: str`, `body_path: str`, `reason: str`; a `message` property returning `org pack '<pack>': node '<node>' (<kind>) body_path '<body_path>' escapes the pack root: <reason>`; and `as_dict() -> dict[str, str]`.
- `def find_body_path_escapes(fragment: OrgDRGFragment, pack_root: Path) -> list[BodyPathEscape]:` iterates `fragment.authored_nodes`, skips a falsy `body_path`, calls `resolve_relative_path_within_root(pack_root, node.body_path)` and, on `OrgPackSubdirEscapeError as exc`, appends an escape with `reason=str(exc)`. It does no file reads beyond the primitive's `resolve` (NFR-001).
- Import the primitive and the error from `charter.offering.drg.org_pack_config` (check for import cycles: `org_pack_config` must not import `org_pack_loader`).
- Add both names to `__all__`. Docstrings follow the module's style: why authored-only, and which authority.

### T003 — `find_org_body_path_escapes`

**File**: `src/charter/activation/drg_activation.py`.

- `def find_org_body_path_escapes(repo_root: Path, fragments: Sequence[OrgDRGFragment]) -> list[BodyPathEscape]:` builds `{pack.name: pack.effective_root(repo_root) for pack in load_pack_registry(repo_root).packs}`, then for each fragment extends the result with `find_body_path_escapes(fragment, roots[fragment.pack_name])`.
- A fragment whose pack is not in the registry cannot occur (the fragments came from the same registry). Let the `KeyError` (or any registry fault) propagate: the doctor records it as "check failed", never "no escapes".
- Add it to `__all__`. Keep it pure apart from the registry read.

### T004 — Red-first doctor tests

**File**: `tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py` (extend; reuse its fixture style).

- A fixture `tmp_repo_with_escaping_pack(tmp_path)`: copy `example_org` (its `body_path: directives/sox-controls.directive.yaml` is the contained control), then add an authored node `{id: team-asset, kind: assets, title: Team asset, body_path: ../../../../etc/hostname}` to its `drg/fragment.yaml`.
- `_collect_org_layer_data(repo)` → `body_path_escapes` has 1 entry `{pack: example-org, node: team-asset, kind: assets, body_path: ../../../../etc/hostname, reason: ...}`; `errors` contains its message.
- Healthy control: the unmodified `example_org` → `body_path_escapes == []`, no escape message in `errors`.
- Key always present: on the missing-pack early return and on the load-error return, `body_path_escapes == []`.
- Check crash: patch `find_org_body_path_escapes` (at the import site the collector uses) to raise → `errors` contains `org-layer body_path check failed: ...` and `body_path_escapes == []`.
- Renderer: `_render_org_layer_section(repo, Console(file=StringIO(), width=200))` prints `body_path escapes:` with `team-asset` and the path; the healthy control prints `body_path escapes: none`; a check crash prints `body_path escapes: not checked`.
- CLI (entry point): `runner.invoke(<doctor app>, ["charter-packs", "--json"])`, chdir'd or rooted at the repo the way the existing CLI tests in this file do it → `exit_code == 1` for the escaping fixture and the absolute variant (`/etc/hostname`); `exit_code == 0` for the control. Use the same invocation helper this file already uses (read it first).

### T005 — Collector wiring

**File**: `src/specify_cli/cli/commands/_charter_pack_collect.py`, `_collect_org_layer_data`.

- Add `"body_path_escapes": []` to the initial `result` dict, next to `dangling_endpoints`, with a short comment (the always-present rationale).
- After `result["configured_packs"] = packs` and the `if not fragments: return result` guard, call a new helper `_record_body_path_escapes(result, repo_root, fragments)`, **before** the merge (an escape is a pack fault and must not be hidden by a refused merge).
- The helper imports `find_org_body_path_escapes` from `charter.activation.drg_activation`, wraps the call in `try/except Exception` (`# noqa: BLE001`, matching the module's diagnostic convention, and only if the module's existing handlers carry that suppression; otherwise mirror exactly what they do), records `org-layer body_path check failed: {exc}` via `_append_org_errors` on a crash, and otherwise sets `result["body_path_escapes"] = [e.as_dict() for e in escapes]` and appends each `e.message`.
- Keep `_collect_org_layer_data` at complexity ≤ 15 (`ruff check --select C901`).

### T006 — Renderer wiring

**File**: `src/specify_cli/cli/commands/_profile_health_render.py`, `_render_org_layer_section`.

- After the per-pack `✓ loaded` lines and before the merge, call a new `_render_org_body_path_escapes(console, repo_root, fragments)`.
- It calls `find_org_body_path_escapes`. On a crash it prints `[yellow]body_path escapes: not checked[/yellow] (<exc>)`. With none it prints `body_path escapes: none`. Otherwise it prints `[red]body_path escapes:[/red] N fragment node(s) point outside their pack`, then up to `_ORG_FINDINGS_SHOWN` bullets of `e.message`, then the same "… and N more (run … --json …)" tail `_render_dangling_org_endpoints` uses. Reuse that shape rather than inventing a new one.

## Test commands

```bash
uv run --frozen pytest tests/charter_offering/drg/test_org_body_path_escapes.py tests/specify_cli/cli/commands/test_doctor_charter_packs_org_layer.py -q
uv run --frozen pytest tests/charter/ tests/charter_offering/ -q -p no:cacheprovider -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/ -q -k "doctor or charter_pack" -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_charter_facades_reexport_offering.py tests/architectural/test_charter_offering_public_surface.py tests/architectural/test_charter_offering_does_not_import_activation.py tests/architectural/test_layer_rules.py -q
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched> && uv run --frozen mypy <touched src>
```

## Definition of Done

- Every T001/T004 test was red before the fix and is green after; the red is recorded in the implement notes.
- The entry-point reproduction from research now exits 1 (`..` and absolute) and the control exits 0.
- No new `noqa`/`type: ignore` beyond the module's existing `BLE001` diagnostic convention, the complexity ceiling holds, and ruff/format/mypy are clean on the touched files.
- `body_path_escapes` is present in every `org_drg` payload.

## Risks / reviewer guidance

- Verify a contained-but-missing `body_path` is **not** flagged (no `strict=True` resolve).
- Verify discovered nodes are not checked, and that the check runs even when the merge refuses.
- Verify the human and JSON halves call the same function (no second predicate).
- Verify no edit to `packs/`, the facades' identity tables, `pyproject.toml` or `_charter_pack_health.py`.
