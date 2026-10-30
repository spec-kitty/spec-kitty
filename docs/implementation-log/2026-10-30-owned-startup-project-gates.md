---
title: Owned checkout startup admission repair
description: Evidence and decisions for correcting startup admission of explicitly selected migrated linked checkouts.
doc_status: active
type: reference
audience: docs/context/audience/internal/system-architect.md
updated: '2026-10-30'
---
# Owned checkout startup admission repair

Status: Current, October 30, 2026; exact release-source repair under the parent
Subsequent mission `framework-facades-semantic-conversion-01M67ARH`.

The source baseline is upstream `spec-kitty/spec-kitty` tag `v4.0.0rc7`, peeled
commit `1b0fe9fc388b095f9964471b0177b4213e9c6c98`. The Crucible mirror's default
branch remains on 3.2.7 and lacks these owned-checkout APIs. This repair must not
be described as a delivered Crucible-default-branch or published-release fix.

## User Experience Findings

An upgraded linked checkout could not create a mission while the repository's
primary checkout retained its legacy charter. Startup inspected the primary
before the command could validate its explicit owned-checkout selection. That
forced another active owner's checkout to upgrade merely to use an isolated,
already migrated checkout.

The regression drives the actual mission-create command, verifies the scaffold
exists only in the selected checkout, and checks that ordinary commands in the
legacy primary remain refused. It covers invocation from both physical roots.

## Engineering Decisions

Startup tokenizes the real registered command path without executing callbacks.
Only a parsed owned-checkout option can invoke the existing canonical owned
create-root minter; a flag-shaped argument or an unsupported option grants no
authority. The selected checkout controls version, schema and legacy checks.
Full mission, topology and write custody validation remains in the command.
Invalid claims retain the original refusal path. Non-owned startup avoids the
owned helper's import graph, preserving startup-fast paths.

The implementation remains Python, as required by this owning project's charter.
It is a bounded safety/correctness repair to existing CLI behavior, with no
dependency, release-version, workflow, schema or language-policy change. Explicit
casts document existing lazy-import return contracts under narrow strict checks;
they neither bypass nor replace runtime validation.

The parent mission owns this blocker and its runtime custody. Standalone dispatch
in the release has no owned-checkout option and would select the protected legacy
primary, so no Op or lifecycle record is fabricated there.

The publication port also preserves the existing exact Git-call controls. Startup
and the leaf share only the canonical minter's successful immutable basic custody
claim within one root context. A lightweight private lifetime module starts a fresh
scope for every root invocation, including nested invocations, and resets it on
normal and error exit. Mission identity, topology, protection and write-branch
validation remain fresh. Normal/error sequential invocation controls replace the
selected path with a foreign repository and require fresh refusal; nested-error
and changed-branch controls check the corresponding lifetime boundaries. No
Git-call pin is raised to conceal duplicated registry work.

## Known Limitations

The candidate is a private, explicitly addressed patched 4.0.0rc7 runtime linked
to this source checkout; the shared installation is untouched. Preserve the source
checkout while a producer uses that editable runtime. Exact source hashes, red
and green test receipts and executable identity are retained externally.

The authenticated account has read but not push/admin authority over upstream.
Source publication and upstream-main delivery remain separate from local runtime
qualification. The independent Crucible mirror cannot receive a small PR of
these changes without first reconciling its 3.x/4.x source divergence.

The shared repository configuration points at an absent `.githooks` directory in
the release source. No hook was disabled or skipped. The canonical task-workflow
pre-commit script, UTF-8 decoding, diff checks, formatter, linter and relevant
strict checks are executed explicitly before source publication.
