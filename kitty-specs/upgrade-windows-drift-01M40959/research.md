# Research: Upgrade and Windows drift

Grounding evidence and seam census: [research-memo.md](research-memo.md). This file records the decisions the plan rests on.

## D1 — Fix false drift at the command-skill owner

- **Decision**: `command_installer` treats on-disk bytes equal to the current canonical rendering as fresh, and the adoption pass refreshes the recorded `content_hash` to that digest. `probe` and `verify` stay hash-versus-manifest and become correct once the manifest is refreshed.
- **Rationale**: the owner already renders canonical bytes in `prepare_commands`; the upgrade already runs that adoption pass (`_repair_stale_command_manifest`) before probing. Probing a second canonical render in the provider would duplicate rendering and leave the manifest stale for every other reader.
- **Alternatives considered**: canonical check inside `CommandSkillsProvider.probe` (duplicate render, manifest still stale); reclassify as `stale` (contract "stale" means disk equals manifest but not canonical, the opposite case).

## D2 — Consent is the existing explicit repair

- **Decision**: `CommandSkillsProvider.repair` passes `ApplyConsent(automatic=True, overwrite_paths=<drifted rels>)`, like `AgentProfilesProvider.repair`; `preserve()` lets a `consent_required` path through when it is named in `overwrite_paths`. No new flag.
- **Rationale**: matches agent-profile prior art and drift-policy Rules 3 and 5; `_apply_auto_repairs` never hands drifted statuses to a provider, so unattended upgrade stays report-only.
- **Alternatives considered**: expose `--repair-drift=overwrite` on upgrade (new public flag, escalation per C-002); auto-overwrite on upgrade (violates C-003).

## D3 — Compare Git object ids for planning artifacts

- **Decision**: `_files_changed_vs_ref` compares `git hash-object --stdin-paths` (each path's clean filter applied) with the object id at `<ref>:<rel>` from one `git ls-tree`. Any git error keeps the file as changed.
- **Rationale**: identical to what `git add` would store, so a line-ending-only difference compares equal and a real token change (in any line ending) compares unequal (C-004).
- **Alternatives considered**: normalize CRLF to LF in Python (diverges from `.gitattributes` semantics, e.g. `-text` files); `git diff --quiet <ref> -- <path>` per file (one subprocess per file); change `show_blob` (other callers rely on raw bytes).

## D4 — Mission workspace is a standalone clone

- **Decision**: the mission runs in a standalone local clone at `../sk-upgrade-windows-drift`, not a linked worktree.
- **Rationale**: at `fb7c92d6f0` planning commands for a `lanes_with_coord` mission resolve from the repository root checkout; a linked worktree is accepted as an owned checkout only for `single_branch`. A clone is its own repository root, keeps the requested topology, and leaves the primary checkout untouched. Logged as tooling friction.
- **Alternatives considered**: `single_branch` with `--owned-checkout` (loses the requested topology); working in the primary checkout (forbidden by the brief).
