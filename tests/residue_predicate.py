"""A ``ResidueClassifier`` built from a bare path predicate, for tests that pin ONE disposability rule.

Production code passes a ``ResidueContext`` (which checkout, which Mission); a test
that exercises the dirty scan itself only needs "this path is residue, that one is
not", and states it with :func:`residue_when`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PredicateResidue:
    """Satisfies ``specify_cli.git.ref_advance.ResidueClassifier`` for every checkout alike."""

    predicate: Callable[[str], bool]

    def is_disposable(self, path: str) -> bool:
        return self.predicate(path)

    def for_checkout(self, _repo_root: Path, _worktree: Path) -> PredicateResidue:
        return self


def residue_when(predicate: Callable[[str], bool]) -> PredicateResidue:
    """The classifier that treats exactly the paths ``predicate`` accepts as disposable."""
    return PredicateResidue(predicate)
