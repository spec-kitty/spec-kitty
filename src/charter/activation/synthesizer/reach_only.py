"""Reach-only synthesized tactics (#6404).

A synthesized ``how-we-apply-*`` tactic is linked FROM its directive by a
``directive:<id> --suggests--> tactic:<slug>`` edge in the project overlay. Such a
tactic must reach action context only through that edge, never as a closure root
of its own. :func:`reach_only_tactic_ids` names those tactics;
:func:`append_synthesized_tactic_activations` appends the tactics a synthesis run
created to an explicit ``activated_tactics`` list (an absent key stays absent).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ruamel.yaml.error import YAMLError

from charter.activation.org_pack_discovery import read_org_required_ids
from charter.activation.synthesizer.reconcile import is_synthesized_tactic_edge, synthesized_node_urns
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.loader import DRGLoadError, has_graph_files, load_graph_or_dir
from charter.offering.drg.models import NodeKind
from kernel.charter_pack_paths import project_pack_root

__all__ = ["append_synthesized_tactic_activations", "created_tactic_slugs", "reach_only_tactic_ids"]

_ACTIVATED_TACTICS_KEY = "activated_tactics"
_TACTIC_PREFIX = "tactic:"


def _manifest_tactic_urns(repo_root: Path) -> frozenset[str]:
    """``tactic:<slug>`` URNs the synthesis manifest registers; empty when absent or unreadable."""
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml  # noqa: PLC0415

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
    """Append *tactic_slugs* to an explicit ``activated_tactics`` list; return warnings.

    An absent key is left absent (C-001). The synthesis manifest's bundle hash is
    restamped after the write.
    """
    from charter.activation.activation_engine import promote_activations  # noqa: PLC0415
    from charter.activation.bundle_restamp import restamp_bundle_hash  # noqa: PLC0415
    from charter.activation.pack_manager import resolve_activation_write_target  # noqa: PLC0415

    slugs = list(dict.fromkeys(tactic_slugs))
    if not slugs:
        return []
    target_path, data, save = resolve_activation_write_target(repo_root)
    current = data.get(_ACTIVATED_TACTICS_KEY)
    if current is None:
        return []
    slugs = [slug for slug in slugs if slug not in current]
    if not slugs:
        return []  # nothing new: no config rewrite, no restamp
    outcome = promote_activations(
        {_ACTIVATED_TACTICS_KEY: slugs},
        config_path=target_path,
        config_data=data,
        save=save,
        effective_sets={},
    )
    restamp_bundle_hash(repo_root)
    return [warning for plan in outcome.committed for warning in plan.warnings]


def created_tactic_slugs(reconciliation: object) -> list[str]:
    """Tactic slugs this run added to the synthesis manifest (empty for a missing/foreign delta).

    Only entries new to the manifest count: a tactic an operator removed from
    ``activated_tactics`` stays in the manifest and is not re-added by a later run.
    """
    from charter.activation.synthesizer.reconcile import ReconciliationDelta  # noqa: PLC0415

    if not isinstance(reconciliation, ReconciliationDelta):
        return []
    return [ref.slug for ref in reconciliation.manifest_delta.added if ref.kind == "tactic"]
