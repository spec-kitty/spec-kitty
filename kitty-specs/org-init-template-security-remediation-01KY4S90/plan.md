# Implementation Plan: Org Init Template Security Remediation

**Branch**: `feat/doctrine-org-init-from-template` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/kitty-specs/org-init-template-security-remediation-01KY4S90/spec.md`  
**Mission merge target**: `feat/doctrine-org-init-from-template` (PR #2719)

## Summary

Harden the existing doctrine `org init --template` pipeline against the third-party-tree threat model without redesigning seams. Skip `GIT_TOKEN` injection on the template resolve path; skip symlink entries during copy; reject `{{ORG_NAME}}` / `{{LOCAL_PATH}}` in entry names; reject `http://` / `git://`; make `--force` install move-aside-then-swap; replace `assert` with explicit guards; single-pass leftover scan; document fnmatch subset and credential policy.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: stdlib (`pathlib`, `shutil`, `tempfile`, `fnmatch`, `urllib.parse`); existing `specify_cli.doctrine.sources.GitSource`  
**Storage**: N/A (filesystem template copy only)  
**Testing**: pytest unit tests under `tests/specify_cli/doctrine/template_render/` (+ targeted GitSource/resolve tests)  
**Target Platform**: macOS / Linux CLI (operator workstation)  
**Project Type**: single (Spec Kitty CLI package)  
**Performance Goals**: no regression vs current local template render (&lt;30s typical)  
**Constraints**: remediations stay inside existing seams; do not clear `pr:deferred`; land on PR branch only  
**Scale/Scope**: ~6 modules touched; ~10–15 focused tests; docs touch for credential + fnmatch notes

## Charter Check

- ATDD-first: RED tests for token-leak, symlink, path-token, scheme reject before green fixes.  
- Fail-closed / no silent sanitising preserved.  
- Complexity ≤15 on touched functions; extract helpers if needed.  
- No blanket `# noqa` / `# type: ignore`.

## Implementation Concern Map

| ID | Concern | Primary surfaces | FR coverage |
|---|---|---|---|
| IC-01 | Credential injection policy on template path | `resolve.py`, `GitSource` (opt-in inject / factory flag), docs | FR-001, FR-002 |
| IC-02 | Symlink-safe copy | `ignore_copy.py` | FR-003, FR-004 |
| IC-03 | Path-token rejection + single-pass content leftovers | `substitute.py`, pipeline ordering | FR-005, FR-006, FR-010 |
| IC-04 | Scheme allowlist + atomic install + assert→guard | `resolve.py`, `pipeline.py` | FR-007, FR-008, FR-009 |
| IC-05 | Docs (credential policy, fnmatch subset) | doctrine org-init / template guide | FR-002, FR-011 |

## Project Structure

### Documentation (this mission)

```
kitty-specs/org-init-template-security-remediation-01KY4S90/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── credential-injection.md
│   └── path-token-rejection.md
└── tasks.md   # via /spec-kitty.tasks
```

### Source Code (repository root)

```
src/specify_cli/doctrine/
├── sources/git_source.py          # optional inject_token flag or no-op for template
└── template_render/
    ├── resolve.py                 # scheme reject; pass no-inject to GitSource
    ├── ignore_copy.py             # skip is_symlink()
    ├── substitute.py              # path-name scan; single-pass leftovers
    └── pipeline.py                # atomic force; explicit source guard

tests/specify_cli/doctrine/template_render/
docs/guides/  # or existing doctrine org-init doc — credential + fnmatch notes
```

## Approach

1. **GitSource**: add `inject_token: bool = True` (or equivalent) to constructor; `_inject_token` no-ops when false. Template `_resolve_git` constructs `GitSource(..., inject_token=False)`. Document in FR-002 docs. Other callers keep default True.  
2. **Copy**: at start of each `rglob` entry, if `path.is_symlink(): continue` (before `is_file()`). Do not copy link targets as file bytes.  
3. **Path tokens**: before or after content substitute, scan all relative path components under staging for placeholders; return `SubstituteError` with new `rule_id` (e.g. `substitute.path_token`). Prefer scan on destination after copy so names match PACK_PATH layout.  
4. **Single-pass content**: in `_substitute_file`, after replace, if placeholders remain in that file’s text, accumulate offender; drop separate full-tree leftover pass (or make leftover pass only for files not already checked).  
5. **Schemes**: `_classify_location` / parse reject `http://` and `git://` with `ResolveError` rule id `template.scheme_rejected` before fetch.  
6. **Atomic force**: if `pack_path.exists()` and force: `backup = pack_path.with_name(pack_path.name + ".bak-<nonce>")`; `move(pack_path, backup)`; `move(staging, pack_path)`; then `rmtree(backup)`. On failure after move-aside, attempt restore from backup.  
7. **Guards**: replace `assert source is not None` with `if source is None: return PipelineError(...)`. `_install_staging` destination-exists-without-force → `PipelineError` (or keep unreachable via prior check but type consistently).

## Phase 0 / Phase 1 artifacts

See [research.md](./research.md), [data-model.md](./data-model.md), [quickstart.md](./quickstart.md), [contracts/](./contracts/).

## Complexity Tracking

| Item | Why needed |
|---|---|
| Optional `inject_token` on GitSource | Avoids forking a second Git client; template path can disable injection without allowlist complexity |

## Risks

| Risk | Mitigation |
|---|---|
| Private-template HTTPS clones that relied on GIT_TOKEN via `--template` break | Document FR-002; SSH remotes still work; operators can embed credentials in URL if they insist (not recommended) |
| Skipping symlinks surprises templates that used links for shared files | Document; doctrine templates should be real files |
| Atomic install leaves `.bak-*` on crash | Best-effort restore; document cleanup |

## Delivery WP sketch (for tasks)

```
WP01 (IC-01+IC-04 schemes): GitSource inject flag + resolve scheme reject + tests
WP02 (IC-02+IC-03): symlink skip + path-token reject + single-pass leftovers + tests
WP03 (IC-04 install + IC-05 docs): atomic force, assert→guard, docs FR-002/FR-011
```

WP01 ∥ WP02 after shared test fixtures if needed; WP03 after WP01+WP02 or parallel on docs-only half.
