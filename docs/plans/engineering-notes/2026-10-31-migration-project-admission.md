---
title: Migration project write admission
description: Preserve project discovery while preventing global runtime storage from authorizing unrelated migrations.
doc_status: point_in_time
updated: '2026-10-31'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/2026-10-30-owned-charter-context.md
- docs/plans/engineering-notes/index.md
---
# Migration project write admission

## Objective and observed user experience

A no-project migration can discover an ancestor global runtime `.kittify`
directory as though it were project metadata. During isolated CLI qualification,
`repin-hooks` created a new ancestor `.git/hooks` tree without a Git repository.
A separate dossier rebaseline invocation traversed the global ancestor and timed
out before its first snapshot write. Reproductions with nested dossier fixtures
also demonstrate that an eventual traversal could modify unrelated snapshots.
The exact observed hook tree, restoration verification and bounded process
results are preserved in external recovery receipts; the newly created tree was
removed without changing global runtime storage.

## Admission boundary and compatibility

Project discovery keeps its existing ordering and return values. The valid
`SPECIFY_REPO_ROOT` rule is extracted once and reused by discovery and migration
admission. It remains deliberate corpus-root authority for dossier rebaseline,
including valid aliases and linked-checkout normalization. Missing and
non-directory overrides retain normal discovery fallthrough. An explicit root
can still select a non-Git corpus independently of the current directory.

Before dossier traversal, the migration compares the discovered root and its
`.kittify` marker with canonical `get_kittify_home()` resolution, including
runtime-home overrides and aliases. An inferred global runtime marker needs a
fresh exact Git working-tree root. Ordinary non-global, non-Git projects retain
marker-based operation. Rejection happens before the snapshot iterator in both
write and dry-run modes.

Hook repinning always needs fresh exact Git authority, including with an
explicit root. The uncached observation invokes the existing canonical Git
probe implementation without clearing or replacing its caches. Existing real,
linked and aliased repository behavior remains intact. The low-level installer
creates the hooks directory without creating missing parents, so deletion of
Git metadata after the admission probe cannot recreate a fake ancestor tree.
Synthetic renderer fixtures retain their existing low-level contract.

## Regression evidence and limitations

Paired controls reproduce the original failures on unchanged production source
and test the corrected boundary with actual CLI calls, real repositories,
deleted cached topology, metadata removal after admission, global-home aliases,
nested unchanged dossier snapshots and explicit corpus selection. The original
no-project CLI assertions also pass under a short private validation root with
no Git or global runtime marker ancestors. Long or uncontrolled test roots are
recorded as rejected validation configuration rather than production proof.

This is a bounded correctness and safety repair in the existing Python CLI.
It neither changes general project discovery semantics nor introduces an
additional Git resolver. External receipts pin source, interpreter, dependencies,
commands and outcomes. Source implementation, successful qualification,
publication and consumer admission remain separate events.

## Owner, resources and next event

The runtime context delivery lane owns this repair, its private temporary roots
and joined process groups. Frozen-source qualification uses a short private
root outside project and user-global metadata ancestry. Preserve recovery
artifacts and historical failed runs; retire only exact released temporary
resources after their producers join. Review delivery, upstream findings and
remaining acceptance routing at the next publication event or on 2026-11-01.
