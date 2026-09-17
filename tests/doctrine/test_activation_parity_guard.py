"""Doctrine-tier entry point for the FR-005/NFR-002 config<->derived parity guard.

WP05 (mission ``unify-charter-activation-surfaces-01KX5SJ9``). Before this WP,
``charter.activation.consistency_check.run_consistency_check`` was reachable only from
the CLI (``spec-kitty charter pack consistency-check``, wired at
``src/specify_cli/cli/commands/charter/pack.py:31-47``). NFR-002 requires the
fail-closed config<->derived parity guard to bite in the test suite too, not
only when an operator remembers to run the CLI by hand -- this module is that
entry point (T019), plus the non-vacuity self-tests (T020) that prove each
new assertion actually fires on a planted divergence rather than being green
for the wrong reason.

Covers:
- ``test_this_project_charter_pack_is_coherent``: T019 suite-tier entry point.
- ``test_config_directive_absent_from_references_bites`` /
  ``test_config_directive_present_in_references_is_coherent``: T017 forward
  ID-level parity (the #2524 dangler class), RED/GREEN pair.
- ``test_orphan_paradigm_reference_bites``: T017 reverse ID-level parity
  (paradigms only -- see ``consistency_check._check_reference_id_parity``
  docstring for why the reverse check is scoped to paradigms).
- ``test_config_kind_absent_from_graph_bites``: T018 KIND-level config<->DRG
  parity.
- ``test_consistency_check_does_not_import_freshness_or_specify_cli``: layer
  discipline pinned per the WP -- ``consistency_check`` must stay disjoint
  from ``freshness/computer.py`` (a ``specify_cli`` module that imports
  ``charter`` back) and must never import ``specify_cli`` at all.

Post-WP05 adversarial-squad findings on this same guard (mission
``unify-charter-activation-surfaces-01KX5SJ9``, PR #2528):

- ``test_org_overlay_activated_artefact_resolves_for_parity``: #2529 --
  ``_check_reference_id_parity`` must resolve org/project-overlay
  artefacts (``org_roots``), not built-in doctrine only; otherwise a
  config-activated ORG artefact silently skips the parity check instead of
  being caught as a dangler.
- ``test_corrupt_references_yaml_fails_closed`` /
  ``test_references_yaml_malformed_schema_fails_closed`` /
  ``test_references_yaml_absent_is_still_a_clean_skip``: #2530 -- an
  unreadable/corrupt ``charter.yaml`` (IC-04: re-homed from ``references.yaml``)
  must surface a ``verification_errors`` finding and NOT-coherent report,
  distinct from the legitimate "not yet synthesized" no-op skip (file
  simply absent).
- ``test_drg_load_failure_fails_closed``: #2530 -- the KIND-level
  config<->DRG check must fail closed the same way on a DRG load/validate
  failure, not silently return an empty (passing) result.
- ``test_paradigm_canonical_id_equals_config_stem_invariant``: pins the
  invariant the reverse paradigm parity check depends on (paradigm
  canonical id == config stem, no normalization step) via the same
  resolver bridge the forward check uses, so it cannot silently rot.

IC-04 (consolidate-charter-bundle / WP04) re-point: both parity reads --
``_load_raw_activation_lists`` (activation) and ``_load_reference_ids_by_kind``
(catalog) -- now read from ``charter.yaml`` instead of ``config.yaml``
direct-embedding / the retired ``references.yaml``. The catalog fixtures below
use :func:`_write_charter_yaml_catalog` (writing ``.kittify/charter/
charter.yaml``'s ``catalog.references``) in place of the retired
``_write_references`` (``references.yaml``). New tests
(``test_activation_reads_charter_yaml_pointer_not_stale_config`` /
``test_dangling_charter_pointer_fails_closed_for_activation``) close the
WP02<->WP04 transient-parity coupling this WP's Definition of Done calls out:
the activation-list parity read and ``PackContext.from_config`` (WP02) must
resolve the exact same source when a ``charter:`` pointer is present.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.consistency_check import run_consistency_check
from charter.activation.invocation_context import ProjectContext

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]

# A real, stable built-in directive whose canonical id (``DIRECTIVE_001``)
# DIFFERS from its config stem (``001-architectural-integrity-standard``) --
# exercises the exact stem<->canonical-id normalization the guard depends on
# (C-006: "a stem that fails to normalize must be rejected, never silently
# dropped").
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_REAL_DIRECTIVE_CANONICAL = "DIRECTIVE_001"
# A real, stable built-in paradigm whose id == its config stem (paradigms are
# rendered 1:1, never DRG-transitively expanded).
_REAL_PARADIGM_STEM = "atomic-design"


def _write_config(tmp_path: Path, content: str) -> Path:
    """Write a .kittify/config.yaml with the given content; return .kittify/."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")
    return kittify


def _write_charter_yaml_catalog(kittify: Path, ref_entries: list[dict[str, str]]) -> Path:
    """Write a minimal ``.kittify/charter/charter.yaml`` carrying the given
    ``catalog.references`` entries (IC-04: replaces the retired
    ``references.yaml`` -- ``charter.yaml``'s ``catalog`` mirrors that file's
    body verbatim, see ``charter.activation.schemas.CharterCatalog``). Returns the
    written path.
    """
    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0.0",
        "governance": {},
        "directives": {},
        "catalog": {
            "mission": "software-dev",
            "template_set": "software-dev-default",
            "languages": ["python"],
            "references": ref_entries,
        },
    }
    yaml = YAML()
    yaml.default_flow_style = False
    charter_yaml_path = charter_dir / "charter.yaml"
    with charter_yaml_path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)
    return charter_yaml_path


def _reference_entry(ref_id: str, kind: str) -> dict[str, str]:
    return {
        "id": ref_id,
        "kind": kind,
        "title": "x",
        "summary": "x",
        "source_path": "",
        "local_path": "x",
    }


def _write_org_directive(org_pack_root: Path, *, stem: str, canonical_id: str) -> None:
    """Write a minimal org-pack-only directive artefact for #2529 org resolution.

    ``resolve_artifact_urn``'s ``org_roots`` scan
    (``charter.activation.kind_vocabulary._scan_roots``) treats every org root the same
    way it treats the built-in doctrine root: it looks for
    ``<root>/<plural>/built-in/*.yaml``. This mirrors that exact shape so the
    fixture is reachable through the precise code path Fix A repairs -- not
    the (different) ``<root>/<plural>/*.yaml`` layout used by
    ``charter.offering.service.DoctrineService``'s org layer elsewhere in the suite.
    """
    directive_dir = org_pack_root / "directives" / "built-in"
    directive_dir.mkdir(parents=True, exist_ok=True)
    (directive_dir / f"{stem}.directive.yaml").write_text(
        f"schema_version: '1.0'\nid: {canonical_id}\ntitle: x\nintent: x\nenforcement: required\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# T019: doctrine-test-tier entry point -- the guard now bites in the suite.
# ---------------------------------------------------------------------------


def test_this_project_charter_pack_is_coherent() -> None:
    """The guard runs against this project's own config/doctrine/DRG.

    Previously this only happened when an operator ran
    ``spec-kitty charter pack consistency-check`` by hand; this test makes
    it a suite-tier gate (NFR-002) so a #2524-style divergence fails
    locally, not only at CI or on manual invocation.
    """
    ctx = ProjectContext.from_repo(_REPO_ROOT)
    report = run_consistency_check(ctx)

    assert report.coherent, (
        "Charter pack consistency check failed for this project:\n"
        f"unknown_references={report.unknown_references}\n"
        f"missing_from_doctrine={report.missing_from_doctrine}\n"
        f"kind_violations={report.kind_violations}\n"
        f"reference_id_divergences={report.reference_id_divergences}\n"
        f"graph_kind_gaps={report.graph_kind_gaps}\n"
        f"suggestions={report.suggestions}"
    )


# ---------------------------------------------------------------------------
# T020: non-vacuity self-tests -- a planted divergence MUST make the guard bite.
# ---------------------------------------------------------------------------


def test_config_directive_absent_from_references_bites(tmp_path: Path) -> None:
    """#2524 dangler class: config activates a directive, charter.yaml's
    catalog lacks it."""
    kittify = _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )
    # Compiled WITHOUT the activated directive -- the exact #2524 shape (live
    # in config, dangling in the compiled reference set).
    _write_charter_yaml_catalog(kittify, [])

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert f"directive/{_REAL_DIRECTIVE_STEM}" in report.reference_id_divergences
    assert any("does not resolve in .kittify/charter/charter.yaml's catalog" in s for s in report.suggestions)


def test_config_directive_present_in_references_is_coherent(tmp_path: Path) -> None:
    """Sibling GREEN case: proves the RED above is a real assertion, not env noise."""
    kittify = _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )
    _write_charter_yaml_catalog(
        kittify,
        [_reference_entry(f"DIRECTIVE:{_REAL_DIRECTIVE_CANONICAL}", "directive")],
    )

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is True
    assert report.reference_id_divergences == []


def test_orphan_paradigm_reference_bites(tmp_path: Path) -> None:
    """Reverse direction (paradigms only): a compiled paradigm with no config activation.

    Paradigms are rendered 1:1 from ``config.activated_paradigms`` with no
    DRG-transitive expansion, so this is the one kind where a reverse
    (catalog -> config) check is sound -- see
    ``consistency_check._check_reference_id_parity``.
    """
    kittify = _write_config(
        tmp_path,
        "activated_paradigms:\n  - domain-driven-design\n",
    )
    _write_charter_yaml_catalog(
        kittify,
        [
            _reference_entry("PARADIGM:domain-driven-design", "paradigm"),
            # Orphan: resolves in the catalog but not activated in config.
            _reference_entry(f"PARADIGM:{_REAL_PARADIGM_STEM}", "paradigm"),
        ],
    )

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert f"paradigm/{_REAL_PARADIGM_STEM}" in report.reference_id_divergences


def test_config_kind_absent_from_graph_bites(tmp_path: Path) -> None:
    """KIND-level (T018): config activates directives, but 'directives' is
    excluded from ``activated_kinds`` -- no directive kind can survive the
    KIND-level activation gate, so the graph shows zero directive nodes even
    though config carries directive IDs.

    Campsite note (mission ``drg-relation-parity-activation-gate-01KY48PD``,
    WP02/T007): ``_check_graph_kind_parity`` was re-pointed KIND-granular ->
    per-ID (a deliberate behavior upgrade, plan.md IC-02); this test's own
    ``graph_kind_gaps`` assertion is the one collateral break from that
    re-point, and this file has no owning WP in that mission, so the fix
    lands here directly (rationale-backed leeway, no ownership overlap) --
    the finding now names the specific activated stem, not just its kind.
    """
    _write_config(
        tmp_path,
        (
            f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"
            "activated_kinds:\n"
            "  - tactics\n"
            "  - paradigms\n"
            "  - styleguides\n"
            "  - toolguides\n"
            "  - procedures\n"
            "  - agent_profiles\n"
            "  - mission_step_contracts\n"
            "  - templates\n"
            "  - assets\n"
        ),
    )
    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert f"directive/{_REAL_DIRECTIVE_STEM}" in report.graph_kind_gaps
    assert any("does not survive in the activation-filtered DRG graph" in s for s in report.suggestions)


def test_config_kind_present_in_activated_kinds_is_coherent(tmp_path: Path) -> None:
    """Sibling GREEN case for T018: proves the RED above is a real assertion."""
    _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )
    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.graph_kind_gaps == []


# ---------------------------------------------------------------------------
# IC-04 (WP04): activation-list parity must read charter.yaml via the
# ``charter:`` pointer, not a possibly-stale ``config.yaml`` direct embed --
# closing the WP02<->WP04 transient-parity coupling (the guard used to read a
# DIFFERENT source than ``PackContext.from_config`` -- WP02 -- once a project
# migrated to a charter.yaml pointer).
# ---------------------------------------------------------------------------


def test_dangling_charter_pointer_fails_closed_for_activation(tmp_path: Path) -> None:
    """#2530 re-homed onto charter.yaml: a ``charter:`` pointer naming a
    charter.yaml that does not exist must fail closed (verification_errors
    populated, report NOT coherent) -- never a silent fallback to the legacy
    config-embedded activation, and never an unhandled exception past
    ``run_consistency_check``.

    ``ProjectContext`` is constructed directly (bypassing ``.from_repo()``)
    because ``PackContext.from_config`` (WP02) ALREADY fails closed on this
    exact dangling-pointer condition at context-construction time -- this
    test isolates ``run_consistency_check``'s OWN fail-closed catch around
    ``_load_raw_activation_lists`` (the code path this WP adds), not WP02's
    pre-existing one.
    """
    _write_config(
        tmp_path,
        (f"charter: .kittify/charter/charter.yaml\nactivated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n"),
    )
    # No .kittify/charter/charter.yaml written -- the pointer dangles.

    ctx = ProjectContext(repo_root=tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert report.verification_errors, "a dangling charter.yaml pointer must be reported as 'could not verify', not silently treated as 'nothing activated'"
    assert any("charter.yaml" in entry for entry in report.verification_errors)


# ---------------------------------------------------------------------------
# #2529: the guard must resolve org/project-overlay artefacts, not
# built-in-only.
# ---------------------------------------------------------------------------


def test_org_overlay_activated_artefact_resolves_for_parity(tmp_path: Path) -> None:
    """#2529: an org-only activated artefact must be caught, not silently skipped.

    Before the fix, ``_check_reference_id_parity`` called
    ``resolve_artifact_urn`` with no ``org_roots``, so a config-activated
    ORG-only directive raised ``UnknownArtifactIdError``; the guard's
    ``except UnknownArtifactIdError: continue`` swallowed it silently and
    ``reference_id_divergences`` stayed empty even though the artefact is
    dangling exactly like the #2524 class (activated in config, absent from
    the compiled reference set) -- while ``compiler.py``'s equivalent
    resolver call, which does NOT catch that exception, crashes on the exact
    same stem. That is a false negative, not a best-effort skip. Threading
    ``org_roots=list(pack_context.pack_roots[1:])`` into the guard's
    ``resolve_artifact_urn`` call closes it: the org-only stem now resolves
    and the real dangler is caught.
    """
    org_pack_root = tmp_path / "org-pack"
    _write_org_directive(org_pack_root, stem="org-only-directive", canonical_id="DIRECTIVE_ORG_ONLY")

    kittify = _write_config(
        tmp_path,
        (f"activated_directives:\n  - org-only-directive\ndoctrine:\n  org:\n    packs:\n      - name: test-org\n        local_path: {org_pack_root.as_posix()}\n"),
    )
    # Compiled WITHOUT the org directive -- the exact #2524 dangler shape.
    _write_charter_yaml_catalog(kittify, [])

    ctx = ProjectContext.from_repo(tmp_path)
    assert ctx.pack_context is not None
    assert len(ctx.pack_context.pack_roots) == 2, (
        "fixture sanity check: exactly one org pack root must be configured so this test actually exercises org resolution"
    )

    report = run_consistency_check(ctx)

    # This is the assertion Fix A controls: without org_roots, the stem
    # raises UnknownArtifactIdError inside _check_reference_id_parity and is
    # silently skipped, leaving reference_id_divergences empty even though
    # the artefact is a genuine dangler. With org_roots threaded, the stem
    # resolves and the missing compiled entry is correctly reported.
    #
    # (`unknown_references` also fires here via a separate, pre-existing
    # gap: `_collect_all_doctrine_ids`/`CharterPackManager.list_available`
    # is called with no `layer_roots` either, so it never sees org
    # artefacts. That is a different call site than the one #2529 reports
    # and is out of scope for this fix -- it does not change what this
    # assertion demonstrates about `_check_reference_id_parity`.)
    assert "directive/org-only-directive" in report.reference_id_divergences
    assert report.coherent is False


# ---------------------------------------------------------------------------
# #2530: the guard must fail closed on unreadable/corrupt input, distinct
# from the legitimate "not yet synthesized" no-op skip.
# ---------------------------------------------------------------------------


def test_corrupt_references_yaml_fails_closed(tmp_path: Path) -> None:
    """#2530: unparseable charter.yaml must surface a verification error.

    Before the fix, ``_load_reference_ids_by_kind`` caught every exception
    from the YAML parse and returned ``None`` -- the exact same return value
    used for "no charter synthesis has run yet". ``_check_reference_id_parity``
    then treated a truncated/corrupt file identically to a legitimately
    absent one: "nothing to check against", reporting ``coherent=True``.
    """
    kittify = _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )
    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    # Truncated YAML: an unterminated flow mapping -- a real ParserError,
    # not a benign empty-document parse.
    (charter_dir / "charter.yaml").write_text("catalog: {references: [{id: 'x'\n", encoding="utf-8")

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert report.verification_errors, "a corrupt charter.yaml must be reported as 'could not verify', not silently treated as an empty, passing result"
    assert any("charter.yaml" in entry for entry in report.verification_errors)
    assert any("could not verify config<->references parity" in s.lower() for s in report.suggestions)


@pytest.mark.parametrize(
    ("yaml_text", "expected_fragment"),
    [
        pytest.param(
            "- just\n- a\n- list\n",
            "does not contain a YAML mapping",
            id="non_mapping_document_root",
        ),
        pytest.param(
            "schema_version: '2.0.0'\n",
            "missing a valid 'catalog' mapping",
            id="catalog_not_a_mapping",
        ),
        pytest.param(
            "catalog:\n  mission: software-dev\n",
            "missing a valid 'references' list",
            id="references_not_a_list",
        ),
    ],
)
def test_references_yaml_malformed_schema_fails_closed(tmp_path: Path, yaml_text: str, expected_fragment: str) -> None:
    """#2530: a parseable-but-wrong-shape charter.yaml must fail closed too.

    Sibling of ``test_corrupt_references_yaml_fails_closed`` -- that test
    covers the YAML *parse* failure (``_load_reference_ids_by_kind``'s
    ``except Exception`` branch); these three parametrized cases cover the
    three ``isinstance`` shape guards that run AFTER a successful parse
    (document root not a mapping, ``catalog`` not a mapping, ``catalog.
    references`` not a list). Each must surface a ``CharterYamlCorruptError``-driven
    verification error and ``coherent=False``, never the "not yet
    synthesized" clean-skip return value (``None``) that a genuinely absent
    file gets.
    """
    kittify = _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )
    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(yaml_text, encoding="utf-8")

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert report.verification_errors, "a malformed-schema charter.yaml must be reported as 'could not verify', not silently treated as an empty, passing result"
    assert any(expected_fragment in entry for entry in report.verification_errors)
    assert any("could not verify config<->references parity" in s.lower() for s in report.suggestions)


def test_references_yaml_absent_is_still_a_clean_skip(tmp_path: Path) -> None:
    """Sibling GREEN case: 'not yet synthesized' (file simply absent) stays a
    legitimate no-op skip, distinct from the corruption cases above (#2530)."""
    _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )
    # No .kittify/charter/charter.yaml written at all.

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.verification_errors == []
    assert report.reference_id_divergences == []
    assert report.coherent is True


def test_drg_load_failure_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2530: a DRG load/validation failure must surface a verification error.

    Before the fix, ``_check_graph_kind_parity`` caught every exception from
    ``load_validated_graph`` (and from resolving ``ctx``'s required fields)
    and returned silently -- ``graph_kind_gaps`` stayed empty and the report
    was ``coherent=True`` even though the KIND-level check never actually
    ran. Unlike ``references.yaml``, the built-in DRG graph is always
    bundled with the package, so there is no legitimate "not yet
    synthesized" skip state here -- any load/validate failure is a genuine
    "could not verify".
    """
    _write_config(
        tmp_path,
        f"activated_directives:\n  - {_REAL_DIRECTIVE_STEM}\n",
    )

    def _raise_corrupt_drg(*_args: object, **_kwargs: object) -> None:
        raise ValueError("simulated corrupt/invalid DRG graph")

    monkeypatch.setattr("charter.activation._drg_helpers.load_validated_graph", _raise_corrupt_drg)

    ctx = ProjectContext.from_repo(tmp_path)
    report = run_consistency_check(ctx)

    assert report.coherent is False
    assert report.verification_errors, "a DRG load/validation failure must be reported as 'could not verify', not silently treated as an empty, passing result"
    assert any("could not verify config<->graph kind parity" in entry.lower() for entry in report.verification_errors)


# ---------------------------------------------------------------------------
# NIT: pin the invariant the reverse paradigm parity check depends on.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# T020: layer discipline -- the guard must stay disjoint from freshness /
# specify_cli. ``freshness/computer.py`` is a ``specify_cli`` module that
# imports ``charter``; ``charter.activation.consistency_check`` importing it back would
# be a cycle (and a layer-rule violation independent of the cycle -- see
# ``tests/architectural/test_layer_rules.py`` for the general charter
# !import specify_cli rule this test pins the specific case of).
# ---------------------------------------------------------------------------
