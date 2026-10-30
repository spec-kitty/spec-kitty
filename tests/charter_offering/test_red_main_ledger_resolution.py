"""The repository's own activation ledger resolves against the fetched packs (#6693).

``.kittify/charter/activation.yaml`` is the single authority for what this
repository activates (ADR ``2026-10-19-1``), and the artifacts it names live in
the *fetched* charter packs — ``packs/built-in`` plus the repo-local org pack
``packs/internal`` — not in the tracked source tree. So an upstream change that
moves an artifact to another kind (as ``spec-kitty-open-packs#74`` did for the
red-main rule, #6693) leaves the ledger naming something no layer provides.

Two surfaces go wrong when that happens, and both are silent unless something
checks them:

* the **allow** side: an activated id that resolves to nothing renders as
  ``Charter catalog miss for <kind>:<id>; cause=missing_artifact`` on every
  governed command, so the rule it was meant to activate stops being delivered;
* the **deny** side: a denied id no layer provides is reported by
  ``spec-kitty doctor charter-packs`` as ``DENY_UNKNOWN_ID``.

These tests pin both, through the production readers the CLI itself uses
(:func:`~charter.activation.activation_ledger.load_activation_ledger`,
:meth:`~charter.activation.identity_index.IdentityIndex.build` and
:func:`~charter.activation.activation_ledger.ledger_findings`), so the next
re-kinding upstream fails here instead of in a warning nobody reads.

The negative assertions are paired with a positive control on the same index
(``test_known_good_ids_resolve_through_the_same_index``): a probe that cannot
see an artifact which *is* present cannot prove anything about one that is
absent.
"""

from __future__ import annotations

import pytest

from charter.activation.activation_ledger import (
    ActivationLedger,
    load_activation_ledger,
    ledger_findings,
)
from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import ArtifactKind
from tests.charter_offering.conftest import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

#: The red-main rule's file stem. It is the same stem in both packs and in both
#: kinds: ``spec-kitty-open-packs#74`` moved the artifact from a procedure to a
#: directive without renaming its file, so the config id is stable and only the
#: activation key it belongs under moves (#6693).
_RED_MAIN_STEM = "red-main-release-discipline"

#: Ids that must resolve for the positive control: a directive spelling both as
#: its file stem and as its declared id, plus a procedure, so the probe is shown
#: to work for more than one kind and more than one spelling.
_KNOWN_GOOD: tuple[tuple[ArtifactKind, str], ...] = (
    (ArtifactKind.DIRECTIVE, "034-test-first-development"),
    (ArtifactKind.DIRECTIVE, "DIRECTIVE_034"),
    (ArtifactKind.PROCEDURE, "test-first-bug-fixing"),
)


@pytest.fixture(scope="module")
def ledger() -> ActivationLedger:
    """This repository's activation ledger, read exactly as the CLI reads it."""
    return load_activation_ledger(REPO_ROOT, report_stray=False)


@pytest.fixture(scope="module")
def identity_index() -> IdentityIndex:
    """One identity index over the project + org + built-in pack chain."""
    return IdentityIndex.build(REPO_ROOT)


def test_every_activated_id_resolves_in_the_pack_chain(ledger: ActivationLedger, identity_index: IdentityIndex) -> None:
    """No activated id may name an artifact no layer provides (the catalog-miss class)."""
    unresolved = [f"{kind.plural}:{token}" for kind, tokens in ledger.allow for token in tokens or () if not identity_index.knows(kind, token)]

    assert unresolved == [], (
        "the activation ledger names artifacts no layer provides: "
        f"{unresolved}. Either the artifact moved kind/was renamed upstream (repoint the "
        "ledger, as #6693 did for the red-main rule) or the entry is stale."
    )


def test_no_denied_id_names_an_artifact_no_layer_provides(ledger: ActivationLedger, identity_index: IdentityIndex) -> None:
    """A deny entry for an id no layer provides is the doctor's ``DENY_UNKNOWN_ID`` residue."""
    stale = [f"{kind.plural}:{token}" for kind, tokens in ledger.deny for token in tokens if not identity_index.knows(kind, token)]

    assert stale == [], (
        "the deny list names artifacts no layer provides: "
        f"{stale}. `spec-kitty doctor charter-packs` reports this as DENY_UNKNOWN_ID; "
        "remove the stale deny entry (its own remedy text) rather than leaving it to rot."
    )


def test_doctor_reports_no_deny_unknown_id(ledger: ActivationLedger) -> None:
    """The doctor's own read of the same ledger agrees: no store error, no unknown deny id."""
    findings = ledger_findings(REPO_ROOT)

    assert findings.errors == (), f"the activation ledger raised a doctor error: {[f.to_dict() for f in findings.errors]}"
    unknown_deny = [finding for finding in findings.warnings if finding.code == "DENY_UNKNOWN_ID"]
    assert unknown_deny == [], f"DENY_UNKNOWN_ID survived: {[f.to_dict() for f in unknown_deny]}"


def test_red_main_rule_is_activated_as_a_directive(ledger: ActivationLedger) -> None:
    """The concrete claim of #6693: the rule is an activated directive, not a procedure.

    Asserting both halves matters. Asserting only the directive half would stay
    green if the retired procedure entry came back beside it, which is exactly
    the state (an activated id that resolves to nothing) the sibling test above
    exists to catch.
    """
    activated_directives = ledger.allow_for(ArtifactKind.DIRECTIVE) or ()
    activated_procedures = ledger.allow_for(ArtifactKind.PROCEDURE) or ()

    assert _RED_MAIN_STEM in activated_directives, (
        f"the red-main rule must be activated as a directive (RED_MAIN_RELEASE_DISCIPLINE); activated directives: {sorted(activated_directives)}"
    )
    assert _RED_MAIN_STEM not in activated_procedures, (
        "the retired red-main procedure is still activated; the packs ship the rule as a "
        f"directive now (open-packs#74, #6693). activated procedures: {sorted(activated_procedures)}"
    )
    assert _RED_MAIN_STEM not in ledger.deny_for(ArtifactKind.PROCEDURE), "the retired procedure is still named in the deny list, which no layer can satisfy"


def test_known_good_ids_resolve_through_the_same_index(identity_index: IdentityIndex) -> None:
    """Positive control: the probe can see artifacts that are present.

    Same index, same lookup, on ids that must resolve. Without this, a probe that
    silently sees nothing (a broken layer resolution, an unsynced worktree) would
    make the negative assertions above pass vacuously.
    """
    missing = [f"{kind.plural}:{token}" for kind, token in _KNOWN_GOOD if not identity_index.knows(kind, token)]

    assert missing == [], (
        "the identity index cannot see artifacts that ARE in the fetched packs: "
        f"{missing}. Run `make sync-packs`; if the tree is present, the layer resolution is broken."
    )
