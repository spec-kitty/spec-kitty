# WP02 review feedback (cycle 1) — reviewer-renata (claude)

Verdict: **changes requested**. One blocking defect; the rest of the WP is solid (parity, remedy text, JSON contract, lazy probe, T006 refactor all verified).

## Issue 1 (BLOCKING): the residue state leaks into the audit engine and turns an ERROR into a false green

`audit_repo`, `find_duplicate_prefixes` and `find_ambiguous_selectors` are not only `doctor identity`'s helpers. The audit engine consumes all three:

- `src/specify_cli/audit/engine.py:480` `identity_states = audit_repo(options.repo_root)` feeds `identity_state_to_findings` (`src/specify_cli/audit/identity_adapter.py:79`), which emits `IDENTITY_MISSING` (ERROR) only for `state == "orphan"` and returns `[]` for any other state, so `residue` returns `[]` too.
- `engine.py:271-272` `find_duplicate_prefixes(repo_root)` / `find_ambiguous_selectors(identity_states)` now drop residue.

The engine still decides Mission-ness with the laxer `is_mission_dir` (`engine.py:166`), where a tracked `spec.md` (or any marker on a non-git root) counts as a Mission. So a folder that the engine audits as a Mission is now `residue` in the identity index, and its findings disappear. Reproduced with the base source (`673e5664`) against HEAD, through `run_audit(AuditOptions(repo_root=r))`:

| fixture | base | HEAD |
|---|---|---|
| git repo, `001-spec-tracked/` (committed spec.md only) beside `001-mission` | `IDENTITY_MISSING` (error), `DUPLICATE_PREFIX`, `AMBIGUOUS_SELECTOR` | **no findings** |
| `001-mission` (its prefix/selector partner) | `DUPLICATE_PREFIX`, `AMBIGUOUS_SELECTOR` | **no findings** |
| non-git root, `002-spec-only/` | `IDENTITY_MISSING` (error) | **no findings** |

Consequences: `spec-kitty doctor mission-state --audit --fail-on error` flips from exit 1 to exit 0 for exactly the #6673 case (tracked meta.json deleted on disk) and for tracked spec.md-only folders. `migration/mission_state.py::_teamspace_audit_blockers` (line 1100) reads the same report. This contradicts:
- the WP's own risk note and the plan's IC-03: "`audit/identity_adapter.py` is unaffected".
- spec FR-008: the audit engine is one of the walkers that *keeps* its own rule (documented difference), not one that silently changes.
- C-004 in spirit: `classify_mission` is unchanged, but the engine never calls it directly; it consumes `audit_repo`'s states.

`tests/audit` stays green only because no audit test has a spec.md-only (or deleted-meta) directory in a default scan.

**Fix (pick one, keep the engine's output byte-identical to base):**
- Keep `audit_repo` / `find_duplicate_prefixes` with their pre-WP02 contract for the engine, and give `doctor identity` the residue-aware walk through a separate entry point or a keyword-only opt-in (for example `audit_repo(repo_root, *, residue=True)` used only by `run_identity_audit` and `_scope_to_mission`). `find_ambiguous_selectors` then needs the residue filter only on the doctor path, or it stays a no-op for the engine because the engine's states never carry `residue`.
- Or have the engine map the cases itself. That is a wider change to the audit engine, and FR-008 argues against it.

**Add a regression test in `tests/audit/`** (red on HEAD, green after the fix). It runs `run_audit` on a git fixture with a committed spec.md-only folder sharing a prefix/slug with a Mission, plus a non-git spec.md-only folder, and asserts `IDENTITY_MISSING` / `DUPLICATE_PREFIX` / `AMBIGUOUS_SELECTOR` are still emitted. Also update the engine/adapter docstrings if any wording changes.

## Non-blocking nits (fix if cheap)

1. `tests/architectural/test_mission_resolver_walker_gate.py:34-43`: `_mission_type_audit.py` no longer does a raw walk (it calls `iter_kitty_specs_children`), but its allowlist entry and its long rationale comment remain. No staleness check exists, so nothing fails. The entry is now misleading: drop it or reword the comment (the raw walk moved to `status/identity_audit.py`, already allowlisted). The file is out of map, so coordinate or leave it to WP03.
2. `tests/specify_cli/cli/commands/test_identity_audit.py::test_residue_remedy_is_the_planned_text` checks prefix, one substring and suffix, not the whole text. The constant does match plan.md exactly (reviewer verified by string comparison). Pin it fully, or copy the plan sentence into the test.
3. `doctor identity` probes git once in `audit_repo` and again in `find_duplicate_prefixes` (two `ReporterTrackedPaths`), and a third time in the `_scope_to_mission` fallback. That is within NFR-001's "per walk" wording. Sharing one memo through `run_identity_audit` would make it one per command.
4. `_needs_git` + `classify_walk_entry` read an id-less child's `meta.json` up to four times (`_carries_identity` twice through `is_selectable_mission_dir`, again in the second predicate call, then `classify_mission`). NFR-002 still passes. Fine as is, but a comment on why the double predicate call is cheap would help the next reader.
5. `tests/doctor/test_identity_audit.py::test_summarize_counts_and_lists_residue` adds three `# type: ignore[assignment]`. That follows the file's existing pattern, but `cast(...)` or `isinstance` asserts avoid new suppressions.
6. `audit_mission_types` now returns `[]` before resolving the roster when there is no selectable child. That is noted in the activity log and is harmless (the result is identical), unless `existing_mission_types` / `_resolve_layered_roster` raising on a broken charter was a signal someone relied on. Non-blocking.

## Verified OK

- T006 (`bcbfec63`) preserves behaviour: `safe_is_dir` on `kitty-specs/` and per entry, `[]` on a listing `OSError`, unstattable entries skipped (#3194), order kept (sorted, then filtered).
- `classify_mission` is unchanged. `RESIDUE_NOTICE` / `mission_resolver.py` are untouched by WP02. `RESIDUE_REMEDY == plan.md` blockquote (exact).
- Parity with `is_selectable_mission_dir` holds empirically. I compared selection, `audit_repo` non-residue and `audit_mission_types` on a git root, a non-git root, a nested tracked project and a nested untracked project. Each fixture had a Mission, a tracked id-less meta, tracked and untracked spec-only folders, an untracked id-less meta, lock-only, deleted meta (#6673), a non-string id, malformed JSON and a `meta.json` directory. All three sets were identical in every topology.
- The `_NO_TRACKED_PATHS` empty-set trick is correct. With an empty set the predicate is True exactly for an identity-bearing meta (or the `is_mission_dir` resolve-error fallback, which then agrees on both calls). A non-git root reaches `tracked_mission_paths -> None -> True`, never misclassified. A broken index raises (test present).
- JSON is additive (`summary.residue` always present, `residue_remedy` only with residue). `--fail-on residue` works. `--mission <residue>` reports residue on both the walk path and the fallback path. The golden snapshot diff is limited to the `doctor identity` docstring and `--fail-on` help.
- ruff, C901, `ruff format --check --force-exclude` are clean. mypy shows only the pre-existing `doctor.py:1266` error.
