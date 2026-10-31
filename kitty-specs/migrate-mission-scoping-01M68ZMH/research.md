# Discovery — #6347 real `--mission` scoping for the corpus-walking `migrate` commands

Mission: `migrate-mission-scoping-01M68ZMH` (branch `issue-6347-migrate-mission-scoping`).

## Decision D-01 — The issue still reproduces on current `main`, and is not superseded

**Evidence.** On `origin/main` (HEAD `6f73b2a98e`), from an empty directory:

```
$ spec-kitty migrate backfill-provenance --mission ghost
`--mission` is not supported by this command: it is not mission-scoped. ...
```

The reject from #5294 / PR #6345 is present; there is no `--mission` option on any
of `backfill-provenance`, `charter-encoding`, `rebaseline-dossier-hashes`
(`CorpusWideCommand` on all three, which parses `--mission` only to raise
`UsageError`). `git log -S "not mission-scoped" -- src/specify_cli/cli/commands/migrate_cmd.py`
finds only `855991db52` (PR #6345), the change this issue follows up. A tracker
search for `6347` returns only PR #6345; no branch carries the follow-up.

**Conclusion.** Reproduces exactly as described; nothing superseded it. The
issue's own triage disposition (2026-10-19) already settled the one open design
point: `charter-encoding --mission` **skips** the global charter store with an
explicit diagnostic, and the store's bytes must be provably unchanged. Omitting
the selector keeps the corpus-wide default.

## Decision D-02 — Handle resolution belongs in the CLI, not in each backend

**Evidence.** The already-mission-scoped `migrate` commands do not agree on this.
`backfill-identity`, `backfill-topology` and `normalize-lifecycle` take a raw
`str` and pass it to a backend that treats it as a **directory-name slug**
(`backfill_mission_type_repo` even documents that a mid8 would raise
`MissionNotFoundError`, which is why `backfill-mission-type` advertises
`SLUG`). `backfill-merge-commit` instead calls
`specify_cli.cli.selector_resolution.resolve_mission_handle(...)`, which
resolves mission_id / mid8 / slug / bare prefix and exits 2 (human) or 1
(`--json`) on an unknown or ambiguous handle.

**Decision.** The three commands resolve `--mission` once, in the CLI, through
`resolve_mission_handle`, and hand the resolved canonical `mission_slug` to the
backend. Reasons: the issue explicitly asks for `mission_id` / `mid8` /
`mission_slug` "consistent with the already-mission-scoped `migrate` commands
like `backfill-identity`"; `resolve_mission_handle` is the single canonical
resolver (charter: single canonical authority, C-001 below); and it makes an
unknown handle fail closed with the resolver's own diagnostic instead of
silently degrading into an empty (or worse, unscoped) walk. Backends therefore
keep a plain `mission_slug: str | None` parameter and never re-parse handles.

## Decision D-03 — Scope discovery at the source, not by post-filtering

**Evidence.**

- `backfill-provenance`: `_collect_matrix_paths(repo_root)` iterates
  `kitty-specs/*/` and resolves each Mission's matrix through
  `mission_runtime.placement_seam(repo_root, slug).read_dir(ACCEPTANCE_MATRIX)`
  (a coord-homed matrix is found there, never via a primary-tree path join).
  Scoping must therefore narrow the *loop*, not post-filter resolved paths, or a
  coord-homed matrix would be missed.
- `charter-encoding`: `_collect_charter_files(project_root)` walks
  `kitty-specs/*/charter/*.{yaml,md,txt}` **and** `.kittify/charter/*.{yaml,md,txt}`
  in one pass. The second corpus is the global store the ruling says to skip.
- `rebaseline-dossier-hashes`: discovery is
  `iter_recorded_snapshot_files(root)` = `root.glob("**/.kittify/dossiers/*/snapshot-latest.json")`,
  recursive — it matches both `kitty-specs/<mission>/.kittify/dossiers/<slug>/`
  (the layout in this repo, verified by `find`) and a repo-root
  `.kittify/dossiers/<slug>/` cache. `rebaseline_snapshot_file` already prefers
  the recorded `mission_slug` field over the directory name, and its docstring
  notes a directory slug may differ from the indexed slug.

**Decision.** Each backend gains a keyword-only `mission_slug` that narrows its
existing discovery. `rebaseline` scoping matches on *mission identity*, not on
one path segment: the recorded `mission_slug`, the dossier directory slug, or
the owning `kitty-specs/<slug>` source directory — so a snapshot whose dossier
directory slug differs from the Mission slug is still found (spec Edge Cases).

## Decision D-04 — `charter-encoding` reports the exclusion in both renderings

**Evidence.** The command already has two summary renderers
(`_emit_json_summary`, sorted keys, and `_emit_human_summary`) and its JSON
payload is a documented, machine-read contract. A silent skip would violate the
ruling ("never touch the global store silently").

**Decision.** `--mission` adds a diagnostic to *both* renderings; the JSON
payload gains `"mission"` and `"global_store_excluded"` keys so a scripted
caller can assert the exclusion rather than parse prose. The scoped run's exit
code is computed from the Mission-scoped files only — a pre-existing global
store never fails a valid Mission-scoped operation.

## Decision D-05 — Mission topology: `single_branch`

The default `coord` topology mints a coordination branch and a separate
coordination worktree for a one-work-package change. This mission touches three
CLI commands, their three backends, one test file and one changelog entry, all
in one commit — a coordination branch and lane worktrees would add moving parts
without adding isolation. Reconciling the charter's change-scope tension
(`small diff ↔ boy-scout ↔ locality`) towards locality inside the two modules
the change already owns, the mission is `single_branch` on the PR branch
`issue-6347-migrate-mission-scoping`.

## Open questions carried into specify/plan

1. Should `charter-encoding --mission` **also** accept `--project-root`? (Yes —
   keep the existing option; the scope is orthogonal to the root.)
2. What does a scoped run report when the Mission has no matching file at all?
   (Decided in spec: a valid no-op, exit 0, never a widened walk.)
3. Do the two non-Mission commands' tests move? (No — they stay in the reject
   set; only the three scoped commands leave it.)
