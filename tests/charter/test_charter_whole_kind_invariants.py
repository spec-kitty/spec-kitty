"""Red-first regression tests for invariants I1-I5 (mission
``charter-generation-drops-scoped-references-01M3M1KF``, WP01 T002-T006).

Binding invariants (copied verbatim from plan.md's "Round-5 restatement" and
round-6 amendments -- see plan.md lines ~93-140 and ~310-357 for the full
text; cite line references here only where helpful):

- **I1 -- completeness.** Every activated reference id, from any source
  bucket (``graph.<kind>`` or ``graph.unresolved``), ends up either in
  ``catalog.references`` (resolved or placeholder) or in a structured
  diagnostic -- never silently absent. **Carve-out:** this per-id guarantee
  does NOT extend to ids reachable ONLY via DRG-transitive closure when the
  whole graph fails to load -- those are covered collectively, never
  individually, by the single loud ``_graph``/``_load_failure`` sentinel
  diagnostic.
- **I2 -- single evaluation point, both source buckets counted.** The
  whole-kind fail-closed check is evaluated once per kind, after ALL sources
  (every per-kind ``_render_kind_references`` call AND the kind-mapped
  ``graph.unresolved`` pass) have contributed. A kind counts as
  **activated** if EITHER ``graph.<kind>`` is non-empty OR at least one
  ``graph.unresolved`` URN was attributed to it via the kind-mapping step.
- **I3 -- every diagnostic is shaped.** Every structured diagnostic record
  carries a defined ``kind``, ``id``, ``cause``. Four unattributable
  ``graph.unresolved``-URN classes each get a defined shape per
  ``contracts/charter-generate-json-diagnostics.md``'s "Round-5 addition"
  section.
- **I4 -- graph-load failure is loud, not fail-closed.** A total DRG
  graph-load failure yields a loud structured diagnostic (``kind: "_graph"``,
  ``id: "_load_failure"``, ``cause: "graph_load_failed"``) and does NOT make
  ``generate`` exit non-zero.
- **I5 -- determinism.** Generation is deterministic across repeat
  invocations on both the fail-closed and diagnostic paths.

Approach: these fixtures call the private functions
``_build_references_from_service``/``_raw_kind_repository``
(``src/charter/activation/compiler.py``) directly -- the exact functions
WP02 modifies -- with hand-constructed stub repositories/doctrine-services
and (for T002/T003) a monkeypatched ``_resolve_transitive_reference_graph``
that returns a precisely-controlled ``ResolveTransitiveRefsResult``. This
mirrors T006's own white-box precedent (calling a module-private helper
directly is a legitimate unit-test pattern per the WP prompt) and plan.md
IC-04's "implementer's choice ... narrower compiler.py-level unit test"
allowance: it gives deterministic, precise control over each invariant's
edge case without fighting real DRG-graph/pack-root construction to
reproduce fragile corner cases the mechanism doesn't yet implement at all.
T004 and the I1/I2 carve-out fixture instead drive the REAL
``_resolve_transitive_reference_graph`` (via a corrupted project-level DRG
overlay), since I4's defect lives inside that function's own except branch,
not in anything monkeypatching would let us observe.

None of the assertions below reference a not-yet-existing structured-records
sink parameter or exception type by name (that would crash with
``TypeError``/``AttributeError`` for the wrong reason); every assertion is
against ``diagnostics: list[str]`` content, ``references`` content, or
(where plan.md explicitly commits to it -- the RuntimeError propagating to
``generate.py``'s existing handler, see plan.md's WP-CORE step (e)) a
``RuntimeError``. Per T003's guidance, a ``# TODO(WP02)`` comment marks each
place a structured-record assertion will be ADDED once WP02 exposes that
sink -- the diagnostics-list assertion here is deliberately not removed at
that point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import types
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation import compiler as compiler_module
from charter.activation.compiler import (
    ConfigActivatedRoots,
    WholeKindUnresolvedError,
    _raw_kind_repository,
)
from charter.offering.drg.query import ResolveTransitiveRefsResult

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Shared test doubles / helpers
# ---------------------------------------------------------------------------


@dataclass
class _StubRepository:
    """Minimal raw-repository double.

    ``.get(id)`` resolves only ids in *known*; everything else misses.
    *scope_filtered_ids* mirrors ``BaseArtifactRepository.scope_filtered_ids``
    -- when a missing id is a member, the future classify-and-placeholder
    helper (``_diagnose_catalog_miss``) will route it to ``SCOPE_FILTERED``
    instead of ``MISSING_ARTIFACT``/``TYPO_SUSPECTED``.
    """

    known: dict[str, Any] = field(default_factory=dict)
    scope_filtered_ids: frozenset[str] = frozenset()

    def get(self, artifact_id: str) -> Any | None:
        return self.known.get(artifact_id)

    def list_all(self) -> list[str]:
        return list(self.known)


class _StubActiveCharterService:
    """Activation-aware-wrapper double: exposes ``raw_repository(kind)``.

    ``_raw_kind_repository`` (compiler.py) prefers this method when present,
    matching the real ``charter.activation.resolver.ActiveCharterService`` shape
    every production caller passes.
    """

    def __init__(self, **repositories: _StubRepository) -> None:
        self._repositories = repositories

    def raw_repository(self, kind: str) -> _StubRepository:
        return self._repositories.get(kind, _StubRepository())


def _empty_config_roots() -> ConfigActivatedRoots:
    return ConfigActivatedRoots(
        directives=[],
        paradigms=[],
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        agent_profiles=[],
    )


def _call_build_references(
    monkeypatch: pytest.MonkeyPatch,
    graph: ResolveTransitiveRefsResult,
    *,
    repositories: dict[str, _StubRepository] | None = None,
    config_roots: ConfigActivatedRoots | None = None,
) -> tuple[list[Any], list[str], list[dict[str, str]]]:
    """Call ``_build_references_from_service`` with *graph* injected in place
    of a real ``_resolve_transitive_reference_graph`` call.

    ``monkeypatch.setattr`` on the module attribute is effective even for the
    call from inside ``_build_references_from_service`` itself, since that
    call resolves the name via the module's global namespace at call time.

    Returns ``(references, diagnostics, unresolved_records)`` -- the third
    element is the structured ``{kind, id, cause, detail}`` sink WP02 exposes
    (compiler.py's ``unresolved_records`` parameter), threaded through so
    callers can assert on the STRUCTURED record shape directly rather than
    only the plain-text ``diagnostics`` strings (PR-TESTS-005 / WP03-C1-003).
    """
    monkeypatch.setattr(compiler_module, "_resolve_transitive_reference_graph", lambda **_kwargs: graph)
    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []
    doctrine_service = _StubActiveCharterService(**(repositories or {}))
    references = compiler_module._build_references_from_service(
        mission="software-dev",
        template_set="default",
        config_roots=config_roots or _empty_config_roots(),
        doctrine_root=Path("/nonexistent-doctrine-root-not-used-once-patched"),
        doctrine_service=doctrine_service,
        repo_root=None,
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )
    return references, diagnostics, unresolved_records


def _write_dangling_edge_project_overlay(repo_root: Path) -> None:
    """Write a project-level DRG overlay (``<repo>/.kittify/charter-packs/graph.yaml``)
    with a dangling edge target, so ``assert_valid`` rejects the merged graph
    and ``_resolve_transitive_reference_graph``'s own ``except Exception:``
    branch (compiler.py, current ~line 1306) fires for real -- this is the
    "deliberately corrupted DRG fragment file in the fixture repo" T004
    calls for, exercised through the REAL function (not monkeypatched),
    since I4's defect is inside that function's own except branch.
    """
    overlay_dir = repo_root / ".kittify" / "charter-packs"
    overlay_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    payload = {
        "nodes": [
            {"urn": "styleguide:ghost-node-01M3M1KF", "kind": "styleguide", "label": "Ghost"},
        ],
        "edges": [
            {
                "source": "styleguide:ghost-node-01M3M1KF",
                "target": "styleguide:totally-nonexistent-target-01M3M1KF",
                "relation": "requires",
            },
        ],
    }
    with (overlay_dir / "graph.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


# ---------------------------------------------------------------------------
# T002 -- I1/I2 whole-kind fail-closed fixtures
# ---------------------------------------------------------------------------


def test_whole_kind_missing_artifact_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture A (T002 step 2): a kind whose only activated id(s) resolve
    into ``graph.<kind>`` (a real DRG node reached, e.g. a misconfigured
    pack root -- the DRG graph still declares the node but the raw
    repository has no artifact for it) but the raw-repository lookup misses
    for ALL of them must fail closed with a non-zero-exit-equivalent
    (``RuntimeError``, per plan.md's WP-CORE step (e): "so generate.py's
    existing RuntimeError handler ... exits non-zero") naming the kind --
    never a silently-empty-but-structurally-successful ``styleguide``
    section.

    RED pre-fix: today ``_build_references_from_service`` returns normally
    (no whole-kind check exists at all) -- ``pytest.raises`` fails with
    "DID NOT RAISE", an assertion failure about the missing behaviour, not a
    crash.
    """
    graph = ResolveTransitiveRefsResult(styleguides=["misconfigured-pack-root-id"])

    with pytest.raises(RuntimeError, match="styleguide"):
        _call_build_references(
            monkeypatch,
            graph,
            repositories={"styleguides": _StubRepository(known={})},
        )


def test_whole_kind_graph_unresolved_routing_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture B (T002 step 3): an id reachable ONLY via ``graph.unresolved``
    (no DRG node -- e.g. an activated id with no corresponding graph entry)
    that is the SOLE activated id of its kind must be routed through the
    same classify-and-placeholder helper, get a reason-bearing diagnostic,
    and -- because it never resolves and never places a placeholder -- trip
    the same whole-kind fail-closed check as Fixture A (I2: both source
    buckets counted at ONE evaluation point).

    RED pre-fix: today's ``graph.unresolved`` loop only appends an opaque
    diagnostics-list string; no whole-kind check exists, so ``generate``
    (and this direct call) never fails closed for this bucket either.
    """
    urn = "agent_profile:orphan-no-drg-node-01M3M1KF"
    graph = ResolveTransitiveRefsResult(unresolved=[(urn, urn)])

    with pytest.raises(RuntimeError, match="agent_profile"):
        _call_build_references(monkeypatch, graph)


def test_whole_kind_fail_closed_raises_typed_error_carrying_the_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fail-closed exit is a typed, still-``RuntimeError`` exception that
    carries the kind and the run's structured records, so each CLI can translate
    it (notice / clean error / ``--json`` payload) without parsing a message."""
    graph = ResolveTransitiveRefsResult(styleguides=["misconfigured-pack-root-id"])

    with pytest.raises(WholeKindUnresolvedError) as raised:
        _call_build_references(monkeypatch, graph, repositories={"styleguides": _StubRepository(known={})})

    assert isinstance(raised.value, RuntimeError)
    assert raised.value.kind == "styleguide"
    assert [(r["kind"], r["id"]) for r in raised.value.unresolved_records] == [("styleguide", "misconfigured-pack-root-id")]
    assert "misconfigured-pack-root-id" in str(raised.value)


def test_whole_kind_missing_artifact_fails_closed_is_deterministic_across_repeat_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I5 (determinism), Fixture A: plan.md's ATDD invariant table commits
    to an idempotency assertion on the whole-kind-unresolved fixture -- run
    twice, assert both invocations fail closed identically (same
    ``RuntimeError``, same kind named). Fixture A's whole-kind check is a
    pure function of its inputs with no state mutated before the raise, so
    two invocations on the identical fixture must raise with the identical
    message.

    RED pre-fix (PR-TESTS-002): this file called
    ``_call_build_references`` for this fixture exactly once; plan.md's I5
    row committed to appending this idempotency assertion and that
    commitment was unfulfilled.
    """
    graph = ResolveTransitiveRefsResult(styleguides=["misconfigured-pack-root-id"])
    repositories = {"styleguides": _StubRepository(known={})}

    with pytest.raises(RuntimeError, match="styleguide") as first_invocation:
        _call_build_references(monkeypatch, graph, repositories=repositories)
    with pytest.raises(RuntimeError, match="styleguide") as second_invocation:
        _call_build_references(monkeypatch, graph, repositories=repositories)

    assert str(first_invocation.value) == str(second_invocation.value)


def test_whole_kind_graph_unresolved_routing_fails_closed_is_deterministic_across_repeat_invocations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I5 (determinism), Fixture B: the same idempotency commitment as
    above, for the ``graph.unresolved``-routing whole-kind fail-closed
    path -- run twice on the identical fixture, assert both invocations
    raise ``RuntimeError`` with the identical message naming the same kind.

    RED pre-fix (PR-TESTS-002): unfulfilled for the same reason as Fixture
    A's sibling test above.
    """
    urn = "agent_profile:orphan-no-drg-node-01M3M1KF"
    graph = ResolveTransitiveRefsResult(unresolved=[(urn, urn)])

    with pytest.raises(RuntimeError, match="agent_profile") as first_invocation:
        _call_build_references(monkeypatch, graph)
    with pytest.raises(RuntimeError, match="agent_profile") as second_invocation:
        _call_build_references(monkeypatch, graph)

    assert str(first_invocation.value) == str(second_invocation.value)


def test_scope_filtered_id_among_missing_ids_does_not_trip_whole_kind_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control (T002 step 5): a kind with at least one
    ``SCOPE_FILTERED`` id among otherwise-``MISSING_ARTIFACT`` ids of the
    same kind must NOT trip the fail-closed path -- that kind's reference
    list is non-empty once the ``SCOPE_FILTERED`` id placeholders.

    NOT part of the red set: nothing raises today for ANY input (no
    whole-kind check exists pre-fix at all), so this assertion already
    holds trivially before the fix. It is included as a stability control
    WP02 must not regress into a false-positive fail-closed trip once
    ``SCOPE_FILTERED`` placeholdering exists -- the reviewer should confirm
    it STAYS green post-fix, not that it turns red first.
    """
    graph = ResolveTransitiveRefsResult(styleguides=["scope-filtered-id", "genuinely-missing-id"])
    repositories = {
        "styleguides": _StubRepository(
            known={},
            scope_filtered_ids=frozenset({"scope-filtered-id"}),
        )
    }

    # Must not raise.
    _call_build_references(monkeypatch, graph, repositories=repositories)


# ---------------------------------------------------------------------------
# T003 -- I3: four unattributable `graph.unresolved` URN classes
# ---------------------------------------------------------------------------

_UNATTRIBUTABLE_URN_CASES: tuple[tuple[str, str, str, str, str, str], ...] = (
    # (case label, urn, expected cause, expected kind label, expected bare id, expected detail)
    (
        "malformed-no-colon",
        "malformed-urn-no-colon-at-all",
        "malformed_urn",
        "_unattributed",
        "malformed-urn-no-colon-at-all",
        "malformed URN, no kind prefix",
    ),
    (
        "malformed-empty-id",
        "tactic:",
        "malformed_urn",
        "_unattributed",
        "tactic:",
        "malformed URN, no artifact id",
    ),
    (
        "unrecognized-kind-prefix",
        "action:some-action-id",
        "unattributed_kind",
        "action",
        "some-action-id",
        "unrecognized artifact kind: action",
    ),
    # NOTE: the stub ``_StubActiveCharterService.raw_repository`` (above) never
    # returns ``None`` -- it defaults to an empty ``_StubRepository()`` for
    # any kind not explicitly configured -- so this fixture exercises the
    # "valid, real-repository kind outside the six tracked kinds" contract
    # shape (item 4), not the "genuinely-None-repository" shape (item 3),
    # even though ``template`` is one of the three kinds whose REAL
    # production repository is ``None``. Asserted against the detail this
    # fixture actually produces, not the theoretical production one.
    (
        "valid-kind-none-repository",
        "template:some-template-id",
        "unattributed_kind",
        "template",
        "some-template-id",
        "kind 'template' is not one of the six DRG-backed kinds tracked for reference resolution",
    ),
    (
        "valid-kind-untracked",
        "paradigm:some-paradigm-id",
        "unattributed_kind",
        "paradigm",
        "some-paradigm-id",
        "kind 'paradigm' is not one of the six DRG-backed kinds tracked for reference resolution",
    ),
)


@pytest.mark.parametrize(
    ("case_label", "urn", "expected_cause", "expected_kind_label", "expected_id", "expected_detail"),
    _UNATTRIBUTABLE_URN_CASES,
    ids=[case[0] for case in _UNATTRIBUTABLE_URN_CASES],
)
def test_unattributable_graph_unresolved_urn_gets_a_shaped_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    case_label: str,
    urn: str,
    expected_cause: str,
    expected_kind_label: str,
    expected_id: str,
    expected_detail: str,
) -> None:
    """I3: each of the four unattributable ``graph.unresolved`` URN classes
    (contracts/charter-generate-json-diagnostics.md's "Round-5 addition")
    gets a defined ``kind``/``id``/``cause``/``detail`` shape rather than the
    prior opaque ``"Unresolved reference: <urn>/<urn>"`` duplicate-URN
    string.

    Asserts BOTH the plain-text ``diagnostics`` entry (kept -- still
    genuinely useful, human-facing coverage) AND the STRUCTURED
    ``unresolved_records`` dict directly (PR-TESTS-005 / WP03-C1-003:
    fulfills the former ``TODO(WP02)`` marker now that compiler.py exposes
    the structured-records sink).
    """
    graph = ResolveTransitiveRefsResult(unresolved=[(urn, urn)])

    _, diagnostics, unresolved_records = _call_build_references(monkeypatch, graph)

    assert any(expected_cause in line and expected_kind_label in line for line in diagnostics), (
        f"[{case_label}] expected a diagnostic naming cause={expected_cause!r} and kind={expected_kind_label!r} for urn={urn!r}, got: {diagnostics!r}"
    )

    matching_records = [record for record in unresolved_records if record.get("kind") == expected_kind_label and record.get("id") == expected_id]
    assert matching_records, (
        f"[{case_label}] expected a structured unresolved_records entry for kind={expected_kind_label!r}/id={expected_id!r}, got: {unresolved_records!r}"
    )
    assert matching_records[0] == {
        "kind": expected_kind_label,
        "id": expected_id,
        "cause": expected_cause,
        "detail": expected_detail,
    }, f"[{case_label}] structured record shape mismatch: {matching_records[0]!r}"


def test_graph_unresolved_urn_the_raw_repository_can_resolve_renders_a_real_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DRG can list a URN as unresolved while the raw repository does have
    the artifact (DRG/repository disagreement, e.g. an org pack): it must render
    a real reference, as the per-kind path does, not be reported as a miss -- and
    it counts as the kind's reference, so the whole-kind check does not trip."""
    urn = "styleguide:repo-only-id"
    model = types.SimpleNamespace(id="repo-only-id", title="Repo Only", principles=["Resolve me"])
    graph = ResolveTransitiveRefsResult(unresolved=[(urn, urn)])

    references, diagnostics, unresolved_records = _call_build_references(
        monkeypatch, graph, repositories={"styleguides": _StubRepository(known={"repo-only-id": model})}
    )

    matching = [ref for ref in references if ref.id == "STYLEGUIDE:repo-only-id"]
    assert len(matching) == 1, references
    assert matching[0].title == "Repo Only"
    assert matching[0].summary == "Resolve me"
    assert unresolved_records == []
    assert diagnostics == []


# ---------------------------------------------------------------------------
# T004 -- I4: total graph-load failure is loud, not fail-closed
# ---------------------------------------------------------------------------


def test_total_graph_load_failure_yields_loud_diagnostic_not_fail_closed(tmp_path: Path) -> None:
    """A corrupted/unparseable project DRG fragment forces
    ``_resolve_transitive_reference_graph``'s ``except Exception:`` branch
    (compiler.py, current ~line 1306) for real. Assert: the direct-root
    styleguide id still resolves (transitive closure is NOT reconstructed,
    but direct-root ids resolve normally -- unchanged, positive control);
    a loud, graph-load-failure diagnostic is present in ``diagnostics``
    (RED pre-fix: the except branch currently returns the fallback result
    silently, with no diagnostics parameter even threaded into it); and the
    function does not raise (I4: loud, never fail-closed).
    """
    import charter.activation.compiler as real_compiler_module

    _write_dangling_edge_project_overlay(tmp_path)

    doctrine_service = real_compiler_module._default_active_charter_service(tmp_path)
    config_roots = ConfigActivatedRoots(
        directives=[],
        paradigms=[],
        tactics=[],
        styleguides=["python-conventions"],
        toolguides=[],
        procedures=[],
        agent_profiles=[],
    )
    diagnostics: list[str] = []
    unresolved_records: list[dict[str, str]] = []

    references = real_compiler_module._build_references_from_service(
        mission="software-dev",
        template_set="default",
        config_roots=config_roots,
        doctrine_root=real_compiler_module.resolve_offering_root(),
        doctrine_service=doctrine_service,
        repo_root=tmp_path,
        diagnostics=diagnostics,
        unresolved_records=unresolved_records,
    )

    # Positive control (already true pre-fix, not part of the red set):
    # the direct root still resolves even though the graph failed to load.
    reference_ids = {reference.id for reference in references}
    assert "STYLEGUIDE:python-conventions" in reference_ids, "direct-root id must still resolve when the transitive graph fails to load"

    assert any("Graph load failed" in line for line in diagnostics), f"expected a loud graph-load-failure diagnostic, got: {diagnostics!r}"

    # PR-TESTS-005 / WP03-C1-003: the structured `_graph`/`_load_failure`
    # sentinel record (contracts/charter-generate-json-diagnostics.md's
    # "Round-3 addition") directly, not only its plain-text diagnostics line.
    graph_load_failure_records = [record for record in unresolved_records if record.get("kind") == "_graph"]
    assert len(graph_load_failure_records) == 1, f"expected exactly one _graph/_load_failure sentinel record, got: {unresolved_records!r}"
    sentinel = graph_load_failure_records[0]
    assert sentinel["id"] == "_load_failure"
    assert sentinel["cause"] == "graph_load_failed"
    assert sentinel["detail"], "sentinel record must carry a non-empty exception summary as detail"


def test_i1_i2_carve_out_transitive_only_id_under_graph_load_failure(tmp_path: Path) -> None:
    """I1/I2 carve-out fixture: an id activated ONLY via DRG-transitive
    closure (no direct ``config.activated_*`` root of its own kind),
    combined with the same corrupted-DRG-fragment total-load-failure.

    Assert: no per-id record/placeholder exists for the transitively-only
    id (it cannot -- the transitive closure was never reconstructed); the
    loud sentinel diagnostic is present (same RED reason as T004 above);
    the call does not raise (not fail-closed); and repeating the call twice
    produces byte-identical ``diagnostics`` (I5 determinism on this path).
    """
    import charter.activation.compiler as real_compiler_module

    _write_dangling_edge_project_overlay(tmp_path)

    doctrine_service = real_compiler_module._default_active_charter_service(tmp_path)
    # A directive is activated directly; in a healthy graph its transitive
    # closure would reach further styleguide/tactic ids with no direct
    # config root of their own -- but the graph never loads here, so ONLY
    # this directive's own bare id can possibly appear (fallback covers
    # direct roots only, never reconstructs the transitive walk).
    config_roots = ConfigActivatedRoots(
        directives=["001-architectural-integrity-standard"],
        paradigms=[],
        tactics=[],
        styleguides=[],
        toolguides=[],
        procedures=[],
        agent_profiles=[],
    )

    def _run() -> tuple[list[Any], list[str], list[dict[str, str]]]:
        diagnostics: list[str] = []
        unresolved_records: list[dict[str, str]] = []
        references = real_compiler_module._build_references_from_service(
            mission="software-dev",
            template_set="default",
            config_roots=config_roots,
            doctrine_root=real_compiler_module.resolve_offering_root(),
            doctrine_service=doctrine_service,
            repo_root=tmp_path,
            diagnostics=diagnostics,
            unresolved_records=unresolved_records,
        )
        return references, diagnostics, unresolved_records

    references_1, diagnostics_1, unresolved_records_1 = _run()
    references_2, diagnostics_2, unresolved_records_2 = _run()

    # No per-id record for anything transitively-only-reachable: only the
    # directive's own bare id (a direct root, not a DRG-backed kind this
    # function tracks) can appear, and it never places a STYLEGUIDE/TACTIC/
    # etc. reference on its own account.
    transitively_reachable_kinds = {reference.kind for reference in references_1}
    assert not ({"styleguide", "tactic", "toolguide", "procedure", "agent_profile"} & transitively_reachable_kinds), (
        f"a transitively-only-reachable id must not gain a per-id reference under total graph-load failure, got kinds: {transitively_reachable_kinds!r}"
    )

    assert any("Graph load failed" in line for line in diagnostics_1), f"expected a loud graph-load-failure diagnostic, got: {diagnostics_1!r}"

    # PR-TESTS-005 / WP03-C1-003: the structured `_graph`/`_load_failure`
    # sentinel record directly -- and no per-id record exists for the
    # transitively-only-reachable id (it cannot -- the closure was never
    # reconstructed), matching the carve-out (I1/I2).
    graph_load_failure_records = [record for record in unresolved_records_1 if record.get("kind") == "_graph"]
    assert len(graph_load_failure_records) == 1, f"expected exactly one _graph/_load_failure sentinel record, got: {unresolved_records_1!r}"
    sentinel = graph_load_failure_records[0]
    assert sentinel["id"] == "_load_failure"
    assert sentinel["cause"] == "graph_load_failed"
    assert sentinel["detail"]
    assert not ({"styleguide", "tactic", "toolguide", "procedure", "agent_profile"} & {record.get("kind") for record in unresolved_records_1}), (
        f"a transitively-only-reachable id must not gain a per-id unresolved record either, got: {unresolved_records_1!r}"
    )

    # I5 determinism: identical sentinel diagnostic/record and content across repeats.
    assert diagnostics_1 == diagnostics_2
    assert unresolved_records_1 == unresolved_records_2


# ---------------------------------------------------------------------------
# T006 -- `_raw_kind_repository` raw-service degrade fixture
# ---------------------------------------------------------------------------


class _RawUnwrappedOfferingServiceDouble:
    """A raw/unwrapped ``charter.offering.service.CharterOfferingService`` double: no
    ``raw_repository`` method (per ``_raw_kind_repository``'s own docstring
    branch), and no attribute matching an untracked kind such as
    ``"templates"``/``"anti_patterns"``.
    """


def test_raw_kind_repository_degrades_instead_of_raising_for_untracked_kind() -> None:
    """Round-6-folded residual: ``_raw_kind_repository``'s raw-service
    fallback branch (``compiler.py`` ~line 1093, ``return getattr(
    doctrine_service, kind)``, no default) raises ``AttributeError`` instead
    of degrading to ``None`` for a kind with no matching attribute on the
    raw/unwrapped shape.

    Post-WP02, this must return ``None`` -- a reported miss, not a crash.
    The call is wrapped so a pre-fix ``AttributeError`` becomes a clean,
    named sentinel rather than an uncaught exception escaping the test (per
    the WP brief: fail on an assertion about the missing behaviour, not on
    an ImportError/AttributeError/fixture error).

    RED pre-fix: ``AttributeError`` is raised today, so *outcome* below is
    the ``"RAISED"`` sentinel, not ``None`` -- the assertion fails on that
    observed, named difference.
    """
    doctrine_service = _RawUnwrappedOfferingServiceDouble()
    assert not hasattr(doctrine_service, "raw_repository")
    assert not hasattr(doctrine_service, "templates")

    try:
        outcome: Any = _raw_kind_repository(doctrine_service, "templates")
    except AttributeError:
        outcome = "RAISED"

    assert outcome is None, (
        f"_raw_kind_repository must degrade to None for an untracked kind on "
        f"a raw/unwrapped doctrine_service, got: {outcome!r} (pre-fix, "
        f"AttributeError propagates instead of degrading)"
    )
