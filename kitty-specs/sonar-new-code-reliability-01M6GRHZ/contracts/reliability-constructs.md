# Contracts: the three reliability constructs and what must stay true

These are the invariants this mission's guard (`tests/architectural/test_new_code_reliability_shapes.py`)
pins. They are internal contracts between a module and the analyzers/readers that consume it — no
public API changes — but a change that breaks one of them silently reintroduces the SonarCloud
findings the mission removed.

## C-01 — The `events tail` default ledger is derived from the closed kind registry

- **Surface**: `src/specify_cli/cli/commands/events.py` (`_LOG_KIND_MEMBERS`, `_LogKind`,
  `_DEFAULT_LOG_KIND`, `_LOG_KIND_DEFAULT`).
- **Guarantee**: exactly one constant names the default kind (`_DEFAULT_LOG_KIND = "status"`), and
  the `Typer` default is the `_LogKind` member whose *value* is that constant. `_LOG_KIND_MEMBERS`
  maps `kind.upper() -> kind`, and `SUPPORTED_LOG_KINDS` remains the only list of tail-able ledgers.
- **Shape requirement**: the default is resolved with a name subscript (`_LogKind[...]`), never by
  calling the class (`_LogKind("status")`). The functional-API `Enum` is a class and the call is
  valid Python, but SonarCloud's `python:S5756` reads it as a call on a non-callable and scores the
  module BLOCKER.
- **Failure mode**: a new literal default (`_LogKind("status")`) reintroduces `S5756`; a second
  source of the kind list breaks the closed-registry authority.

## C-02 — `_default_active_charter_service` binds its service class before naming it

- **Surface**: `src/charter/activation/compiler.py::_default_active_charter_service`.
- **Guarantee**: both branches return an instance of
  `charter.activation.resolver.ActiveCharterService` — the builder's wrapper when `repo_root` is
  given, the `pack_context=None` wrapper otherwise. The import stays function-local (module scope is
  what it avoids).
- **Shape requirement**: the `import` statement precedes the annotated assignment that mentions the
  name in the same function body. `from __future__ import annotations` keeps the annotation inert,
  so this is about which statement comes first, not about runtime order.
- **Failure mode**: moving the import back below the annotation reintroduces `python:S3827`.

## C-03 — The tracked-`meta.json` refusal path returns a notice exactly when git cannot supply an identity

- **Surface**: `src/specify_cli/migration/backfill_identity.py::_tracked_mission_id` and
  `src/specify_cli/upgrade/tracked_meta_notice.py::tracked_meta_refusal`.
- **Guarantee**: for an unavailable tracked copy the caller returns `(None, <coded notice>)`; for a
  usable one it returns `(<mission_id>, None)`; an unusable copy never yields a minted identity.
- **Shape requirement**: a caller inside `if tracked.unavailable:` states the non-`None` refusal as
  an invariant (`assert refusal is not None`) rather than re-testing a condition the analyzer can
  prove false (`pythonbugs:S2583`). `tracked_meta_refusal` documents that precondition; a caller
  outside that guard must still branch on `None`.
- **Failure mode**: re-testing the dead condition reintroduces `S2583`; removing the `None` branch
  from the helper without this note would mislead a future second caller.

## Out of contract (deliberately)

- The SonarCloud scan scope of `acceptance-jvm` (MAIN code on purpose).
- The nineteen pre-existing reliability findings outside the new-code window.
- No `NOSONAR` marker, `sonar.issue.ignore` rule, exclusion or scan-scope change is part of any of
  the three contracts above; each fix removes the misread construct instead.
