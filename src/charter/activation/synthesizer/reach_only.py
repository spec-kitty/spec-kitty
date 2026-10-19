"""Reach-only synthesized tactics (#6404).

A synthesized ``how-we-apply-*`` tactic is linked FROM its directive by a
``directive:<id> --suggests--> tactic:<slug>`` edge in the project overlay. Such a
tactic must reach action context only through that edge, never as a closure root
of its own. :func:`reach_only_tactic_ids` names those tactics;
:func:`append_synthesized_tactic_activations` appends the tactics a synthesis run
created for the first time to an explicit ``activated_tactics`` list (an absent key
stays absent).

An operator's removal sticks (operator ruling, 2026-10-19): every tactic id synthesis
has ever created is recorded in :data:`CREATED_TACTICS_PATH`, and a recorded id is
never appended again, even when a later run regenerates the tactic after a
``--prune`` or a deleted manifest. Only the operator brings it back
(``spec-kitty charter activate tactic <id>``).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.activation.org_pack_discovery import read_org_required_ids
from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml
from charter.activation.synthesizer.reconcile import is_synthesized_tactic_edge, synthesized_node_urns
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.loader import DRGLoadError, has_graph_files, load_graph_or_dir
from charter.offering.drg.models import NodeKind
from kernel.atomic import atomic_write
from kernel.charter_pack_paths import project_pack_root

__all__ = ["append_synthesized_tactic_activations", "created_tactic_slugs", "reach_only_tactic_ids"]

_ACTIVATED_TACTICS_KEY = "activated_tactics"
_TACTIC_PREFIX = "tactic:"
_CREATED_TACTICS_KEY = "created_tactics"

#: Every tactic id synthesis has created; a listed id is never re-appended.
CREATED_TACTICS_PATH = Path(".kittify/charter/synthesized-tactics.yaml")
_CREATED_TACTICS_HEADER = (
    "# Tactic ids spec-kitty synthesis has created. Synthesis adds a tactic to an\n"
    "# explicit activated_tactics list only the first time it creates it, so a tactic\n"
    "# you remove stays removed. Written by spec-kitty; do not edit.\n"
)
_UNREADABLE_LEDGER_WARNING = (
    "{path} is unreadable; no synthesized tactic was added to activated_tactics. Activate one with `spec-kitty charter activate tactic <id>`."
)


class _UnreadableLedgerError(ValueError):
    """The created-tactics record exists but cannot be read as a list of ids."""


def _read_created_tactics(repo_root: Path) -> set[str]:
    """Ids in the created-tactics record; empty when absent, raises when malformed."""
    path = repo_root / CREATED_TACTICS_PATH
    if not path.exists():
        return set()
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except (OSError, YAMLError) as exc:
        raise _UnreadableLedgerError(str(path)) from exc
    ids = data.get(_CREATED_TACTICS_KEY) if isinstance(data, dict) else None
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise _UnreadableLedgerError(str(path))
    return set(ids)


def _write_created_tactics(repo_root: Path, ids: set[str]) -> None:
    lines = "".join(f"- {item}\n" for item in sorted(ids))
    atomic_write(repo_root / CREATED_TACTICS_PATH, f"{_CREATED_TACTICS_HEADER}{_CREATED_TACTICS_KEY}:\n{lines}", mkdir=True)


def _manifest_tactic_urns(repo_root: Path) -> frozenset[str]:
    """``tactic:<slug>`` URNs the synthesis manifest registers; empty when absent or unreadable."""
    manifest_path = repo_root / MANIFEST_PATH
    try:
        manifest = load_yaml(manifest_path)
    except (OSError, ValueError, YAMLError):
        return frozenset()
    return frozenset(urn for urn in synthesized_node_urns(manifest) if urn.startswith(_TACTIC_PREFIX))


def reach_only_tactic_ids(repo_root: Path) -> frozenset[str]:
    """Bare ids of synthesized tactics that reach context only through their directive edge.

    A tactic counts only when it (a) is registered in the synthesis manifest and
    (b) is the target of an overlay edge matching the shared synthesis shape
    (:func:`is_synthesized_tactic_edge`). Hand-authored tactics, hand-authored
    edges and org-required tactics (which stay roots) never count.

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
    manifest_tactics = _manifest_tactic_urns(repo_root)
    tactic_urns = {node.urn for node in graph.nodes if node.kind is NodeKind.TACTIC} & manifest_tactics
    reached = {edge.target for edge in graph.edges if is_synthesized_tactic_edge(edge) and edge.target in tactic_urns}
    if not reached:
        return frozenset()
    org_required = set(read_org_required_ids(repo_root, ArtifactKind.TACTIC))
    return frozenset(urn[len(_TACTIC_PREFIX) :] for urn in reached) - org_required


def append_synthesized_tactic_activations(repo_root: Path, tactic_slugs: Iterable[str]) -> list[str]:
    """Append first-time *tactic_slugs* to an explicit ``activated_tactics`` list; return warnings.

    A slug counts only when synthesis has never created it before: neither in the
    created-tactics record nor in the synthesis manifest from before this run. Every
    slug is then recorded, also when the key is absent, so a later removal sticks.
    An absent key is left absent (C-001). An unreadable record appends nothing and
    warns. The synthesis manifest's bundle hash is restamped after a config write.
    """
    from charter.activation.activation_engine import promote_activations  # noqa: PLC0415
    from charter.activation.bundle_restamp import restamp_bundle_hash  # noqa: PLC0415
    from charter.activation.pack_manager import resolve_activation_write_target  # noqa: PLC0415

    slugs = list(dict.fromkeys(tactic_slugs))
    if not slugs:
        return []
    try:
        recorded = _read_created_tactics(repo_root)
    except _UnreadableLedgerError:
        return [_UNREADABLE_LEDGER_WARNING.format(path=CREATED_TACTICS_PATH.as_posix())]
    # Tactics already in the manifest before this run were created by an earlier one.
    earlier = {urn[len(_TACTIC_PREFIX) :] for urn in _manifest_tactic_urns(repo_root)} - set(slugs)
    first_time = [slug for slug in slugs if slug not in recorded | earlier]
    if not (set(slugs) | earlier) <= recorded:
        _write_created_tactics(repo_root, recorded | earlier | set(slugs))
    if not first_time:
        return []
    target_path, data, save = resolve_activation_write_target(repo_root)
    current = data.get(_ACTIVATED_TACTICS_KEY)
    if current is None:
        return []
    first_time = [slug for slug in first_time if slug not in current]
    if not first_time:
        return []  # nothing new: no config rewrite, no restamp
    outcome = promote_activations(
        {_ACTIVATED_TACTICS_KEY: first_time},
        config_path=target_path,
        config_data=data,
        save=save,
        effective_sets={},
    )
    restamp_bundle_hash(repo_root)
    return [warning for plan in outcome.committed for warning in plan.warnings]


def created_tactic_slugs(reconciliation: object) -> list[str]:
    """Tactic slugs this run added to the synthesis manifest (empty for a missing/foreign delta).

    Only entries new to the manifest count; :func:`append_synthesized_tactic_activations`
    further drops any tactic synthesis created before (an operator's removal sticks).
    """
    from charter.activation.synthesizer.reconcile import ReconciliationDelta  # noqa: PLC0415

    if not isinstance(reconciliation, ReconciliationDelta):
        return []
    return [ref.slug for ref in reconciliation.manifest_delta.added if ref.kind == "tactic"]
