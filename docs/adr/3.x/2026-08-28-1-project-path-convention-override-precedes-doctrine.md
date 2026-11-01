---
title: 'ADR: A project path_conventions override precedes the doctrine default, without changing the blocking policy'
description: 'A project path_conventions override remaps resolved accept directories ahead of the mission-type doctrine default, leaving the #3783 blocking policy unchanged.'
status: Accepted
date: '2026-08-28'
doc_status: active
kind: ADR
updated: '2026-08-28T00:00:00Z'
---

# ADR: A project `path_conventions` override precedes the doctrine default, without changing the blocking policy

**Status:** Accepted

**Date:** 2026-08-28

**Deciders:** Mission `accept-path-convention-override-01M14P41` (mission_id
`01M14P41`); folds #3016 and #2330 Item 1; in-radius follow-on to the honesty mission #3730/#3085
(merged as PR #3783).

**Technical Story:** #3016. Planning contracts under
`kitty-specs/accept-path-convention-override-01M14P41/` — `spec.md`, `contracts/config-schema.md`,
`contracts/precedence-contract.md`, `data-model.md`.

---

## Context and Problem Statement

The honesty mission #3783 made mission-path acceptance **blocking by default**: when a mission-type
doctrine convention names a directory (e.g. software-dev's `workspace: src/`) and that directory does
not exist, `spec-kitty accept` blocks with a `path_violations` finding that names two honest levers —
`accept --lenient` to downgrade to advisory, or adopt the convention — and never a bare `mkdir`.

That policy is correct, but it left a real project honestly stuck. A repository whose source root is
genuinely not `src/` — a Django project rooted at `apps/`, a Go project at `internal/` — has no way to
tell accept what its layout actually is. The only escapes were to fabricate an empty `src/` (dishonest,
exactly what #3783 set out to stop) or to run every accept with `--lenient` (throws away the honest
signal for every key, not just the mislabelled one).

The missing piece is a **value channel**: a way for a project to declare "my `workspace` is `apps/`, not
`src/`" so that accept validates against the project's real layout — while the strict/lenient *policy*
stays exactly as #3783 settled it. This ADR records how that override resolves, why it is remap-only,
why one key is excluded, and what the deliberate next step is.

## Decision Drivers

* **Non-reversal of #3783 (C-001, C-009).** The override is a *value* supplied to the existing
  validator; it must not reintroduce advisory-by-default or weaken any settled #3783 assertion.
* **Honest, non-fakeable acceptance (SC-006).** Overriding `workspace` to `apps/` when `apps/` is absent
  must *still block* under strict — the override changes the resolved directory, never the decision.
* **Single canonical authority (Directive 044).** One frozenset of valid path keys, reused by both
  `MissionConfig` validation and the override reader; no second, drifting list.
* **Routing safety (C-010).** The path-convention *value* and the mission artifact-token vocabulary are
  coupled at the routing seam; the override must not be able to flip an artifact-routed key's resolution
  surface.
* **Fail-closed on malformed config, lenient on absent config (FR-008).** A typo or a wrong-typed value
  is an operator error worth a clear, actionable raise; an absent section or an unreadable file must
  never break accept.

## Decision Outcome

A project may declare `project.path_conventions` in `.kittify/config.yaml` — a mapping of path-convention
key to the directory that key resolves to in *this* repository. `validate_mission_paths` applies it
**remap-only** and **ahead of** the mission-type doctrine default, then runs the unchanged #3783 blocking
policy against the resolved directory.

### Precedence order (per key)

1. **Project override** — if the mission declares `key` in `mission.config.paths`, `key` is not
   artifact-routed, and `project.path_conventions[key]` is set → the resolved directory is the override.
2. **Doctrine default** — otherwise the resolved directory is `mission.config.paths[key]` (the
   mission-type convention).
3. **Blocking-by-default + `--lenient`** — the resolved directory (whichever of 1 or 2 won) is then
   subject to the *unchanged* #3783 policy: absent under strict → blocking `path_violations`; absent
   under `--lenient` → advisory warning. The override changes *which directory* is checked, never
   *whether absence blocks* (C-001).

Research missions still apply their `path_prefix` via `_prefix_required_path` after the remap, unchanged.
The merge therefore happens on `declared` **before** the `required_paths` prefix comprehension and
**before** the artifact-token membership check, so an overridden key is prefixed for research missions
and never bypasses artifact routing (C-008).

### Remap-only

The override may only **remap a key the mission already declares**; it never introduces a new required
path. An override for a key the mission does not declare is ignored. This keeps the set of required paths
under the mission-type doctrine's control — the project chooses *where* a required directory lives, never
*which* directories are required.

### Deliberate non-reversal of #3783

This mission supplies a value and nothing else. The strict/lenient decision, the `path_violations`
payload shape, and the two-lever remediation string are all inherited verbatim from #3783; the mission's
test coverage is strictly additive and deletes or weakens no #3783 assertion (C-009). The
non-fakeable discriminator (SC-006) is the proof: `override.workspace = apps/` with `apps/` absent still
blocks under strict. An implementation that silently demoted conventions to advisory would fail that
test — which is exactly the #3783 regression this ADR forbids.

### Why `deliverables` is excluded — the value ↔ artifact-token coupling (C-010)

Routing at the paths seam is decided by whether `_normalize_path_token(declared[key])` is a member of
the mission's artifact tokens. Software-dev's `deliverables` default value is `contracts/`, and
`contracts/` **is** a mission artifact token — so `deliverables` resolves against the mission's
`feature_dir`, not the repository root, and carries a mission-surface artifact check. Allowing an
override to change `deliverables`' value would flip that resolution surface from `feature_dir` to
`project_root` and drop the artifact check.

The path-convention *value* and the artifact-token *vocabulary* are therefore coupled: overriding an
artifact-routed key is not a repo-layout remap, it is a routing change. Rather than special-case the
routing seam, the override *vocabulary* is restricted to repo-layout keys and **excludes any key whose
default value is a mission artifact token**. Concretely that is `deliverables`, the sole such key across
the four built-in mission types; the reader excludes it by name (`ARTIFACT_ROUTED_KEYS`) and
warns-and-ignores an override that targets it. The override thus never reaches an artifact-routed key,
and the routing check is provably unaffected.

The remaining vocabulary is the repo-layout subset of the canonical valid path keys —
`{workspace, tests, documentation, data}` — validated against the single frozenset `VALID_PATH_KEYS`
that `MissionConfig` also uses.

### Fail-closed scope

Validation is fail-closed on the **section shape**, lenient on the **file**:

* A key outside `VALID_PATH_KEYS` (a typo) → raise `PathConventionsConfigError` naming the offending key
  and the known keys (FR-007a).
* A section present but not a mapping, or a non-string / null value → raise, naming the offending key
  (FR-008).
* An artifact-routed key (`deliverables`) → warn and ignore (C-010).
* An absent `path_conventions` key → `{}`.
* A missing, unreadable, or corrupt `.kittify/config.yaml` → `{}` (lenient), matching the co-resident
  section readers.

The reader also reads **only** the `project.path_conventions` subkey — never the whole `project:` block,
which carries identity fields (`uuid`/`slug`/`node_id`/`build_id`) that must not be rejected (C-011). The
config is read once per accept run; there is no per-key filesystem read (NFR-002).

### Layout auto-detection (#2744) is the deliberate next step

This ADR deliberately stops at an **explicit** operator declaration. It does not infer a project's layout
from filesystem signals (`manage.py` → Django `apps/`, `go.mod` → Go `internal/`), and it does not relax
accept for research plan/tasks/WP shape. Automatic layout auto-detection is tracked separately as #2744
and is the intended follow-on: the explicit `project.path_conventions` channel this ADR establishes is
the substrate an auto-detector would populate, not a competitor to it. Shipping the explicit channel
first keeps the honesty contract auditable (the operator states the layout; nothing is guessed) before
inference is layered on top.

## Considered Options

* **A. Keep only `--lenient`.** Rejected: throws away the honest signal for every key to fix one
  mislabelled key, and still leaves no record of the project's real layout.
* **B. Explicit project `path_conventions` value override, remap-only, artifact-routed keys excluded
  (chosen).** Fixes the honestly-stuck project without touching the #3783 policy.
* **C. Auto-detect the layout now (#2744).** Deferred, not rejected: valuable, but inference before an
  explicit channel exists makes the honesty contract harder to audit. It builds on B.

## Consequences

### Positive

* A project whose real source root is not `src/` accepts honestly against an untouched working tree — no
  fabricated `src/`, no blanket `--lenient`.
* The #3783 blocking policy, payload, and remediation string are unchanged and re-proven by additive
  tests.
* One canonical `VALID_PATH_KEYS` frozenset serves both mission-config validation and the override reader.

### Negative

* Operators must know the `project.path_conventions` config surface exists; until #2744 lands, the layout
  is stated by hand rather than inferred.

### Neutral

* `deliverables` remains doctrine-owned and un-overridable by design; a project cannot relocate an
  artifact-routed key through this channel.

## Confirmation

* Precedence and remap-only behaviour: `tests/agent/test_validators_unit.py` (override resolves `apps/`,
  no `src/` violation; SC-006 declared-but-absent still blocks under strict).
* Non-reversal of #3783: `tests/cross_cutting/misc/test_acceptance_support.py`
  `test_no_override_still_blocks_strict` pins the exact `path_violations` payload and full
  `format_errors()` string beside the untouched `test_lenient_downgrades_path_conventions_to_warning`;
  the accept-boundary fail-closed and one-read cases live in the same file.
* Reader contract (subkey-only C-011, typo/malformed/lenient, one read NFR-002):
  `tests/specify_cli/config/test_path_conventions_reader.py`.

## More Information

* Builds on the honesty settlement PR #3783 (#3730/#3085); this ADR is explicitly additive to it.
* Deferred follow-on: layout auto-detection via `manage.py`/`go.mod` signals and research-shape accept
  relaxation, tracked as #2744.
* Reader: `src/specify_cli/config/path_conventions.py`. Merge site: `src/specify_cli/validators/paths.py`
  (`validate_mission_paths`, `_remap_declared_paths`). Seam wiring:
  `src/specify_cli/acceptance/summary_core.py` (`evaluate_path_conventions`). Canonical key set:
  `src/specify_cli/mission.py` (`VALID_PATH_KEYS`).
