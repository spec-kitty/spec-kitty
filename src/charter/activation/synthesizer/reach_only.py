"""Reach-only synthesized artifacts by kind (#6404 tactics, #6442 styleguides).

A synthesized ``how-we-apply-*`` tactic, or a styleguide sourced from its directive
(``testing_philosophy`` -> DIRECTIVE_034, ``quality_gates`` -> DIRECTIVE_030,
``documentation_policy`` -> DIRECTIVE_037), is linked FROM that directive by a
``directive:<id> --suggests--> <kind>:<slug>`` edge in the project overlay. Such an
artifact must reach action context only through that edge, never as a closure root
of its own. :func:`reach_only_ids` names those artifacts for one kind;
:func:`append_synthesized_activations` appends the artifacts a synthesis run
created for the first time to an explicit ``activated_<kind>s`` list (an absent key
stays absent, and synthesis never creates one).

An operator's removal sticks (operator ruling, 2026-10-19): every artifact id
synthesis has ever created is recorded per kind in :data:`CREATED_ARTIFACTS_PATH`
(the unreleased tactic-only record :data:`_LEGACY_CREATED_TACTICS_PATH` is still
read, never written), and a recorded id is never appended again, even when a later
run regenerates it after a ``--prune`` or a deleted manifest. Only the operator
brings it back (``spec-kitty charter activate <kind> <id>``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.org_pack_discovery import read_org_required_ids
from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml
from charter.activation.synthesizer.reconcile import REACH_ONLY_KINDS, is_synthesized_source_edge, synthesized_node_urns
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.loader import DRGLoadError, has_graph_files, load_graph_or_dir
from charter.offering.drg.models import NodeKind
from kernel.atomic import atomic_write
from kernel.charter_pack_paths import project_pack_root

__all__ = ["append_synthesized_activations", "created_slugs_by_kind", "reach_only_ids"]

#: Every reach-only artifact id synthesis has created, per kind; a listed id is never re-appended.
CREATED_ARTIFACTS_PATH = Path(".kittify/charter/synthesized-artifacts.yaml")
_LEGACY_CREATED_TACTICS_PATH = Path(".kittify/charter/synthesized-tactics.yaml")
_CREATED_ARTIFACTS_HEADER = (
    "# Artifact ids spec-kitty synthesis has created, per kind. Synthesis adds an\n"
    "# artifact to an explicit activated_<kind>s list only the first time it creates\n"
    "# it, so an artifact you remove stays removed. Written by spec-kitty; do not edit.\n"
)
_UNREADABLE_RECORD_WARNING = (
    "{path} is unreadable; no synthesized artifact was added to an activation list. Activate one with `spec-kitty charter activate <kind> <id>`."
)


class _UnreadableRecordError(ValueError):
    """A created-artifact record exists but cannot be read as per-kind lists of ids."""


def _record_key(kind: str) -> str:
    return f"created_{ArtifactKind(kind).plural}"


def _activation_key(kind: str) -> str:
    return f"activated_{ArtifactKind(kind).plural}"


def _load_record_file(path: Path) -> dict[str, Any]:
    """The mapping in one record file; empty when absent, raises when malformed."""
    if not path.exists():
        return {}
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise _UnreadableRecordError(path.as_posix()) from exc
    if not isinstance(data, dict):
        raise _UnreadableRecordError(path.as_posix())
    return dict(data)


def _ids_under(data: Mapping[str, Any], key: str, path: Path) -> set[str]:
    ids = data.get(key, [])
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise _UnreadableRecordError(path.as_posix())
    return set(ids)


def _read_record(repo_root: Path) -> tuple[dict[str, set[str]], dict[str, Any]]:
    """Per-kind recorded ids (the legacy tactic record unioned in) and the keys this module does not own."""
    path = repo_root / CREATED_ARTIFACTS_PATH
    data = _load_record_file(path)
    legacy_path = repo_root / _LEGACY_CREATED_TACTICS_PATH
    legacy = _load_record_file(legacy_path)
    recorded = {kind: _ids_under(data, _record_key(kind), path) for kind in REACH_ONLY_KINDS}
    recorded["tactic"] |= _ids_under(legacy, _record_key("tactic"), legacy_path)
    foreign = {key: value for key, value in data.items() if key not in {_record_key(kind) for kind in REACH_ONLY_KINDS}}
    return recorded, foreign


def _write_record(repo_root: Path, recorded: Mapping[str, set[str]], foreign: Mapping[str, Any]) -> None:
    body = {**{_record_key(kind): sorted(recorded[kind]) for kind in REACH_ONLY_KINDS}, **foreign}
    stream = StringIO()
    YAML().dump(body, stream)
    atomic_write(repo_root / CREATED_ARTIFACTS_PATH, f"{_CREATED_ARTIFACTS_HEADER}{stream.getvalue()}", mkdir=True)


def _manifest_slugs(repo_root: Path, kind: str) -> frozenset[str]:
    """Bare slugs of *kind* the synthesis manifest registers; empty when absent or unreadable."""
    try:
        manifest = load_yaml(repo_root / MANIFEST_PATH)
    except (OSError, ValueError, YAMLError):
        return frozenset()
    prefix = f"{kind}:"
    return frozenset(urn[len(prefix) :] for urn in synthesized_node_urns(manifest) if urn.startswith(prefix))


def reach_only_ids(repo_root: Path, kind: str) -> frozenset[str]:
    """Bare ids of synthesized *kind* artifacts that reach context only through their directive edge.

    An artifact counts only when it (a) is registered in the synthesis manifest and
    (b) is the target of an overlay edge matching the shared synthesis shape
    (:func:`is_synthesized_source_edge`). Hand-authored artifacts, hand-authored
    edges and org-required artifacts (which stay roots) never count.

    Reads the project overlay only (not the activation-filtered graph), so the set
    does not change when the owning directive is deactivated. An absent or
    unloadable overlay or manifest yields the empty set (matches ``project_degrade``).
    """
    pack_dir = project_pack_root(repo_root)
    try:
        if not pack_dir.is_dir() or not has_graph_files(pack_dir):
            return frozenset()
        graph = load_graph_or_dir(pack_dir)
    except DRGLoadError:
        return frozenset()
    prefix = f"{kind}:"
    registered = {f"{prefix}{slug}" for slug in _manifest_slugs(repo_root, kind)}
    node_urns = {node.urn for node in graph.nodes if node.kind is NodeKind(kind)} & registered
    reached = {edge.target for edge in graph.edges if is_synthesized_source_edge(edge) and edge.target in node_urns}
    if not reached:
        return frozenset()
    org_required = set(read_org_required_ids(repo_root, ArtifactKind(kind)))
    return frozenset(urn[len(prefix) :] for urn in reached) - org_required


def _first_time_slugs(
    repo_root: Path,
    slugs_by_kind: Mapping[str, list[str]],
    recorded: Mapping[str, set[str]],
) -> dict[str, list[str]]:
    """Slugs synthesis creates now for the first time: neither recorded nor in the manifest from before this run."""
    first_time: dict[str, list[str]] = {}
    for kind, slugs in slugs_by_kind.items():
        earlier = _manifest_slugs(repo_root, kind) - set(slugs)
        first_time[kind] = [slug for slug in slugs if slug not in recorded[kind] | earlier]
    return first_time


#: Kinds whose edge-less artifacts keep today's activation semantics (#6442): only a reach-only one
#: (sourced from its directive) is appended or recorded. Tactics keep the #6404 behaviour.
_SOURCED_ONLY_KINDS: frozenset[str] = frozenset({"styleguide"})


def _eligible(repo_root: Path, kind: str, slugs: list[str]) -> list[str]:
    if kind not in _SOURCED_ONLY_KINDS or not slugs:
        return slugs
    reach_only = reach_only_ids(repo_root, kind)
    return [slug for slug in slugs if slug in reach_only]


def append_synthesized_activations(repo_root: Path, created_by_kind: Mapping[str, Iterable[str]]) -> list[str]:
    """Append first-time created slugs to each explicit ``activated_<kind>s`` list; return warnings.

    *created_by_kind* maps a kind in :data:`~charter.activation.synthesizer.reconcile.REACH_ONLY_KINDS`
    to the slugs a run created. A slug counts only when synthesis has never
    created it before: neither in a created-artifact record nor in the synthesis
    manifest from before this run. Every slug is then recorded, also when the key
    is absent, so a later removal sticks; when a config write is needed the record
    follows it, so a failed write retries. An absent key is left absent (C-001). An
    unreadable record appends nothing for any kind and warns. The synthesis
    manifest's bundle hash is restamped once after a config write.
    """
    slugs_by_kind = {kind: list(dict.fromkeys(created_by_kind.get(kind, ()))) for kind in REACH_ONLY_KINDS}
    slugs_by_kind = {kind: _eligible(repo_root, kind, slugs) for kind, slugs in slugs_by_kind.items()}
    slugs_by_kind = {kind: slugs for kind, slugs in slugs_by_kind.items() if slugs}
    if not slugs_by_kind:
        return []
    try:
        recorded, foreign = _read_record(repo_root)
    except _UnreadableRecordError as exc:
        return [_UNREADABLE_RECORD_WARNING.format(path=exc)]
    first_time = _first_time_slugs(repo_root, slugs_by_kind, recorded)
    # Every slug of a participating kind is recorded, including those already in the manifest.
    updated = {
        kind: recorded[kind] | set(slugs_by_kind[kind]) | set(_eligible(repo_root, kind, sorted(_manifest_slugs(repo_root, kind))))
        if kind in slugs_by_kind
        else recorded[kind]
        for kind in REACH_ONLY_KINDS
    }

    def _record() -> None:
        if updated != recorded:
            _write_record(repo_root, updated, foreign)

    write_target = _activation_write_target(repo_root) if any(first_time.values()) else None
    additions = _config_additions(write_target[1], first_time) if write_target is not None else {}
    if write_target is None or not additions:
        _record()
        return []  # nothing to append: no config rewrite, no restamp
    warnings = _promote(additions, write_target)
    # Record only once the config write succeeded: a failed promote must leave the
    # artifact unrecorded so a later run still appends it.
    _record()
    from charter.activation.bundle_restamp import restamp_bundle_hash  # noqa: PLC0415

    restamp_bundle_hash(repo_root)
    return warnings


_WriteTarget = tuple[Path, dict[str, Any], Callable[[Path, dict[str, Any]], None]]


def _activation_write_target(repo_root: Path) -> _WriteTarget:
    from charter.activation.pack_manager import resolve_activation_write_target  # noqa: PLC0415

    target: _WriteTarget = resolve_activation_write_target(repo_root)
    return target


def _config_additions(data: Mapping[str, Any], first_time: Mapping[str, list[str]]) -> dict[str, list[str]]:
    """``{activation key: slugs to append}`` for every explicit list; absent keys are skipped."""
    additions: dict[str, list[str]] = {}
    for kind, slugs in first_time.items():
        current = data.get(_activation_key(kind))
        if current is None:
            continue
        fresh = [slug for slug in slugs if slug not in current]
        if fresh:
            additions[_activation_key(kind)] = fresh
    return additions


def _promote(additions: Mapping[str, list[str]], write_target: _WriteTarget) -> list[str]:
    from charter.activation.activation_engine import promote_activations  # noqa: PLC0415

    target_path, data, save = write_target
    outcome = promote_activations(additions, config_path=target_path, config_data=data, save=save, effective_sets={})
    return [warning for plan in outcome.committed for warning in plan.warnings]


def created_slugs_by_kind(reconciliation: object) -> dict[str, list[str]]:
    """:func:`created_slugs` for every kind in ``REACH_ONLY_KINDS`` (the one place the kind list lives)."""
    return {kind: created_slugs(reconciliation, kind) for kind in REACH_ONLY_KINDS}


def created_slugs(reconciliation: object, kind: str) -> list[str]:
    """Slugs of *kind* this run added to the synthesis manifest (empty for a missing/foreign delta).

    Only entries new to the manifest count; :func:`append_synthesized_activations`
    further drops any artifact synthesis created before (an operator's removal sticks).
    """
    from charter.activation.synthesizer.reconcile import ReconciliationDelta  # noqa: PLC0415

    if not isinstance(reconciliation, ReconciliationDelta):
        return []
    return [ref.slug for ref in reconciliation.manifest_delta.added if ref.kind == kind]
