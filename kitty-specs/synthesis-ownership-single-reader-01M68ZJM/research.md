# Research — synthesis-ownership single reader (#6767)

Discovery for Mission `synthesis-ownership-single-reader-01M68ZJM`. Everything below was read
from the clone at `origin/main` (base `3a49d35f2f`) before any planning artifact was written.

## Evidence: the three readers today

| # | Site | Reads | Fallback | Raises |
| --- | --- | --- | --- | --- |
| A | `src/charter/activation/synthesizer/reach_only.py:150 _synthesized_slugs` → `_registered_slugs` → `reconcile.synthesized_node_urns` | manifest entries of the kind, URN `f"{entry.kind}:{entry.slug}"` | `_recorded_slugs` → `.kittify/charter/synthesized-artifacts.yaml` (`created_tactics`/`created_styleguides`) ∪ legacy `.kittify/charter/synthesized-tactics.yaml` | `SynthesisMembershipUnreadableError`, code `SYNTHESIS_MEMBERSHIP_UNREADABLE` (a `KittyInternalConsistencyError`) |
| B | `src/charter/activation/synthesizer/manifest.py:450 _synthesized_urns` → `_synthesized_sidecar_urn` | manifest entries of the kind + each entry's provenance sidecar `artifact_urn`; `adapter_id == "project-direct-write"` is *not* ownership | none | private `_SynthesisOwnershipUnreadableError(ManifestIntegrityError)`, uncoded |
| C | `src/specify_cli/cli/commands/charter/_synthesis.py:504 _extract_artifact_id_from_provenance` | its own `YAML(typ="safe")` parse of the sidecar, `artifact_urn.split(":", 1)[1]` | n/a | never (returns `None`) |

Call sites that must keep working:

- A → `reach_only.reach_only_ids` (`reach_only.py:215`), consumed by
  `charter/activation/action_governance_bundle.py:405` and `charter/activation/compiler.py:292-293`.
- B → `manifest.synthesis_owned_directive_ids` (`manifest.py:531`), re-exported through
  `charter.activation.api` (pinned by `tests/architectural/test_charter_activation_api_reexport.py`),
  consumed by `specify_cli/cli/commands/charter/_synthesis.py:140` and
  `specify_cli/cli/commands/charter/_collision_remedy.py:79`.
- C → `_load_written_artifacts_from_manifest` (`_synthesis.py:457`), the `charter synthesize --json`
  envelope; re-exported from `specify_cli/cli/commands/charter/__init__.py:80,190`.

Additional fact: `_manifest_slugs` (`reach_only.py:133`) is a *lenient* manifest read used only by
the write-side diff (`_first_time_slugs`, `append_synthesized_activations`). It answers "what did
the manifest say before this run", not "what did synthesis create", and its leniency is what keeps
a first-time append working on a partially-written tree. It is therefore not one of the three
readers and stays as it is.

## Decision 1 — the one reader is the manifest + sidecar reader (B's source of truth)

**Decision.** The single reader resolves ownership from the synthesis manifest *and* each listed
entry's provenance sidecar, keeping #6510's direct-write exclusion, and returns
`frozenset` of `<kind>:<id>` URNs. `reach_only` derives its slug ids from the same URNs.

**Why not A's manifest-entry-only rule.** `plan_project_registration`
(`charter/activation/project_registration.py:190-246`) writes a manifest entry *and* a
`project-direct-write` sidecar for every artifact `charter activate`/project registration
touches, for every kind. Treating every entry as synthesis-created (A's rule) therefore reports
hand-authored artifacts as synthesis-owned — the exact answer `reach_only_ids`' own docstring
("Hand-authored artifacts, hand-authored edges and org-required artifacts … never count") and
#6510's collision remedy forbid. B's rule is the documented contract; A's is the drift.

**Consequence worth naming.** A hand-authored, direct-write-registered tactic that some
synthesized-shape edge happens to target stops being reach-only and becomes a root again. That
matches the documented contract, and it is recorded in the changelog entry.

**Why not C.** C parses the same file a second time and cannot express ownership at all (no
direct-write exclusion, no kind check).

## Decision 2 — one fallback policy, applied to both failure sources

Per-entry sidecars make B's reader fail where A's could still answer. Today a *missing sidecar*
for a directive entry raises: the manifest records the file stem, not the directive id
(`PROJECT_001`), so without the sidecar the URN is genuinely unknowable — refusing is the only
honest answer there.

The unified policy therefore is:

1. Manifest absent (not even a dangling symlink) → empty set. Nothing was synthesized.
2. Manifest unreadable/invalid **or** the sidecar of an entry of the requested kind
   unreadable/invalid/missing → the created-artifacts record stands in for that kind (it lists
   every id synthesis has ever created, so it never under-counts — fail closed).
3. The record cannot answer (absent, unreadable, lists no id of the kind, or the kind — a
   directive — is not tracked there) → the one coded error.

This preserves #6454's refusal exactly (for a directive slate the record has no answer, so
`_collision_remedy`'s "ownership record unreadable" branch still fires), and it means a damaged
sidecar no longer refuses delivery when the record can answer. One rule, kind-agnostic.

## Decision 3 — keep the existing code, drop the private class

`SYNTHESIS_MEMBERSHIP_UNREADABLE` is already operator-visible: documented in
`docs/changelog/CHANGELOG.md:131` (#6454), rendered by `charter context` with its code and body
(`specify_cli/cli/commands/charter/context.py:241-246`), and asserted by
`tests/cli/test_charter_context_coded_error_6454.py` and
`tests/charter/synthesizer/test_reach_only_delivery.py:462-480`.

Renaming the code would be user-facing churn for no gain, so the one error keeps the name
`SynthesisMembershipUnreadableError` and the code `SYNTHESIS_MEMBERSHIP_UNREADABLE`, gains the
sidecar/manifest/record metadata (`record_path`, `offending_artifact`, `reason`) that the collision
remedy needs, and moves into the error taxonomy module so both readers can raise it without a
cycle. The private `_SynthesisOwnershipUnreadableError` is deleted; `_collision_remedy` catches the
coded error (keeping its `ManifestIntegrityError` catch for the genuine hash-mismatch case).

## Decision 4 — the reader lives in `manifest.py`, not a new module

`manifest.py` already owns `MANIFEST_PATH`, the manifest models and IO, and the sidecar path
validation (`_validate_manifest_path`, `_resolve_under_repo`). `reach_only.py` already imports from
it, so putting the reader there is one direction of dependency and no new boundary (C-002). The
created-artifacts record's read/write primitives move there too, so both records and their readers
have one home; `reach_only` keeps the activation policy (eligibility, first-time diff, config
writes, warning text).

Alternative considered: a new `ownership.py`. Rejected because it would import `manifest` while
`manifest` must import it for `synthesis_owned_directive_ids` (a cycle needing a function-level
import), and the issue's ask is convergence, not a new package boundary.

## Decision 5 — the display path wraps the strict sidecar reader

`_extract_artifact_id_from_provenance(prov_path)` becomes a wrapper over the one sidecar reader
taking `(repo_root, entry)`, and catching the coded error to return `None`. It keeps its never-raise
contract (the strict-JSON envelope must survive a damaged record) but loses its own YAML parse, and
gains the strict reader's path containment and URN-kind validation.

One deliberate narrowing: a sidecar whose `artifact_urn` kind does not match the manifest entry's
kind now yields `None` instead of a garbage id.

## Open questions (for plan/tasks)

1. Does any gate pin the *number* of manifest readers (a dead-symbol or duplication check) that the
   deleted private function would trip? Needs a search of `scripts/` and the architectural tests
   during tasks.
2. `tests/charter/synthesizer/test_reach_only_delivery.py` builds manifests without sidecars in one
   helper (`_write_manifest`). Fixtures must gain sidecars so they describe a real synthesis tree;
   check no other suite builds a manifest-then-reach-only fixture the same way.
3. The `charter synthesize --json` envelope is asserted in several suites
   (`tests/specify_cli/cli/commands/charter/test_synthesis_*.py`); confirm none of them relies on
   the lenient parser accepting a sidecar the strict reader rejects.
