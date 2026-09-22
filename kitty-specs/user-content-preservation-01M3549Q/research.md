# Research: User-content preservation for mutating flows

Phase 0 consolidation. Findings are traceable to a named source (grounding squad
runs, code inspection on `main@d57619a900`, or the referenced issue). Unsourced
claims are labelled hypotheses.

## R1 — All 7 defects are real on current main; none superseded

**Decision**: Proceed with all 7 in one mission.
**Rationale**: Grounding squad (paula-patterns, opus) verified by code inspection that
every cited `file:line` still matches each issue's "Cause" on `main@d57619a900`, and
`git log <filing-commit>..HEAD -- <file>` is empty for all 9 cause files (zero commits
since filing). The two P0s (#4907, #4895) were live-reproduced. The #4859/#4861/#4862
guard mission is present but wired into `init.py` + `upgrade/migrations/` only —
confirmed against CHANGELOG and the census test scope.
**Alternatives considered**: splitting P0s into a fast-track PR — rejected by operator
decision (DM 01M354BMVXECKWX0M1FT3XE27P: one PR for all 7).

## R2 — Removal flows reuse the existing guard as-is (no guard/prover extension)

**Decision**: Route `_remove_project_agent_surface` through
`guard_destructive_removal(surface, is_tree=True, prover=ManifestProver(check_command=True), backup_parent=None)`.
**Rationale**: `ManifestProver` already checks the command-skills manifest and fails
closed on mixed/untracked dirs (`provers.py`); a purely user-owned `.claude/commands/`
(no manifest entries in 4.x) yields `None` ⇒ preserve. `_prove_dir` gives dir-level
semantics: pure-owned ⇒ remove whole; any-unproven ⇒ preserve whole. #4907 (`remove`
verb) and #2691 (`sync` orphan sweep) call the helper with **identical args** — one
routed call covers both.
**Source**: paula-patterns + architect-alphonso (opus) code reads of
`asset_preservation/{guard,provers}.py` and `config.py:125-234`.
**Alternatives considered**: per-file routing to satisfy the owned-delete anchor —
**rejected**: re-enables the partial-rmtree loss class on a mixed dir (Edge case).

## R3 — Three destructive literals + verdict-driven messaging in config.py

**Decision**: Route `:137 rmtree` and `:139 unlink` through the one guard call;
allowlist `:142 root.rmdir()` (empty-only). Make the return tuple + `remove_agents` /
`_remove_orphaned_agent_dirs` rendering driven by `verdict.owned` / `verdict.diagnostic`.
**Rationale**: Today the helper does `rmtree` → `root.rmdir()` → returns `"Removed"`;
after routing, on preserve the surface stays, `root.rmdir()` raises OSError (non-empty),
is caught, and it **still** returns `"Removed"` — a FR-014/FR-015 violation (reports
removal while preserving). Messaging must follow the verdict.
**Source**: architect-alphonso SHOULD-FIX 1 (opus), verified against `config.py:125-147`.

## R4 — Manifest-pin rewrite (#2691) is a separate seam

**Decision**: Treat the manifest-pin rewrite as a distinct fix within WP-B, located at
the `command_installer.install` / `manifest_store` path (`_register_skill_agent`), not
the rmtree seam. A normal `sync` must leave `.kittify/command-skills-manifest.json`
pinned values byte-identical; any refresh is behind an explicit opt-in; `--json`
enumerates intended tracked mutations.
**Rationale**: #2691 documents two losses — deleted fixtures (the shared rmtree seam,
fixed by R2/R3) and repository-pinned manifest values replaced by the host CLI's own
release/hashes (a compatibility-contract mutation, not a removal).
**Source**: architect-alphonso (confirmed the seam) + paula-patterns (two-halves map).
**Open for /plan-implement**: the exact flag/opt-in name and whether sync should refresh
manifests at all is an implementation decision for WP-B's brownfield scout — hypothesis:
the safest fix is "sync never rewrites pins; a dedicated `--refresh-manifest` (or the
existing install path) is the only writer". Verify against the actual writer before coding.

## R5 — Overwrite backup: new shared symlink-aware helper, not the removal archiver

**Decision**: Add `backup_before_overwrite(path) -> Path` to `asset_preservation/backup.py`,
built on the exported `write_file_verbatim` (byte-exact, mode+mtime, `O_EXCL`) + the
canonical timestamp seam, producing an in-place sidecar (`pre-commit.<ts>`). It must
capture symlink targets via `os.readlink` rather than dereferencing.
**Rationale**: `archive_into`/`_allocate_backup_dir` are removal-parent-shaped (a
`.backup-<ts>/` directory tree) — wrong shape for the hook's in-place sidecar (the #4895
repro greps `pre-commit.(bak|orig|save|local)`). `write_file_verbatim` follows symlinks
via `read_bytes()`, so the helper must special-case links. One helper = one
backup-naming authority (today there are two: `template.manager` move-based +
`asset_preservation` copy-based).
**Source**: architect-alphonso SHOULD-FIX 4/5 (opus), verified against `backup.py`.
**Alternatives considered**: hand-rolled `f"{path}.{ts}"` at the hook site — rejected
(second naming authority, no symlink handling, no O_EXCL collision safety).

## R6 — Foreign-hook detection mirrors the retirement migration

**Decision**: Detect a spec-kitty-owned hook by its signature line
(`# Generated by spec-kitty.`); anything else is foreign ⇒ back up + warn + proceed
(hybrid contract, workflow-internal). A signed hook is replaced as today.
**Rationale**: `m_2_0_0_retire_git_hooks.py` already removes only signature-matching
spec-kitty hooks and leaves custom hooks alone — mirror that ownership proof in the
install direction. A plain signature check is simpler than instantiating a prover.
**Source**: #4895 "Expected" + architect-alphonso; `hook_installer.py:105-166`.

## R7 — intake is a pure refuse gate (no backup)

**Decision**: Drop the `and _source_path.exists()` conjunct at `intake.py:296`
(explicit/stdin) **and** `:156` (`--auto`) so the gate keys on `brief_path.exists()`
alone ⇒ refuse without `--force`, leaving the brief byte-identical. No backup taken.
**Rationale**: #4910 "Expected" is refuse-without-force; the operator drives the command
and `--force` is the natural escape (hybrid contract, user-driven). A fix that patches
only `:296` leaves the `--auto` path clobbering.
**Source**: architect-alphonso NICE 1 + reviewer-renata S3; #4910 Cause names both sites.

## R8 — #4896 encoding is a bespoke faithful-transcode fix

**Decision**: (a) classify text vs binary by content sniff, not `.md` extension; (b)
scope the fallback decode to the offending bytes (or refuse with offsets) instead of a
whole-file cp1252 re-decode; (c) preserve existing line endings (do not universal-newline
translate CRLF→LF); (d) report "Fixed" only on a faithful repair.
**Rationale**: #4896 Cause: `text_sanitization.py:161` (extension-only scope), `:166-180`
(whole-file cp1252/latin-1 fallback), `:189` (forced rewrite), `:166 vs :202`
(newline="" write drops CRLF). Three distinct corruptions (mojibake, binary, CRLF).
**Source**: paula-patterns code inspection; #4896.
**Not**: the #644 lifecycle-encoding redesign (out of scope, C-006).

## R9 — #4890 dep-validation is a unification, not new logic

**Decision**: Make legacy `agent tasks finalize-tasks` validate the **effective persisted**
graph (post frontmatter-preservation) with both `detect_dependency_cycles` and
`validate_dependencies`, exactly as `mission_finalize.py:_validate_dependency_graph`
already does; on rejection exit non-zero and seed no status; on success the `dependencies`
payload equals the persisted graph.
**Rationale**: The canonical command already refuses the identical repository — reuse its
validator over the effective graph rather than inventing a second one (single authority).
`tasks_finalize.py:213-230` validates the `tasks.md` map; `tasks_finalize_validation.py:300-305`
preserves frontmatter unvalidated; `core/dependency_graph.py:validate_dependencies` is
never called here.
**Source**: paula-patterns; #4890.

## R10 — #4888 root fix is single-seam at safe_commit; upgrade propagation is separate

**Decision**: FR-011 root fix at `git/commit_helpers.py:safe_commit` (already path-scoped
via `paths=`) — commit via a temporary index / `git commit --only -- <paths>` so the
operator's index/worktree is never stashed. FR-012 narrows `upgrade/autocommit.py:436`
`except Exception` to propagate the typed `SafeCommitRecoveryFailed` (orphan_stash_ref +
commit_sha), rendered by `cli/commands/upgrade.py`.
**Rationale**: The stash/pop-restore path deterministically fails on any partially-staged
unrelated file; removing the stash from the happy path (temp index) fixes all ~28
callers transparently **provided** it still commits exactly `paths` (verify no caller
relies on "commit whatever is staged"). FR-012 is defense-in-depth for the residual
stash path; its regression is exercised by forcing that path (injection), not the
post-FR-011 flow — so it does not guard dead code.
**Source**: architect-alphonso NICE 2 + reviewer-renata S1; #4888 Cause + fix direction.

## R11 — Census widening (#FR-013) is a closure step, lands last

**Decision**: WP-H widens `test_mutation_ownership_routing.py` with three synchronized
edits: add `cli/commands/agent/config.py` to `_module_set()`; add it to the pinned
`_ROUTED_MODULES` frozenset (set-equality assertion — route-without-pin AND
pin-without-route both fail); allowlist the `:142 Path.rmdir` empty-only op. It depends
on WP-B (config.py must be routed + literal-free first). `list.remove`/`shutil.copy2` in
config.py are not classifier-flagged (no false positives). The overwrite family stays
OUT of this census (that is #4901, out of scope).
**Source**: architect-alphonso SHOULD-FIX 2/3; census test read.

## Adversarial evidence (plan/research)

No security-impacting dependency decision is made (R-supply-chain: N/A). The post-spec
adversarial squad (reviewer-renata + architect-alphonso, opus) challenged the spec; every
contested finding was **accepted** and folded into `spec.md` + `tracer/design-decisions.md`
(overwrite contract consistency, FR-003 manifest AC, FR-011↔FR-012 sequencing, intake
`--auto` site, dir-level routing, symlink handling, census 3-edit closure). No contested
finding was silently dropped.
