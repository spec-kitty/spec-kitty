"""One selection resolver for both activation writers (#6686).

An interview selection (``answers.yaml`` ``selected_<kind>``) may name an artifact
by its declared id or by its file stem, in any doctrine layer's spelling. Two
writers turn such a selection into an activation-list entry: ``charter interview``
and the ``4.0.0rc8_promote_interview_selections`` upgrade step. Each used to carry
its own resolution loop, and the two disagreed: the interview resolved through the
layer-aware :class:`~charter.activation.identity_index.IdentityIndex`
(#6406/#6407), while the upgrade resolved against the built-in pack alone, so a
perfectly valid org-pack selection was reported "unresolved" and never promoted.

:class:`SelectionResolver` is that loop, once, over the same index
``charter context`` reads: the project pack, the org packs, then built-in
(:meth:`IdentityIndex.build`). Resolution is shared; each writer keeps its own
policy for an id some layer declares but no file stem can represent -- the upgrade
reports it ("reported, never dropped silently"), the interview refuses it (Decision
``file_name_collision``) -- which is what ``refuse_ambiguous`` selects.

Import rule: this module sits above ``identity_index`` and must not import the
writers that consume it (``charter.activation.resolver``,
``charter.activation.profile_resolution``, ``specify_cli``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from charter.activation.activation_engine import ActivationIdCollisionError
from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import ArtifactKind

__all__ = [
    "SelectionResolution",
    "SelectionResolver",
    "UnresolvedSelection",
]


@dataclass(frozen=True)
class UnresolvedSelection:
    """A selected id no activation stem answers for.

    ``ambiguous`` marks a declared identity some layer holds but no file stem can
    represent (Decision ``file_name_collision``): the id is not unknown, it is
    unrepresentable. Both are reported; only the ambiguous one is refused by a
    writer that must not store a wrong artifact.
    """

    kind: ArtifactKind
    raw_id: str
    ambiguous: bool = False

    @property
    def urn(self) -> str:
        """The selection as ``<kind>:<id>``, the spelling a diagnostic names."""
        return f"{self.kind.operator_token}:{self.raw_id}"


@dataclass(frozen=True)
class SelectionResolution:
    """Resolved selections, grouped by activation key, plus the ids no stem answers for."""

    stems: dict[str, list[str]] = field(default_factory=dict)
    unresolved: list[UnresolvedSelection] = field(default_factory=list)


class SelectionResolver:
    """Resolve declared ids and stems to activation stems through every layer.

    A thin, selection-shaped view over :class:`IdentityIndex`: the index owns the
    layer precedence and the scan, this class owns only the writer's selection
    loop (probe, dedupe, collect what did not resolve).
    """

    def __init__(self, identity: IdentityIndex) -> None:
        self._identity = identity

    @classmethod
    def build(cls, repo_root: Path, *, offering_root: Path | None = None) -> SelectionResolver:
        """Index *repo_root*'s layers -- the same authority ``charter context`` reads.

        *offering_root* is the built-in layer; a caller that already resolved it
        (and reports its failure its own way) passes it, the index resolves it
        otherwise.
        """
        return cls(IdentityIndex.build(repo_root, offering_root=offering_root))

    def knows(self, kind: ArtifactKind, raw_id: str) -> bool:
        """Whether *raw_id* names an artifact of *kind* in any layer."""
        # Annotated locally: a narrow `mypy --strict` check skips `charter.*` imports
        # (pyproject override), so the index's own return types read as `Any` here.
        knows: bool = self._identity.knows(kind, raw_id)
        return knows

    def stem(self, kind: ArtifactKind, raw_id: str) -> str | None:
        """Activation stem for *raw_id*; ``None`` when no layer knows it.

        Raises :class:`ActivationIdCollisionError` for a known identity no file
        stem can represent, exactly as :meth:`IdentityIndex.stored_spelling` does:
        the caller decides whether that is a report or a refusal.
        """
        if not self.knows(kind, raw_id):
            return None
        resolved: str = self._identity.stored_spelling(kind, raw_id)
        return resolved

    def spell(self, kind: ArtifactKind, token: str) -> str:
        """*token* as the activation stem a writer stores, or as written when no stem answers for it.

        The comparison form of :meth:`stem` for a list already stored: an entry that
        is a declared id is matched by its stem (#6423), and an unknown or
        unrepresentable one stays literal so it compares as itself.
        """
        try:
            return self.stem(kind, token) or token
        except ActivationIdCollisionError:
            return token

    def stems(self, kind: ArtifactKind, raw_ids: Iterable[str]) -> set[str]:
        """Every id of *raw_ids* in its stored spelling; see :meth:`spell`."""
        return {self.spell(kind, raw_id) for raw_id in raw_ids}

    def resolve(self, selections: Mapping[ArtifactKind, Sequence[str]], *, refuse_ambiguous: bool = False) -> SelectionResolution:
        """Resolve every selection to its activation stem, in selection order.

        An id no layer knows is recorded in ``unresolved`` and skipped. A known
        identity with no safe stem is recorded in ``unresolved`` as ``ambiguous``
        (the upgrade reports it) or, with ``refuse_ambiguous=True``, refused with
        the index's :class:`ActivationIdCollisionError` before anything is written
        (the interview, Decision ``file_name_collision``). Stems are deduped per
        activation key, so an id named twice is promoted once.
        """
        stems: dict[str, list[str]] = {}
        unresolved: list[UnresolvedSelection] = []
        for kind, raw_ids in selections.items():
            chosen: list[str] = []
            for raw_id in raw_ids:
                try:
                    stem = self.stem(kind, raw_id)
                except ActivationIdCollisionError:
                    if refuse_ambiguous:
                        raise
                    unresolved.append(UnresolvedSelection(kind, raw_id, ambiguous=True))
                    continue
                if stem is None:
                    unresolved.append(UnresolvedSelection(kind, raw_id))
                elif stem not in chosen:
                    chosen.append(stem)
            if chosen:
                stems[f"activated_{kind.plural}"] = chosen
        return SelectionResolution(stems, unresolved)
