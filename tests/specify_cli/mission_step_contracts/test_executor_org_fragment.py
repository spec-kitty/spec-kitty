"""WP04 (#3530): the org ``drg/fragment.yaml`` layer reaches the executor path.

The mission-step composition dispatch resolved its DRG through
``StepContractExecutor._load_graph_degrading_malformed_org_pack``, which threaded
only ``org_roots`` (a pack's root-level ``*.graph.yaml``) and never the
``org_fragments`` layer. So a pack shipping only ``drg/fragment.yaml`` -- this
repo's own ``packs/internal`` shape -- was silently dropped on this path: the
branch-named silent drop this WP closes.

Red-first: :func:`test_valid_fragment_only_pack_node_reaches_merged_graph`
FAILS before T017 (the fragment node never reaches the merged graph) and passes
after ``org_fragments`` is threaded. This is deliberately a *valid* fragment --
the pre-existing degrade test in ``test_executor.py`` uses a *malformed* one and
only covers the graceful-degrade, never a valid fragment's nodes being folded.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest
import yaml

from charter.activation.drg_activation import load_org_drg
from charter.drg import resolve_existing_org_roots
from charter.mission_steps import MissionStepContract, MissionStepContractStep
from charter.offering.drg.org_pack_loader import OrgPackSchemaError
from charter.offering.drg.validator import DRGValidationError
from specify_cli.mission_step_contracts.executor import (
    StepContractExecutionContext,
    StepContractExecutor,
)

pytestmark = pytest.mark.fast

_EXECUTOR_LOGGER = "specify_cli.mission_step_contracts.executor"
_CHARTER_DRG_LOGGER = "charter.activation.drg_activation"
_TARGET_URN = "directive:OPERATOR_SIGNAL_CONTRACT"
_DROP_WARNING = "without this org pack's contribution"


def _register_pack(repo_root: Path, org_root: Path, *, name: str = "test-org") -> None:
    kit = repo_root / ".kittify"
    kit.mkdir(parents=True, exist_ok=True)
    (kit / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": name, "local_path": str(org_root)}]}}}),
        encoding="utf-8",
    )


def _write_fragment_pack(
    repo_root: Path,
    *,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]] | None = None,
    register: bool = True,
) -> Path:
    """Materialise a fragment-only org pack (``drg/fragment.yaml``, no root graph)."""
    org_root = repo_root.parent / "org-pack"
    (org_root / "drg").mkdir(parents=True, exist_ok=True)
    (org_root / "drg" / "fragment.yaml").write_text(
        yaml.safe_dump(
            {
                "pack_name": "test-org",
                "source_kind": "local_path",
                "source_ref": "org-pack",
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": nodes,
                "edges": edges or [],
            }
        ),
        encoding="utf-8",
    )
    if register:
        _register_pack(repo_root, org_root)
    return org_root


def test_valid_fragment_only_pack_node_reaches_merged_graph(tmp_path: Path) -> None:
    """A valid fragment-only pack's node must reach the executor's merged DRG.

    Red-first before T017: without ``org_fragments`` threading, this directive
    -- authored only in ``drg/fragment.yaml`` -- never entered the graph the
    composition dispatch resolves against.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fragment_pack(
        repo,
        nodes=[
            {
                "id": "OPERATOR_SIGNAL_CONTRACT",
                "kind": "directives",
                "title": "Operator-Signal Contract",
            }
        ],
    )
    roots = resolve_existing_org_roots(repo)

    graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, roots)

    assert _TARGET_URN in {str(node.urn) for node in graph.nodes}


def test_fragment_node_and_edge_are_folded_once_not_twice(tmp_path: Path) -> None:
    """No-double-fold: a pack in BOTH ``org_roots`` and ``org_fragments`` folds once.

    The fix threads ``org_fragments`` at the caller, NOT at the ``org_roots=``
    seam. Fixing at the seam would double-fold for the four callers that already
    pass both lists. This pins the caller-level guarantee: the fragment's node
    and edge appear exactly ``n`` (== 1) times in the merged graph, never ``2n``,
    even though ``resolve_existing_org_roots`` also returns this pack's root.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fragment_pack(
        repo,
        nodes=[
            {"id": "FRAG_DIR_A", "kind": "directives", "title": "Frag Directive A"},
            {"id": "FRAG_DIR_B", "kind": "directives", "title": "Frag Directive B"},
        ],
        edges=[{"source": "FRAG_DIR_A", "target": "FRAG_DIR_B", "relation": "refines"}],
    )
    roots = resolve_existing_org_roots(repo)
    assert roots, "pack must be resolved into org_roots for the dual-path check"

    graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, roots)

    node_count = sum(1 for node in graph.nodes if str(node.urn) == "directive:FRAG_DIR_A")
    edge_count = sum(
        1 for edge in graph.edges if (str(edge.source), str(edge.target), edge.relation.value) == ("directive:FRAG_DIR_A", "directive:FRAG_DIR_B", "refines")
    )

    assert node_count == 1
    assert edge_count == 1


def test_fragment_only_pack_does_not_emit_false_drop_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Warning honesty: a folded fragment-only pack is not warned as dropped.

    ``load_graph_or_dir`` cannot read a fragment-shaped pack (root graphs only),
    but its content DOES arrive via ``org_fragments``. Emitting the
    "without this org pack's contribution" WARNING would misattribute a folded
    pack as a dropped one, so the pre-probe degrades to DEBUG for it.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_fragment_pack(
        repo,
        nodes=[
            {
                "id": "OPERATOR_SIGNAL_CONTRACT",
                "kind": "directives",
                "title": "Operator-Signal Contract",
            }
        ],
    )
    roots = resolve_existing_org_roots(repo)

    with caplog.at_level(logging.WARNING, logger=_EXECUTOR_LOGGER):
        StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, roots)

    assert not [r for r in caplog.records if _DROP_WARNING in r.getMessage()]


def test_graphless_and_fragmentless_root_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Warning honesty: a root with no graph AND no loadable fragment warns.

    The honesty suppression is narrow -- it applies only when the fragment
    genuinely folds. A root that contributes nothing (no root ``*.graph.yaml``
    and no ``drg/fragment.yaml``) is a real drop and still emits the WARNING.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    empty_root = tmp_path / "empty-pack"
    empty_root.mkdir()

    with caplog.at_level(logging.WARNING, logger=_EXECUTOR_LOGGER):
        StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, [empty_root])

    warnings = [r for r in caplog.records if _DROP_WARNING in r.getMessage()]
    assert len(warnings) == 1


class _StubInvocationExecutor:
    """Never invoked: merged-graph validation fails before any step dispatch."""


def test_org_governance_selection_fails_loud_on_executor_path(
    tmp_path: Path,
) -> None:
    """The executor's own DRG build fails loud on a bad org governance selection.

    An org-tier ``governance-profile.yaml`` selecting a nonexistent artifact is
    minted as a dangling ``mission_type --scope--> <artifact>`` edge (WP04's real
    fix). The executor builds its graph through
    ``_load_graph_degrading_malformed_org_pack`` ->
    :func:`charter._drg_helpers.load_validated_graph`, whose ``assert_valid``
    raises :class:`~doctrine.drg.validator.DRGValidationError` naming the dangling
    target -- no dedicated governance-scope guard needed. Driven here through the
    production graph-build path (no injected ``graph``), so the merged-graph
    validation is the real escalation exercised; the stub invocation executor is
    never reached.
    """
    org_root = _write_fragment_pack(
        tmp_path,
        nodes=[{"id": "FRAG_MARKER", "kind": "directives", "title": "marker"}],
    )
    gov_dir = org_root / "mission_types" / "plan"
    gov_dir.mkdir(parents=True)
    (gov_dir / "governance-profile.yaml").write_text(
        yaml.safe_dump(
            {
                "id": "plan",
                "mission_type": "plan",
                "selected_directives": ["THIS_DIRECTIVE_DOES_NOT_EXIST"],
            }
        ),
        encoding="utf-8",
    )

    contract = MissionStepContract(
        id="c",
        schema_version="1.0",
        action="composer",
        mission="fixture",
        steps=[MissionStepContractStep(id="s", description="d")],
        gates=[],
    )
    executor = StepContractExecutor(
        repo_root=tmp_path,
        invocation_executor=_StubInvocationExecutor(),  # type: ignore[arg-type]
    )

    with pytest.raises(DRGValidationError, match=r"THIS_DIRECTIVE_DOES_NOT_EXIST"):
        executor.execute(
            StepContractExecutionContext(
                repo_root=tmp_path,
                mission="fixture",
                action="composer",
                actor="pytest",
                profile_hint="implementer-fixture",
            ),
            contract=contract,
        )


# ---------------------------------------------------------------------------
# Convergent LOW finding (mission doctrine-drg-silent-drop-boundary): a single
# malformed optional fragment must not evict its HEALTHY siblings' fragments.
# The pre-fix executor wrapped the whole ``load_org_drg`` call in one
# try/except, so one bad pack dropped the ENTIRE fragment layer with only a
# DEBUG note. The degrade is now per-pack inside ``load_org_drg``.
# ---------------------------------------------------------------------------

_HEALTHY_PACK_NAME = "healthy-org"
_MALFORMED_PACK_NAME = "malformed-org"
_HEALTHY_MARKER = "HEALTHY_SIBLING_MARKER"
_HEALTHY_MARKER_URN = f"directive:{_HEALTHY_MARKER}"


def _register_packs(repo_root: Path, entries: list[tuple[str, Path]]) -> None:
    """Register a MULTI-pack org chain in ``.kittify/config.yaml`` (order-preserving)."""
    kit = repo_root / ".kittify"
    kit.mkdir(parents=True, exist_ok=True)
    (kit / "config.yaml").write_text(
        yaml.safe_dump({"charter_packs": {"org": {"packs": [{"name": name, "local_path": str(root)} for name, root in entries]}}}),
        encoding="utf-8",
    )


def _write_healthy_fragment(root: Path, *, node_id: str, pack_name: str) -> Path:
    (root / "drg").mkdir(parents=True, exist_ok=True)
    (root / "drg" / "fragment.yaml").write_text(
        yaml.safe_dump(
            {
                "pack_name": pack_name,
                "source_kind": "local_path",
                "source_ref": str(root),
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": [{"id": node_id, "kind": "directives", "title": node_id}],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    return root


def _write_malformed_fragment(root: Path) -> Path:
    """A present-but-malformed fragment: a node whose ``kind`` is not canonical.

    ``load_org_pack`` raises :class:`OrgPackSchemaError` ("unknown kind") for it
    -- the exact schema-fault-of-an-optional-fragment class that degrades.
    """
    (root / "drg").mkdir(parents=True, exist_ok=True)
    (root / "drg" / "fragment.yaml").write_text(
        yaml.safe_dump(
            {
                "pack_name": _MALFORMED_PACK_NAME,
                "source_kind": "local_path",
                "source_ref": str(root),
                "layer_index": 1,
                "provenance_marker": "org",
                "nodes": [{"id": "SHOULD_NEVER_MINT", "kind": "notarealkind", "title": "x"}],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )
    return root


def _two_pack_chain(tmp_path: Path) -> Path:
    """Repo with a HEALTHY fragment pack #1 and a MALFORMED fragment pack #2."""
    repo = tmp_path / "repo"
    repo.mkdir()
    healthy = _write_healthy_fragment(tmp_path / "healthy-pack", node_id=_HEALTHY_MARKER, pack_name=_HEALTHY_PACK_NAME)
    malformed = _write_malformed_fragment(tmp_path / "malformed-pack")
    _register_packs(repo, [(_HEALTHY_PACK_NAME, healthy), (_MALFORMED_PACK_NAME, malformed)])
    return repo


def test_malformed_sibling_does_not_evict_healthy_fragment(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Per-pack degrade: a malformed pack #2 drops ONLY itself; pack #1 folds.

    Red-first against the pre-fix whole-chain drop: that code dropped BOTH
    fragments (the healthy sibling included), so ``_HEALTHY_MARKER_URN`` would
    be ABSENT from the merged graph. After the fix the healthy fragment is
    delivered and the malformed pack is dropped with an operator-visible WARNING
    naming it (not a silent DEBUG). ``org_roots=[]`` isolates the fragment layer.
    """
    repo = _two_pack_chain(tmp_path)

    with caplog.at_level(logging.WARNING, logger=_CHARTER_DRG_LOGGER):
        graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, org_roots=[])

    node_urns = {str(node.urn) for node in graph.nodes}
    # Healthy sibling survives (the core of the finding).
    assert _HEALTHY_MARKER_URN in node_urns
    # Malformed pack's would-be node never minted.
    assert "directive:SHOULD_NEVER_MINT" not in node_urns

    # Operator-visible WARNING names the dropped pack and says why.
    drop_warnings = [r for r in caplog.records if r.levelno == logging.WARNING and _MALFORMED_PACK_NAME in r.getMessage()]
    assert drop_warnings, [r.getMessage() for r in caplog.records]
    assert "malformed or unreadable drg/fragment.yaml" in drop_warnings[0].getMessage()
    # The healthy pack is NOT reported as dropped.
    assert not any(_HEALTHY_PACK_NAME in r.getMessage() for r in drop_warnings)


def test_all_healthy_multipack_chain_folds_both_without_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """No-regression: an all-healthy 2-pack chain folds BOTH with no drop WARNING."""
    repo = tmp_path / "repo"
    repo.mkdir()
    pack_a = _write_healthy_fragment(tmp_path / "pack-a", node_id="ALPHA_MARKER", pack_name="pack-a")
    pack_b = _write_healthy_fragment(tmp_path / "pack-b", node_id="BETA_MARKER", pack_name="pack-b")
    _register_packs(repo, [("pack-a", pack_a), ("pack-b", pack_b)])

    with caplog.at_level(logging.WARNING, logger=_CHARTER_DRG_LOGGER):
        graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, org_roots=[])

    node_urns = {str(node.urn) for node in graph.nodes}
    assert "directive:ALPHA_MARKER" in node_urns
    assert "directive:BETA_MARKER" in node_urns
    assert not [r for r in caplog.records if "malformed or unreadable drg/fragment.yaml" in r.getMessage()]


def test_single_healthy_pack_unchanged_no_warning(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """No-regression: a single healthy fragment pack folds with no drop WARNING."""
    repo = tmp_path / "repo"
    repo.mkdir()
    pack = _write_healthy_fragment(tmp_path / "solo-pack", node_id="SOLO_MARKER", pack_name="solo")
    _register_packs(repo, [("solo", pack)])

    with caplog.at_level(logging.WARNING, logger=_CHARTER_DRG_LOGGER):
        graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, org_roots=[])

    assert "directive:SOLO_MARKER" in {str(node.urn) for node in graph.nodes}
    assert not [r for r in caplog.records if "malformed or unreadable drg/fragment.yaml" in r.getMessage()]


def test_strict_load_still_raises_on_malformed_pack(tmp_path: Path) -> None:
    """Fail-loud invariant: ``strict=True`` still raises on ANY malformed pack.

    Also pins the fail-loud API default (``strict=False`` WITHOUT
    ``degrade_malformed``) still raises, so the diagnostic / cascade callers are
    unweakened -- only the executor's explicit ``degrade_malformed=True`` opt-in
    tolerates a malformed sibling.
    """
    repo = _two_pack_chain(tmp_path)

    with pytest.raises(OrgPackSchemaError, match=r"notarealkind"):
        load_org_drg(repo, strict=True)

    with pytest.raises(OrgPackSchemaError, match=r"notarealkind"):
        load_org_drg(repo, strict=False)

    # The explicit opt-in degrades per-pack: only the healthy fragment returns.
    fragments = load_org_drg(repo, strict=False, degrade_malformed=True)
    assert [f.pack_name for f in fragments] == [_HEALTHY_PACK_NAME]


# ---------------------------------------------------------------------------
# #4200 defect 2 (squad MAJOR on PR #4201): an unreadable ``drg/fragment.yaml``
# (permissions, or the path being a directory) presents as the I/O fault it is
# — ``OSError``, never a masked ``OrgPackParseError`` — so every runtime
# consumer that previously tolerated that fault class must keep tolerating it
# BY NAME. The per-pack degrade in ``load_org_drg`` and the
# ``_org_root_folds_fragment`` probe are the two such consumers on the
# mission-step composition path; each gets a chmod-0 regression test mirroring
# ``tests/charter_offering/drg/test_org_fragment_validation.py::
# test_permission_denied_fragment_is_a_finding``, plus a directory-fragment
# variant that exercises the same ``OSError`` channel on every platform
# (``read_text`` on a directory raises ``OSError`` even for root).
# ---------------------------------------------------------------------------

_UNREADABLE_PACK_NAME = "unreadable-org"


def _write_directory_fragment(root: Path) -> Path:
    """A pack whose ``drg/fragment.yaml`` path is a DIRECTORY (unreadable).

    ``read_text`` on a directory raises ``OSError`` on every platform, so this
    exercises the unreadable-file channel without chmod (which is a no-op for
    root) — same trick as the validator-side
    ``test_unreadable_fragment_is_a_finding_not_a_traceback``.
    """
    fragment = root / "drg" / "fragment.yaml"
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.mkdir()
    return root


def _write_chmod0_fragment(root: Path) -> Path:
    """A pack whose ``drg/fragment.yaml`` is chmod-0 (permission-denied)."""
    fragment = root / "drg" / "fragment.yaml"
    fragment.parent.mkdir(parents=True, exist_ok=True)
    fragment.write_text("nodes: []\nedges: []\n", encoding="utf-8")
    fragment.chmod(0)
    return root


def _healthy_plus_unreadable_chain(tmp_path: Path, write_unreadable) -> Path:
    """Repo with a HEALTHY fragment pack #1 and an UNREADABLE fragment pack #2."""
    repo = tmp_path / "repo"
    repo.mkdir()
    healthy = _write_healthy_fragment(tmp_path / "healthy-pack", node_id=_HEALTHY_MARKER, pack_name=_HEALTHY_PACK_NAME)
    unreadable = write_unreadable(tmp_path / "unreadable-pack")
    _register_packs(repo, [(_HEALTHY_PACK_NAME, healthy), (_UNREADABLE_PACK_NAME, unreadable)])
    return repo


def test_unreadable_sibling_does_not_evict_healthy_fragment(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Directory-fragment variant: an unreadable pack drops ONLY itself.

    The unreadable optional fragment is the exact "previously tolerated"
    condition of #4200 defect 2: before the loader stopped masking read faults
    as ``OrgPackParseError``, the per-pack degrade caught them; after the
    unmasking, ``OSError`` escaped every runtime consumer as a traceback. The
    degrade catch names ``OSError`` now, so a chmod-0 (or directory) fragment
    again drops ONLY its own pack with an operator-visible WARNING.
    """
    repo = _healthy_plus_unreadable_chain(tmp_path, _write_directory_fragment)

    with caplog.at_level(logging.WARNING, logger=_CHARTER_DRG_LOGGER):
        graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, org_roots=[])

    node_urns = {str(node.urn) for node in graph.nodes}
    # Healthy sibling survives (the core of the finding).
    assert _HEALTHY_MARKER_URN in node_urns

    drop_warnings = [r for r in caplog.records if r.levelno == logging.WARNING and _UNREADABLE_PACK_NAME in r.getMessage()]
    assert drop_warnings, [r.getMessage() for r in caplog.records]
    assert "malformed or unreadable drg/fragment.yaml" in drop_warnings[0].getMessage()
    # The healthy pack is NOT reported as dropped.
    assert not any(_HEALTHY_PACK_NAME in r.getMessage() for r in drop_warnings)


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="chmod-based unreadability needs POSIX and a non-root user",
)
def test_permission_denied_sibling_degrades_per_pack(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """chmod-0 variant mirroring ``test_permission_denied_fragment_is_a_finding``.

    A permission-denied optional fragment degrades per-pack on the mission-step
    composition path (the squad's live repro: at the pre-fix head this raised
    ``PermissionError`` out of every dispatch for such a repo).
    """
    repo = _healthy_plus_unreadable_chain(tmp_path, _write_chmod0_fragment)
    try:
        with caplog.at_level(logging.WARNING, logger=_CHARTER_DRG_LOGGER):
            graph = StepContractExecutor._load_graph_degrading_malformed_org_pack(repo, org_roots=[])
    finally:
        fragment = tmp_path / "unreadable-pack" / "drg" / "fragment.yaml"
        if fragment.exists():
            fragment.chmod(0o644)

    node_urns = {str(node.urn) for node in graph.nodes}
    assert _HEALTHY_MARKER_URN in node_urns

    drop_warnings = [r for r in caplog.records if r.levelno == logging.WARNING and _UNREADABLE_PACK_NAME in r.getMessage()]
    assert drop_warnings, [r.getMessage() for r in caplog.records]
    assert "malformed or unreadable drg/fragment.yaml" in drop_warnings[0].getMessage()


def test_strict_load_still_raises_on_unreadable_pack(tmp_path: Path) -> None:
    """Fail-loud invariant: an unreadable fragment raises ``OSError``, unmasked.

    The deliberate #4200 decision: the strict / non-degrading diagnostic paths
    surface the read fault as the I/O fault it is (their callers degrade on
    broad ``Exception`` or translate it to an ``unreadable_file`` finding) —
    it is never translated back into ``OrgPackParseError`` anywhere.
    """
    repo = _healthy_plus_unreadable_chain(tmp_path, _write_directory_fragment)

    with pytest.raises(OSError):
        load_org_drg(repo, strict=True)

    with pytest.raises(OSError):
        load_org_drg(repo, strict=False)

    # The explicit opt-in degrades per-pack: only the healthy fragment returns.
    fragments = load_org_drg(repo, strict=False, degrade_malformed=True)
    assert [f.pack_name for f in fragments] == [_HEALTHY_PACK_NAME]


def _fragment_shaped_root(tmp_path: Path) -> Path:
    root = tmp_path / "probe-pack"
    (root / "drg").mkdir(parents=True, exist_ok=True)
    (root / "drg" / "fragment.yaml").write_text("nodes: []\nedges: []\n", encoding="utf-8")
    return root


def test_org_root_folds_fragment_tolerates_read_fault(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Probe: a read fault answers ``False``, never raises (seam-pinned).

    The loader's read fault is pinned at the seam the probe calls (the same
    ``monkeypatch``-at-the-seam pattern as the validator-side
    ``test_missing_pack_fault_has_its_own_category``), so the ``OSError``
    branch of the probe's catch is exercised on every platform, root included.
    """
    from specify_cli.mission_step_contracts import executor as executor_module

    root = _fragment_shaped_root(tmp_path)

    def _permission_denied(pack_name: str, pack_root: Path, layer_index: int) -> None:
        raise PermissionError(13, "Permission denied", str(pack_root / "drg" / "fragment.yaml"))

    monkeypatch.setattr(executor_module, "load_org_pack", _permission_denied)
    assert StepContractExecutor._org_root_folds_fragment(root) is False


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="chmod-based unreadability needs POSIX and a non-root user",
)
def test_org_root_folds_fragment_false_on_permission_denied(tmp_path: Path) -> None:
    """Probe, chmod-0 variant mirroring ``test_permission_denied_fragment_is_a_finding``.

    The squad's live repro: at the pre-fix head this probe RAISED
    ``PermissionError`` instead of answering; at merge-base it answered
    ``False``. A permission-denied fragment means the pack's content does NOT
    reach the merged graph, so the honest answer is ``False`` (a genuinely
    lost root, WARNED as such), never a traceback.
    """
    root = _fragment_shaped_root(tmp_path)
    (root / "drg" / "fragment.yaml").chmod(0)
    try:
        folds = StepContractExecutor._org_root_folds_fragment(root)
    finally:
        (root / "drg" / "fragment.yaml").chmod(0o644)
    assert folds is False
