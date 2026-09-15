"""Mission-review mode resolution (T018).

Resolves the review mode for a ``spec-kitty review`` invocation following the
precedence contract in:

    kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/review-mode-resolution.md

Resolution order (highest precedence first):
  1. ``--mode`` CLI flag, if present
  2. POST_MERGE if ``meta.json.baseline_merge_commit`` is set
  3. LIGHTWEIGHT otherwise

See: src/specify_cli/cli/commands/review/ERROR_CODES.md
"""

from __future__ import annotations

from enum import StrEnum

from specify_cli.cli.commands.review._diagnostics import MissionReviewDiagnostic

_MODE_MISMATCH_BODY = (
    "MISSION_REVIEW_MODE_MISMATCH: --mode post-merge was requested but "
    "meta.json.baseline_merge_commit is absent, meaning no merge has been "
    "recorded for this mission — neither via `spec-kitty merge` nor from a "
    "GitHub PR acceptance.\n\n"
    "What this means: post-merge mode requires a baseline merge commit recorded "
    "in meta.json to anchor the dead-code scan and gate-record validation. "
    "Without it, the full release-gate contract cannot be enforced.\n\n"
    "Remediation options:\n"
    "  1. Run `spec-kitty merge` to merge the mission and record the baseline "
    "commit, then retry `spec-kitty review --mode post-merge`.\n"
    "  2. If this mission landed through a GitHub PR (`acceptance_mode: pr`), "
    "record the PR's real merge commit instead: `spec-kitty accept --mode pr "
    "--merge-commit <sha>` before the PR merges, or `spec-kitty migrate "
    "backfill-merge-commit --mission <slug> --merge-commit <sha>` afterwards "
    "(#4231).\n"
    "  3. Re-run with `--mode lightweight` to perform a consistency check "
    "without the full post-merge gate requirements.\n"
    "  4. For pre-083 missions that have already been merged but lack "
    "baseline_merge_commit, run `spec-kitty migrate backfill-identity` to "
    "backfill missing identity fields, which will also record the baseline "
    "merge commit if available.\n"
)


class MissionReviewMode(StrEnum):
    """Mode of a ``spec-kitty review`` invocation.

    Resolution order (highest precedence first):
      1. --mode CLI flag, if present
      2. POST_MERGE if meta.json.baseline_merge_commit is set
      3. LIGHTWEIGHT otherwise

    See: src/specify_cli/cli/commands/review/ERROR_CODES.md
    """

    LIGHTWEIGHT = "lightweight"
    POST_MERGE = "post-merge"


def resolve_mode(
    *,
    cli_flag: str | None,
    baseline_merge_commit: str | None,
) -> tuple[MissionReviewMode, bool]:
    """Resolve the review mode from the CLI flag and meta.json state.

    Parameters
    ----------
    cli_flag:
        The value of the ``--mode`` CLI flag, or ``None`` if not provided.
    baseline_merge_commit:
        The value of ``meta.json.baseline_merge_commit``, or ``None`` if absent.

    Returns
    -------
    tuple[MissionReviewMode, bool]
        ``(mode, auto_detected)`` where ``auto_detected`` is ``True`` when the
        mode was derived from ``baseline_merge_commit`` rather than the CLI flag.

    Raises
    ------
    ModeMismatchError
        When ``--mode post-merge`` is requested but ``baseline_merge_commit`` is
        absent.
    """
    if cli_flag is not None:
        mode = MissionReviewMode(cli_flag)
        if mode is MissionReviewMode.POST_MERGE and not baseline_merge_commit:
            raise ModeMismatchError(
                diagnostic_code=MissionReviewDiagnostic.MODE_MISMATCH,
                message=_MODE_MISMATCH_BODY,
            )
        return mode, False

    if baseline_merge_commit:
        return MissionReviewMode.POST_MERGE, True

    return MissionReviewMode.LIGHTWEIGHT, True


class ModeMismatchError(ValueError):
    """Raised when ``--mode post-merge`` is requested without a baseline merge commit.

    Carries the structured diagnostic so callers can emit a JSON diagnostic body.
    """

    def __init__(
        self,
        diagnostic_code: MissionReviewDiagnostic,
        message: str,
    ) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code
        self.message = message


__all__ = [
    "MissionReviewMode",
    "ModeMismatchError",
    "resolve_mode",
]
