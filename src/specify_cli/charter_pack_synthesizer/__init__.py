"""charter_pack_synthesizer — synthesizer core for the Mission Retrospective Learning Loop.

Public API:
    apply_proposals() — the only entry-point for applying retrospective proposals.
    SynthesisResult   — the return type of apply_proposals().
    ConflictGroup     — a group of mutually-conflicting proposals.
    PlannedApplication, AppliedChange, RejectedProposal — SynthesisResult sub-models.

Source-of-truth:
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/synthesizer_hook.md
    kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/data-model.md
"""

from specify_cli.charter_pack_synthesizer.apply import (
    AppliedChange,
    PlannedApplication,
    RejectedProposal,
    SynthesisResult,
    apply_proposals,
)
from specify_cli.charter_pack_synthesizer.conflict import ConflictGroup, detect_conflicts
from specify_cli.charter_pack_synthesizer.provenance import (
    is_already_applied,
    provenance_path,
    write_provenance,
)

__all__ = [
    "apply_proposals",
    "SynthesisResult",
    "PlannedApplication",
    "AppliedChange",
    "RejectedProposal",
    "ConflictGroup",
    "detect_conflicts",
    "provenance_path",
    "is_already_applied",
    "write_provenance",
]
