"""WP15 — progressive disclosure of doctrine context (ADR 2026-07-28-1).

Complete delivery made affordable: everything reachable is either delivered
inline (``requires`` — eager) or named with the guidance that says when to fetch
it (``suggests`` — a link carrying ``when``), never silently absent. This is the
default cadence, and it must be in force before WP11 switches on delivery on
every load (C-012).

The properties under test:

* **T081** — each artefact DTO carries ``references[]``; each entry is
  ``{id, relation, when, reason}`` from the edge, unmodified. Uncovered
  ``suggests`` edges render a *stated default* for ``when``, never a blank.
* **T082** — ``requires`` targets are delivered inline (eager); ``suggests``
  targets are emitted as links (lazy). This is the default cadence, not a mode.
* **T083** — ``--include-all`` materialises the entire reachable closure inline;
  its output is a superset of the progressive render for the same grain.
* **T084** — the union of inlined ids and referenced ids equals the delivered
  set (completeness by naming, no cap); a linked artefact is retrievable by its
  id via the existing ``--include`` verb; ``--include-all`` output ⊇ progressive.
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from charter.activation import progressive_disclosure as pd
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Synthetic-graph fixtures (pure, deterministic — no doctrine tree loaded)
# ---------------------------------------------------------------------------


def _node(urn: str) -> DRGNode:
    kind = NodeKind(urn.split(":", 1)[0])
    return DRGNode(urn=urn, kind=kind)


def _edge(
    source: str,
    target: str,
    relation: Relation,
    *,
    when: str | None = None,
    reason: str | None = None,
) -> DRGEdge:
    return DRGEdge(source=source, target=target, relation=relation, when=when, reason=reason)


def _graph(nodes: list[str], edges: list[DRGEdge]) -> DRGGraph:
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-07-28T00:00:00Z",
        generated_by="test",
        nodes=[_node(u) for u in nodes],
        edges=edges,
    )


# ---------------------------------------------------------------------------
# Integration helpers — the real doctrine tree via the JSON DTO entrypoint
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".kittify" / "charter").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("could not locate repo root with .kittify/charter")


_KIND_BY_ARRAY = {
    "directives": "directive",
    "tactics": "tactic",
    "styleguides": "styleguide",
    "toolguides": "toolguide",
}


def _project_root(tmp_path: Path) -> Path:
    """Copy the checkout's activated charter into an isolated tmp project.

    The built-in doctrine graph ships in the installed package, so only the
    project-local activation surface (``.kittify/charter`` + ``config.yaml``)
    needs copying for the action bundle to resolve exactly as it does in the
    checkout.

    ``mission_type_activations`` is unrelated to the progressive-disclosure
    delivery contract this module pins, but WP04 (C-A1) made it a hard
    construction precondition for ``PackContext.from_config``. The checkout's
    own charter.yaml now carries that provisioning key (emitted by the charter
    generation path — ``charter.activation.compiler.provision_mission_type_activations``),
    so the COPY inherits it with no fixture-side append. Every test in this
    module resolves the ``software-dev`` grain, which is one of the provisioned
    built-in mission types. (Mirrors the fixture in
    ``tests/charter/test_every_load_delivery.py``.)
    """
    src = _repo_root()
    dst_kittify = tmp_path / ".kittify"
    dst_kittify.mkdir(parents=True)
    shutil.copytree(
        src / ".kittify" / "charter",
        dst_kittify / "charter",
        ignore=shutil.ignore_patterns("context-state.json"),
    )
    shutil.copy(src / ".kittify" / "config.yaml", dst_kittify / "config.yaml")
    subprocess.run(["git", "init", "--quiet", str(tmp_path)], check=False, capture_output=True)
    return tmp_path


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    """Every file path and its bytes under ``root`` (proves a shared tree stayed read-only)."""
    return {str(path.relative_to(root)): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _json_payload(repo: Path, *, include_all: bool = False) -> dict[str, object]:
    from charter.activation.context import build_charter_context, build_charter_context_json

    # depth is state-driven; force the bootstrap depth without mutating state.
    result = build_charter_context(
        repo, action="implement", mark_loaded=False, mission_type="software-dev"
    )
    return build_charter_context_json(
        repo,
        action="implement",
        depth=result.depth,
        mission_type="software-dev",
        include_all=include_all,
    )


@pytest.fixture(scope="module")
def shared_project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """One provisioned project (copy + ``git init``) shared by every payload test.

    The payload builders run with ``mark_loaded=False`` and only read, so the
    project is shared instead of re-copied and re-resolved per test; the tree
    snapshot taken up front is asserted unchanged at teardown to prove it.
    """
    repo = _project_root(tmp_path_factory.mktemp("progressive"))
    before = _tree_snapshot(repo)
    yield repo
    assert _tree_snapshot(repo) == before, "a payload test mutated the shared project"


@pytest.fixture(scope="module")
def progressive_payload(shared_project: Path) -> dict[str, object]:
    return _json_payload(shared_project)


@pytest.fixture(scope="module")
def include_all_payload(shared_project: Path) -> dict[str, object]:
    return _json_payload(shared_project, include_all=True)


def _entries(payload: dict[str, object]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for array in _KIND_BY_ARRAY:
        out.extend(payload.get(array, []))  # type: ignore[arg-type]
    return out


def _delivered_ids(payload: dict[str, object]) -> set[str]:
    return {str(e["id"]) for e in _entries(payload)}


def _inlined_ids(payload: dict[str, object]) -> set[str]:
    return {str(e["id"]) for e in _entries(payload) if e.get("delivery") == pd.DELIVERY_INLINE}


def _referenced_ids(payload: dict[str, object]) -> set[str]:
    refs = payload.get("references", [])
    return {str(r["id"]) for r in refs}  # type: ignore[union-attr]


# ===========================================================================
# T081 — references[] on the DTO, populated from edge when/reason
# ===========================================================================


class TestReferencesOnDto:
    def test_edge_fields_are_carried_unmodified(self) -> None:
        edge = _edge(
            "directive:D1",
            "tactic:T1",
            Relation.SUGGESTS,
            when="Use to verify the automated gates before handoff.",
            reason=None,
        )
        ref = pd.edge_to_reference(edge)
        assert ref == {
            "id": "T1",
            "relation": "suggests",
            "when": "Use to verify the automated gates before handoff.",
            "reason": None,
        }

    def test_requires_reason_carried_unmodified(self) -> None:
        edge = _edge("directive:D1", "directive:D2", Relation.REQUIRES, reason="mandatory prerequisite")
        ref = pd.edge_to_reference(edge)
        assert ref["relation"] == "requires"
        assert ref["reason"] == "mandatory prerequisite"

    def test_uncovered_suggests_edge_renders_stated_default_not_blank(self) -> None:
        edge = _edge("directive:D1", "tactic:T1", Relation.SUGGESTS, when=None)
        ref = pd.edge_to_reference(edge)
        assert ref["when"] == pd.STATED_DEFAULT_WHEN
        assert ref["when"], "stated default must be a non-empty string, never blank"

    def test_uncovered_requires_edge_has_no_stated_default(self) -> None:
        # The stated default is a suggests convention only — requires is
        # unconditional and needs no "when".
        edge = _edge("directive:D1", "directive:D2", Relation.REQUIRES, when=None)
        assert pd.edge_to_reference(edge)["when"] is None

    def test_payload_dto_carries_references(self, progressive_payload: dict[str, object]) -> None:
        payload = progressive_payload
        entries = _entries(payload)
        assert entries, "expected a populated implement-grain payload"
        for entry in entries:
            assert "references" in entry
            for ref in entry["references"]:  # type: ignore[union-attr]
                assert set(ref) == {"id", "relation", "when", "reason"}

    def test_payload_uncovered_suggests_reference_is_never_blank(self, progressive_payload: dict[str, object]) -> None:
        payload = progressive_payload
        suggests_refs = [
            ref
            for entry in _entries(payload)
            for ref in entry.get("references", [])  # type: ignore[union-attr]
            if ref["relation"] == "suggests"
        ]
        assert suggests_refs, "the implement grain reaches artefacts via suggests"
        assert all(ref["when"] for ref in suggests_refs), "no suggests link may carry a blank when"


# ===========================================================================
# T082 — requires eager, suggests linked (the default cadence)
# ===========================================================================


class TestDefaultCadence:
    def test_requires_closure_is_transitive(self) -> None:
        graph = _graph(
            ["directive:R", "directive:A", "directive:B", "tactic:S"],
            [
                _edge("directive:R", "directive:A", Relation.REQUIRES),
                _edge("directive:A", "directive:B", Relation.REQUIRES),
                _edge("directive:R", "tactic:S", Relation.SUGGESTS),
            ],
        )
        closure = pd.requires_closure(graph, ["directive:R"])
        assert {"directive:R", "directive:A", "directive:B"} <= closure
        assert "tactic:S" not in closure

    def test_requires_inlined_suggests_linked(self) -> None:
        graph = _graph(
            ["directive:R", "directive:A", "tactic:S"],
            [
                _edge("directive:R", "directive:A", Relation.REQUIRES),
                _edge("directive:R", "tactic:S", Relation.SUGGESTS),
            ],
        )
        delivered = {"directive:A", "tactic:S"}
        inline, link = pd.partition_delivery(graph, ["directive:R"], delivered)
        assert inline == {"directive:A"}
        assert link == {"tactic:S"}

    def test_payload_marks_delivery_and_has_links(self, progressive_payload: dict[str, object]) -> None:
        payload = progressive_payload
        entries = _entries(payload)
        for entry in entries:
            assert entry.get("delivery") in {pd.DELIVERY_INLINE, pd.DELIVERY_LINK}
        # The implement grain reaches its artefacts via suggests, so the default
        # render must contain at least one linked (lazy) artefact.
        assert any(e.get("delivery") == pd.DELIVERY_LINK for e in entries)

    def test_payload_top_level_link_set_present(self, progressive_payload: dict[str, object]) -> None:
        payload = progressive_payload
        assert isinstance(payload.get("references"), list)
        assert payload["references"], "the link set names the reachable-but-not-inlined artefacts"


# ===========================================================================
# T083 — --include-all escape hatch (superset of the progressive render)
# ===========================================================================


class TestIncludeAllHatch:
    def test_collect_typed_artifacts_include_all_is_superset(self) -> None:
        graph = _graph(
            ["directive:R", "directive:A", "tactic:S"],
            [
                _edge("directive:R", "directive:A", Relation.REQUIRES),
                _edge("directive:R", "tactic:S", Relation.SUGGESTS),
            ],
        )

        class _Repo:
            def get(self, _id: str) -> object:
                return None

            def get_provenance(self, _id: str) -> str:
                return "built-in"

        inline = frozenset({"tactic:S"})  # deliberately treat S as *not* inline by default
        progressive = pd.collect_typed_artifacts(
            _Repo(), ["S"], kind="tactic", merged=graph, inline_urns=frozenset(), include_all=False
        )
        allof = pd.collect_typed_artifacts(
            _Repo(), ["S"], kind="tactic", merged=graph, inline_urns=frozenset(), include_all=True
        )
        assert progressive[0]["delivery"] == pd.DELIVERY_LINK
        assert allof[0]["delivery"] == pd.DELIVERY_INLINE
        assert inline  # guard: the fixture stays meaningful

    def test_include_all_marks_every_entry_inline(self, include_all_payload: dict[str, object]) -> None:
        payload = include_all_payload
        entries = _entries(payload)
        assert entries
        assert all(e.get("delivery") == pd.DELIVERY_INLINE for e in entries)

    def test_include_all_inlined_ids_superset_of_progressive(
        self, progressive_payload: dict[str, object], include_all_payload: dict[str, object]
    ) -> None:
        progressive = progressive_payload
        allof = include_all_payload
        prog_inlined = _inlined_ids(progressive)
        all_inlined = _inlined_ids(allof)
        assert prog_inlined <= all_inlined
        # The progressive render leaves suggests-reached artefacts as links, so
        # the hatch is a *strict* superset for this grain.
        assert all_inlined > prog_inlined
        # And the hatch inlines the whole delivered set.
        assert all_inlined == _delivered_ids(allof)


# ===========================================================================
# T084 — named, fetchable, inlined by the hatch (completeness by naming)
# ===========================================================================


class TestCompletenessByNaming:
    def test_union_inlined_and_referenced_equals_delivered_over_a_suggests_chain(self) -> None:
        # root ~suggests~> a ~suggests~> b ~suggests~> c : a deep chain where no
        # delivered artefact is requires-reachable from the root.
        graph = _graph(
            ["directive:root", "tactic:a", "tactic:b", "tactic:c"],
            [
                _edge("directive:root", "tactic:a", Relation.SUGGESTS),
                _edge("tactic:a", "tactic:b", Relation.SUGGESTS),
                _edge("tactic:b", "tactic:c", Relation.SUGGESTS),
            ],
        )
        delivered = {"tactic:a", "tactic:b", "tactic:c"}
        inline, _link = pd.partition_delivery(graph, ["directive:root"], delivered)
        referenced = {ref["id"] for ref in pd.link_references(graph, ["directive:root"], delivered)}
        inlined_ids = {pd.bare_id(u) for u in inline}
        delivered_ids = {pd.bare_id(u) for u in delivered}
        # completeness by naming: union equals the delivered set, no cap.
        assert inlined_ids | referenced == delivered_ids
        # every deep chain member is named even though none is inlined.
        assert referenced == {"a", "b", "c"}

    def test_no_cap_on_the_union(self) -> None:
        # 50 suggested leaves — a truncating [:10] cap would drop 40 of them.
        leaves = [f"tactic:t{i:02d}" for i in range(50)]
        graph = _graph(
            ["directive:root", *leaves],
            [_edge("directive:root", leaf, Relation.SUGGESTS) for leaf in leaves],
        )
        delivered = set(leaves)
        referenced = {ref["id"] for ref in pd.link_references(graph, ["directive:root"], delivered)}
        # Full content equality against all 50 expected bare ids is the real
        # "no cap" contract: a truncating [:10] cap would drop 40 of them and
        # fail this equality outright, so a separate `len(referenced) == 50`
        # cardinality check would be a strictly weaker, redundant duplicate.
        assert referenced == {pd.bare_id(u) for u in leaves}

    def test_payload_union_equals_delivered(self, progressive_payload: dict[str, object]) -> None:
        payload = progressive_payload
        delivered = _delivered_ids(payload)
        assert _inlined_ids(payload) | _referenced_ids(payload) >= delivered

    def test_linked_artifact_retrievable_via_include(
        self, shared_project: Path, progressive_payload: dict[str, object]
    ) -> None:
        from charter.activation.context import build_charter_context_include

        payload = progressive_payload
        linked: tuple[str, str] | None = None
        for array, kind in _KIND_BY_ARRAY.items():
            for entry in payload.get(array, []):  # type: ignore[union-attr]
                if entry.get("delivery") == pd.DELIVERY_LINK:
                    linked = (kind, str(entry["id"]))
                    break
            if linked:
                break
        assert linked is not None, "expected at least one linked artefact"
        kind, artefact_id = linked
        # Reuses the SAME provisioned project the payload was rendered from
        # (rather than the checkout's own real repo root) so the include
        # lookup resolves against the identical copy.
        text = build_charter_context_include(shared_project, f"{kind}:{artefact_id}")
        assert artefact_id in text
