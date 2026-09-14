"""WP04: close the composed-action guard launder seam by construction (#3412).

Mission ``expected-artifacts-loader-unification-01M1C9VQ``, FR-009/FR-010,
C-002/C-003. See
``kitty-specs/expected-artifacts-loader-unification-01M1C9VQ/contracts/guard-seam-invariant.md``
for the full invariant set this module drives.

The seam (``src/runtime/next/runtime_bridge_composition.py`` ~486-510):

    snapshot = _io_seam.gather_artifact_presence(...)   # :486 -- OUTSIDE the try
    try:
        return _cores.evaluate_guards_strict(snapshot)  # :503 -- inside the try
    except _cores.UnregisteredMissionFamilyError:        # :504 -- MUST stay pinned
        return []                                        # tolerant green

WP03 (commit 710a9589fd) made the org-tier reader
(``charter.activation.org_expected_artifacts._read_yaml_mapping``) raise
``MalformedManifestError`` for a present-but-broken org manifest instead of
silently swallowing it to ``None``. That raise now fires inside
``gather_artifact_presence`` at ``:486`` -- OUTSIDE the ``:502-504`` try --
so it propagates through the composed guard regardless of the ``:504``
handler, for ANY mission family (built-in or custom), before the
``blocking_artifact_names`` None-vs-``frozenset`` tri-state (C-002,
``cores.py:724``) is ever consulted.

This module is essentially test-only (WP04's Objective): the ``:504``
handler is ALREADY pinned to ``UnregisteredMissionFamilyError`` only, and
``gather_artifact_presence`` is ALREADY outside the try in the live code, so
T015 goes GREEN purely from WP03's propagation -- no production ``except``
edit is needed here. This module's job is to prove that by construction
(T015), lock it durably against a future broadening (T016), and
characterize the still-tolerant absent-manifest path (T017).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from charter.offering.missions.repository import MalformedManifestError
from runtime.next import runtime_bridge_composition as composition

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# A mission family deliberately absent from
# ``runtime_bridge_cores._GUARD_TABLES`` (research / documentation /
# software-dev / plan) -- the custom-family launder path this WP closes.
_CUSTOM_MISSION_FAMILY = "acme-widget-mission"
_CUSTOM_ACTION = "widget-step"

_BROKEN_ORG_MANIFEST_YAML = "schema_version: [unterminated flow seq\n"


def _write_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    """Write ``<repo_root>/.kittify/config.yaml`` with the canonical
    ``charter_packs.org.packs`` registry (CR-04 canonical shape; see
    ``tests/doctrine/drg/test_org_pack_config_cr04_charter_packs.py``).
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, local_path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_broken_org_manifest(org_root: Path, mission_family: str) -> Path:
    """Write a REAL YAML-syntax-broken ``expected-artifacts.yaml`` at the
    org-tier path ``<org_root>/missions/<mission_family>/expected-artifacts.yaml``
    (contract C-4)."""
    target_dir = org_root / "missions" / mission_family
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "expected-artifacts.yaml"
    manifest_path.write_text(_BROKEN_ORG_MANIFEST_YAML, encoding="utf-8")
    return manifest_path


def _fake_successful_execute_result() -> MagicMock:
    """A minimal stand-in for ``StepContractExecutionResult`` that flows
    cleanly through ``_dispatch_via_composition``'s defensive ``getattr``
    reads of ``invocation_ids`` / ``steps`` (mirrors
    ``tests/integration/test_custom_mission_runtime_walk.py``'s
    ``fake_result`` pattern)."""
    result = MagicMock()
    result.invocation_ids = ()
    result.steps = ()
    return result


# ---------------------------------------------------------------------------
# T015 -- [RED-first] integration regression: malformed org manifest
# propagates through the REAL composed-action guard entry point.
# ---------------------------------------------------------------------------


class TestMalformedOrgManifestPropagatesThroughComposedGuard:
    @pytest.mark.regression
    def test_malformed_org_manifest_propagates_through_composed_guard(self, tmp_path: Path) -> None:
        """#3412: a custom mission family + a YAML-syntax-broken ORG
        ``expected-artifacts.yaml``, driven through the real composed-action
        guard entry point ``_dispatch_via_composition`` (``repo_root``
        threaded at ``composition.py:637-638``), must raise
        ``MalformedManifestError`` -- and the guard result must NEVER
        degrade to ``[]``. See
        ``contracts/guard-seam-invariant.md``'s
        ``test_malformed_org_manifest_propagates_through_composed_guard``.

        Was RED on the pre-WP03 code (``org_expected_artifacts.py`` warned
        and returned ``None`` for a present-but-broken org file, laundering
        it into "not found" -> ``blocking_artifact_names=None`` ->
        ``UnregisteredMissionFamilyError`` -> caught at ``:504`` -> ``[]``);
        GREEN once WP03's fail-loud reader lands on this branch (verified by
        checking out the pre-WP03 reader file in isolation -- see this WP's
        report for the RED-run evidence; not re-executed here since flipping
        production source mid-suite is not itself a test).
        """
        repo_root = tmp_path / "project"
        repo_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_broken_org_manifest(org_root, _CUSTOM_MISSION_FAMILY)
        _write_org_pack_config(repo_root, packs=[("acme", org_root)])

        feature_dir = tmp_path / "feature"
        feature_dir.mkdir()

        with (
            patch(
                "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
                return_value=_fake_successful_execute_result(),
            ),
            pytest.raises(MalformedManifestError) as excinfo,
        ):
            composition._dispatch_via_composition(
                repo_root=repo_root,
                mission=_CUSTOM_MISSION_FAMILY,
                action=_CUSTOM_ACTION,
                actor="test-actor",
                profile_hint=None,
                request_text=None,
                mode_of_work=None,
                feature_dir=feature_dir,
            )

        # I3: the malformed org manifest's own path is named in the error --
        # this is genuinely "your manifest is malformed", not a laundered
        # "unknown family" / empty result.
        assert "acme-widget-mission" in str(excinfo.value)


# ---------------------------------------------------------------------------
# T016 -- durability lock on the ``:504`` pin + explanatory comment.
# ---------------------------------------------------------------------------


def test_504_handler_is_pinned_to_unregistered_only() -> None:
    """FR-010: ``_check_composed_action_guard``'s ``except`` clause around
    ``evaluate_guards_strict`` must catch ``UnregisteredMissionFamilyError``
    and NOTHING else -- in particular, never ``MalformedManifestError`` /
    ``ManifestSchemaError``. A structural (AST) assertion rather than a
    behavioral one: this is the by-construction durability proof --
    broadening the handler (e.g. to
    ``except (UnregisteredMissionFamilyError, MalformedManifestError):``)
    would make this test fail immediately, catching the regression before
    it re-reddens
    ``test_malformed_org_manifest_propagates_through_composed_guard``
    (T015) at runtime.
    """
    source = inspect.getsource(composition._check_composed_action_guard)
    tree = ast.parse(source)

    try_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
    assert len(try_nodes) == 1, (
        "expected exactly one try/except in _check_composed_action_guard; "
        f"found {len(try_nodes)} -- guard-seam-invariant.md's shape assumption "
        "no longer holds, re-verify the seam by hand"
    )
    (guard_try,) = try_nodes
    assert len(guard_try.handlers) == 1, f"the guard's try must have exactly one except handler (never catch-all); found {len(guard_try.handlers)}"
    (handler,) = guard_try.handlers

    assert handler.type is not None, "the handler must name a type, never a bare `except:`"
    assert not isinstance(handler.type, ast.Tuple), (
        "the handler must catch a SINGLE exception type, not a tuple -- a tuple "
        "shape is exactly how #3412 would reopen (adding MalformedManifestError "
        "alongside UnregisteredMissionFamilyError)"
    )

    handler_type_source = ast.unparse(handler.type)
    assert handler_type_source == "_cores.UnregisteredMissionFamilyError", (
        "the composed guard's except clause must catch ONLY "
        f"UnregisteredMissionFamilyError; found {handler_type_source!r}. "
        "Broadening it re-opens the #3412 launder -- see "
        "contracts/guard-seam-invariant.md Invariant 2 (handler type-pinning)."
    )


def test_504_handler_body_never_names_malformed_manifest_error() -> None:
    """Belt-and-braces sibling of the structural pin test above: even a
    handler rename/refactor that keeps a single ``except`` clause must never
    spell ``MalformedManifestError`` or ``ManifestSchemaError`` in the
    handler's own ``except ...:`` line or body -- neither name has any
    legitimate reason to appear there. Scoped to the handler node's own
    source span (via :func:`ast.get_source_segment`), NOT the whole
    function -- the one-line explanatory comment immediately above the
    ``except`` clause (T017) legitimately names both error classes to
    document what must never be caught, and lives outside the handler
    node's span."""
    source = inspect.getsource(composition._check_composed_action_guard)
    tree = ast.parse(source)
    (guard_try,) = [node for node in ast.walk(tree) if isinstance(node, ast.Try)]
    (handler,) = guard_try.handlers

    handler_segment = ast.get_source_segment(source, handler)
    assert handler_segment is not None
    assert "MalformedManifestError" not in handler_segment
    assert "ManifestSchemaError" not in handler_segment


# ---------------------------------------------------------------------------
# T017 -- characterization: absent-manifest custom family stays tolerant-green.
# ---------------------------------------------------------------------------


def test_absent_manifest_still_tolerant_green(tmp_path: Path) -> None:
    """Characterization (NOT @regression): a custom mission family with NO
    ``expected-artifacts.yaml`` on any tier -- no org override, no built-in
    entry -- still returns ``[]`` via the unregistered-family tolerant path
    (``composition.py:504``). Proves T016's narrowed pin does not also
    narrow the legitimate absence case: absence still degrades to ``[]``;
    only MALFORMED (present-but-broken) manifests now propagate.

    Durability note (see also ``test_504_handler_is_pinned_to_unregistered_only``):
    if a future change broadens ``:504`` to also catch
    ``MalformedManifestError``, T015
    (``test_malformed_org_manifest_propagates_through_composed_guard``)
    re-reddens -- that is the intended durability signal, not this test.
    """
    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()

    failures = composition._check_composed_action_guard(
        "totally-unregistered-action",
        feature_dir,
        mission="totally-unregistered-custom-family",
        repo_root=None,
    )

    assert failures == []
