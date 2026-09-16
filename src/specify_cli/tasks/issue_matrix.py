"""Structured issue-matrix core: schema, canonical writer, and scaffold.

Per FR-009 of the test-stabilization-and-debt-pass mission (closes #1163),
migrated to a structured JSON artifact by write-side-seam-matrix-tracer-
01KYP3MH WP05 (C-008 / FR-002 / FR-013).

``issue-matrix.json`` is the **single canonical artifact** going forward --
no ``issue-matrix.md`` render is emitted (D-2 / decisions/index.json). The
row schema mirrors the closed-set vocabulary NFR-007 already encodes ONCE in
``specify_cli.cli.commands.review._issue_matrix`` (``MANDATORY_COLUMNS`` /
``NAMED_OPTIONAL_COLUMNS`` / ``IssueMatrixVerdict``) rather than inventing a
second one: ``verdict`` and ``evidence_ref`` are stored as free-form strings
here (a freshly scaffolded row starts as the placeholder ``"unknown"``
verdict, exactly like the retired markdown scaffold) -- the closed-set
ENFORCEMENT lives solely in ``validate_issue_matrix`` (one validator).

The canonical writer (:func:`write_issue_matrix`) routes every commit
through the WP03 write-seam helper
(:func:`specify_cli.coordination.write_seam.write_artifact`,
``write_target(ISSUE_MATRIX)``) -- never a hand-rolled commit path
(C-001/C-006). Back-compat (failover-read of a legacy ``.md``, migrate-on-
write, and the ONE canonical dir-based reader) lives in the sibling module
``specify_cli.tasks.issue_matrix_migration`` (T022/T023, FR-013).

The scaffold (:func:`scaffold_issue_matrix`) is **idempotent**: an existing
matrix (either format, on whichever surface it resolves to) is never
overwritten, so operator edits survive re-runs.

post-merge-write-authoring-finish-01KYRRM5 WP06 (#1738 FR-012/FR-013)
------------------------------------------------------------------------
:func:`detect_issue_references` also recognises a **same-repo** GitHub
issue URL (``https://github.com/spec-kitty/spec-kitty/issues/<n>``), not
only ``#NNNN`` -- one regex, match-then-filter in Python (see
``_CANONICAL_REPO_SLUG``); a cross-repo URL is matched but filtered before
it can ever become an :class:`IssueReference`, so it cannot newly require a
matrix row. Every discovered reference now also carries ``source_file``
provenance (the basename of the file it was found in), round-tripped
through :class:`IssueMatrixEntry`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from specify_cli.core.owned_mission import effective_root_kwargs

if TYPE_CHECKING:
    from specify_cli.coordination.write_seam import ProtectionPolicyLike, WriteSeamResult

ISSUE_MATRIX_JSON_FILENAME = "issue-matrix.json"
ISSUE_MATRIX_MD_FILENAME = "issue-matrix.md"
ISSUE_MATRIX_SCHEMA_VERSION = 1

# Scaffold placeholders (T021) -- unchanged wording from the retired markdown
# scaffold so the "fill this in" signal stays familiar to operators/agents.
_SCAFFOLD_VERDICT_PLACEHOLDER = "unknown"
_SCAFFOLD_TITLE_PLACEHOLDER = "<fill at WP-implementation time>"
_SCAFFOLD_EVIDENCE_PLACEHOLDER = "<link or commit>"

# Match ``#NNNN`` GH issue references with 2-6 digits, requiring a non-word
# leading boundary (start-of-line, whitespace, ``(``, ``[``) and a non-word
# trailing boundary (whitespace, ``)``, ``]``, ``,``, ``;``, ``.``, EOL); OR
# a GitHub issue URL (``https://github.com/<owner>/<repo>/issues/<n>``,
# owner/repo captured for the Python-side same-repo/cross-repo split below
# -- FR-012, #1738). Anchored to ``/issues/`` ONLY -- a ``/pull/`` URL is
# never treated as an issue reference. The URL arm's trailing boundary
# additionally admits ``#`` (an anchor, e.g. ``#issuecomment-...``) and a
# trailing ``/`` so those are captured rather than silently dropped.
#
# This deliberately rejects:
#   * markdown anchor links like ``#section-name`` (alphabetical, not 2-6 digits)
#   * heading markers like ``# Title`` (no digits)
#   * tiny one-digit refs like ``#1`` (too few digits)
#   * runs of seven-plus digits (out of GitHub's typical issue-number range)
#   * ``/pull/<n>`` URLs (a PR is not an issue)
#
# The prefix alternation is written as a non-capturing OUTER group so the
# hash arm's digit capture stays ``match.group(1)`` exactly as before (the
# existing ``int(match.group(1))`` call keeps working unmodified) -- no new
# capturing group is introduced ahead of it. The URL arm's digits land in
# the named group ``url_number`` instead, since ``owner``/``repo`` must be
# captured first to mirror the URL's own left-to-right shape.
_GH_ISSUE_PATTERN = re.compile(
    r"(?:^|\s|\(|\[)#(\d{2,6})(?=\s|\)|\]|,|;|\.|$)"
    r"|"
    r"https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/issues/"
    r"(?P<url_number>\d{2,6})(?=\s|\)|\]|,|;|\.|#|/|$)",
    re.MULTILINE,
)

# Canonical own-repo slug (``owner/repo``) used to distinguish same-repo
# GitHub issue-URL references from cross-repo/prior-art URLs (FR-012,
# #1738). Deliberately a hardcoded literal, NOT derived from the git
# remote: ``detect_issue_references`` is a pure text parser that must stay
# deterministic across the tmp-repo fixtures the test suite builds --
# git-remote introspection would inject non-determinism and break them.
# No canonical repo-slug constant existed elsewhere in the codebase to
# reuse (D7 research finding); this is the single Python-side
# discrimination point (match-then-filter), not a second regex.
_CANONICAL_REPO_SLUG = "spec-kitty/spec-kitty"
# Historical mission references remain same-repo after the repository rename.
_LEGACY_REPO_SLUGS = frozenset({"priivacy-ai/spec-kitty"})
_SAME_REPO_SLUGS = frozenset({_CANONICAL_REPO_SLUG.casefold()}) | _LEGACY_REPO_SLUGS


def _matched_issue_number(match: re.Match[str]) -> int | None:
    """Extract the same-repo issue number from a ``_GH_ISSUE_PATTERN`` match.

    Returns ``None`` for a cross-repo GitHub issue URL: the regex matches
    ANY ``owner/repo``, and this is the single Python-side filter that keeps
    a cross-repo URL from ever becoming an :class:`IssueReference` -- so it
    cannot newly require an issue-matrix row / block the completeness gate
    (SC-008).
    """
    if match.group(1) is not None:
        return int(match.group(1))
    # GitHub owner/repo slugs are case-insensitive, so a same-repo URL authored
    # with non-canonical casing (e.g. ``priivacy-ai/spec-kitty``) must still be
    # recognised -- a case-sensitive compare would silently drop it, a
    # false-negative that lets a real same-repo issue escape the completeness
    # gate (SC-008). Compare case-folded on both sides.
    owner_repo = f"{match.group('owner')}/{match.group('repo')}"
    if owner_repo.casefold() not in _SAME_REPO_SLUGS:
        return None
    return int(match.group("url_number"))


class IssueReference(NamedTuple):
    """A single GH issue reference detected in a mission artifact.

    Attributes:
        number: Issue number, e.g. ``1163``.
        first_line_context: The first line in the source file where the
            issue appears, stripped of leading and trailing whitespace.
            Useful for generating evidence hints in the matrix.
        source_file: Basename of the file the reference was discovered in
            (e.g. ``"spec.md"``, ``"WP01.md"``) -- provenance for FR-013
            (#1738).
    """

    number: int
    first_line_context: str
    source_file: str


def detect_issue_references(spec_md_path: Path) -> list[IssueReference]:
    """Return the unique list of GH issue refs in a file, ordered by first appearance.

    Recognises ``#NNNN`` (2-6 digits) and same-repo GitHub issue URLs alike
    (FR-012, #1738; see ``_GH_ISSUE_PATTERN``). Skips refs that look like
    markdown anchor links (``#section-name``) and cross-repo/prior-art
    issue URLs (never returned as a reference -- SC-008).

    Args:
        spec_md_path: Filesystem path to the mission artifact to scan (e.g.
            ``spec.md``, a ``tasks/WP01.md`` file).

    Returns:
        Ordered list of :class:`IssueReference` entries with no duplicates,
        each carrying ``spec_md_path.name`` as its ``source_file``. Empty
        list if ``spec_md_path`` contains no (same-repo) GH issue
        references.
    """
    text = spec_md_path.read_text(encoding="utf-8")
    source_file = spec_md_path.name
    seen: dict[int, str] = {}
    for line in text.splitlines():
        for match in _GH_ISSUE_PATTERN.finditer(line):
            num = _matched_issue_number(match)
            if num is None:
                continue  # cross-repo URL -- filtered, never a reference (FR-012)
            if num not in seen:
                seen[num] = line.strip()
    return [IssueReference(num, ctx, source_file) for num, ctx in seen.items()]


# ---------------------------------------------------------------------------
# T020 -- structured schema + canonical writer
# ---------------------------------------------------------------------------

# Field names persisted per row -- kept in one tuple so the round-trip
# (to_dict/from_dict) and any future schema-drift check share one spelling
# (S1192).
_ENTRY_FIELDS: tuple[str, ...] = (
    "verdict",
    "evidence_ref",
    "title",
    "scope",
    "wp",
    "fr",
    "nfr",
    "sc",
    "repo",
    "source_file",
)


@dataclass(frozen=True)
class IssueMatrixEntry:
    """One row of the structured ``issue-matrix.json`` (T020).

    Mirrors the closed-set column vocabulary NFR-007 already encodes in
    ``review._issue_matrix`` (``MANDATORY_COLUMNS`` / ``NAMED_OPTIONAL_COLUMNS``)
    rather than a second one. ``verdict`` / ``evidence_ref`` are free-form
    strings by design: a freshly scaffolded row is not yet a valid
    ``IssueMatrixVerdict`` member (the placeholder ``"unknown"``) --
    membership enforcement is ``validate_issue_matrix``'s job, not the
    writer's.
    """

    verdict: str = _SCAFFOLD_VERDICT_PLACEHOLDER
    evidence_ref: str = ""
    title: str | None = None
    scope: str | None = None
    wp: str | None = None
    fr: str | None = None
    nfr: str | None = None
    sc: str | None = None
    repo: str | None = None
    source_file: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in _ENTRY_FIELDS}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> IssueMatrixEntry:
        kwargs = {name: data.get(name) for name in _ENTRY_FIELDS if name in data}
        verdict = kwargs.pop("verdict", None)
        evidence_ref = kwargs.pop("evidence_ref", None)
        return cls(
            verdict=str(verdict) if verdict is not None else _SCAFFOLD_VERDICT_PLACEHOLDER,
            evidence_ref=str(evidence_ref) if evidence_ref is not None else "",
            **kwargs,
        )


def build_issue_matrix_document(rows: Mapping[str, IssueMatrixEntry]) -> dict[str, Any]:
    """Serialize ``rows`` (keyed by canonicalized issue ref) to the JSON document shape."""
    return {
        "schema_version": ISSUE_MATRIX_SCHEMA_VERSION,
        "rows": {issue_ref: entry.to_dict() for issue_ref, entry in rows.items()},
    }


def parse_issue_matrix_document(data: Mapping[str, Any]) -> dict[str, IssueMatrixEntry]:
    """Inverse of :func:`build_issue_matrix_document` -- round-trips ``rows``."""
    raw_rows = data.get("rows", {})
    if not isinstance(raw_rows, Mapping):
        return {}
    return {str(issue_ref): IssueMatrixEntry.from_dict(entry) for issue_ref, entry in raw_rows.items() if isinstance(entry, Mapping)}


def write_issue_matrix(
    *,
    repo_root: Path,
    mission_slug: str,
    feature_dir: Path,
    rows: Mapping[str, IssueMatrixEntry],
    policy: ProtectionPolicyLike,
    actor: str = "system",
    target_branch: str | None = None,
    effective_root: Path | None = None,
) -> WriteSeamResult:
    """The ONE canonical ``issue-matrix.json`` writer (T020).

    Serializes ``rows`` to ``feature_dir/issue-matrix.json`` and routes the
    commit through :func:`write_target(ISSUE_MATRIX)
    <mission_runtime.PlacementSeam.write_target>` via the WP03 write-seam
    helper (:func:`specify_cli.coordination.write_seam.write_artifact`) --
    never a hand-rolled commit path (C-001/C-006). No ``issue-matrix.md`` is
    ever emitted by this writer (C-008).

    ``feature_dir``'s local copy is materialized via a ``stage=`` thunk
    (WP04 / #3073 / T029): :func:`write_artifact`'s single locus invokes it
    ONLY after the routability probe succeeds, so a refused write never
    touches disk and leaves zero untracked residue (the write-seam
    materialises a coord copy and cleans up the primary residue for coord
    topologies -- see ``commit_router._stage_artifacts_in_coord_worktree``
    R6).
    """
    from specify_cli.coordination.write_seam import write_artifact
    from mission_runtime import MissionArtifactKind

    path = feature_dir / ISSUE_MATRIX_JSON_FILENAME
    document = build_issue_matrix_document(rows)

    def _stage() -> tuple[Path, ...]:
        # T029 (#3073): the write moves INTO the thunk so a refused write
        # never materializes ``issue-matrix.json`` on disk (no residue).
        path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return (path,)

    return write_artifact(
        repo_root=repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.ISSUE_MATRIX,
        stage=_stage,
        message=f"chore: update issue-matrix for {mission_slug}",
        policy=policy,
        entry_id=actor,
        target_branch=target_branch,
        primary_paths_created_this_invocation=frozenset({path}),
        effective_root=effective_root,
    )


# ---------------------------------------------------------------------------
# T021 (B3) -- finalize scaffold, COORD via write_target(ISSUE_MATRIX)
# ---------------------------------------------------------------------------


def scaffold_issue_matrix(
    feature_dir: Path,
    spec_md_path: Path,
    *,
    repo_root: Path,
    mission_slug: str,
    policy: ProtectionPolicyLike,
    target_branch: str | None = None,
    effective_root: Path | None = None,
) -> Path | None:
    """Author ``issue-matrix.json`` from detected GH issue refs (B3).

    Routed via :func:`write_issue_matrix` (``write_target(ISSUE_MATRIX)``) --
    lands on COORD for coord/lanes-with-coord topologies, never a stray
    ``issue-matrix.md`` on the planning (primary) dir. This closes B3: the
    former ``.md``-on-primary scaffold meant FR-013 migrate-on-write never
    fired for a greenfield mission (permanent split-brain).

    The scaffold is **idempotent**: an existing matrix -- either format, on
    whichever surface (coord or primary) it resolves to -- is never
    overwritten, so operator edits (or an already-migrated mission) survive
    re-runs. The existence check is COORD-aware (:func:`coord_read_dir_for`)
    because a prior write may already have unlinked the local primary copy
    (write-seam residue cleanup, R6) -- a bare ``feature_dir``-local
    ``.exists()`` would then wrongly see "nothing here" and re-scaffold.

    Args:
        feature_dir: The ``kitty-specs/<slug>/`` planning directory.
        spec_md_path: The mission's ``spec.md`` (used to detect issue refs).
        repo_root: Primary checkout root.
        mission_slug: Mission handle.
        policy: A duck-typed ``is_protected(ref) -> bool`` protection policy.
        target_branch: Optional short primary branch name (ff-advance).

    Returns:
        Path to the scaffolded (or pre-existing) ``issue-matrix.json``, or
        ``None`` when ``spec.md`` references no GH issues (no file created)
        or the write was refused/failed (best-effort, never blocking).
    """
    from mission_runtime import MissionArtifactKind, coord_read_dir_for

    if effective_root is not None:
        from mission_runtime import placement_seam

        issue_matrix_dir = placement_seam(repo_root, mission_slug, effective_root=effective_root).read_dir(MissionArtifactKind.ISSUE_MATRIX)
    else:
        issue_matrix_dir = coord_read_dir_for(repo_root, mission_slug, MissionArtifactKind.ISSUE_MATRIX) or feature_dir
    json_path = issue_matrix_dir / ISSUE_MATRIX_JSON_FILENAME
    if json_path.exists() or (issue_matrix_dir / ISSUE_MATRIX_MD_FILENAME).exists():
        # Respect existing content (JSON or legacy .md) -- idempotent re-runs
        # are a hard requirement (WP09-era reviewer guidance still applies).
        return json_path

    refs = detect_issue_references(spec_md_path)
    if not refs:
        return None

    rows = {
        f"#{ref.number}": IssueMatrixEntry(
            verdict=_SCAFFOLD_VERDICT_PLACEHOLDER,
            evidence_ref=_SCAFFOLD_EVIDENCE_PLACEHOLDER,
            title=_SCAFFOLD_TITLE_PLACEHOLDER,
            source_file=ref.source_file,
        )
        for ref in refs
    }
    result = write_issue_matrix(
        repo_root=repo_root,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        rows=rows,
        policy=policy,
        actor="finalize-scaffold",
        target_branch=target_branch,
        **effective_root_kwargs(effective_root),
    )
    if result.status in ("committed", "unchanged"):
        # ``issue_matrix_dir`` was resolved BEFORE the write and is unaffected
        # by it (routing is topology-derived, not write-order-derived) --
        # reuse it rather than ``feature_dir``, which write-seam residue
        # cleanup (R6) may already have unlinked for a coord-routed mission.
        return json_path
    if effective_root is not None:
        raise RuntimeError(result.diagnostic or "Owned issue matrix write failed.")
    return None
