"""Unit tests for ``retrospective.tracer_writer`` (WP10 / T038, FR-006).

Pure-logic coverage (no subprocess, no real git -- see
``test_tracer_writer_coord_e2e.py`` for the real-git committed-tree proof):

- Attribution guard (#2960 / I-T2): blank ``actor`` raises, never silently
  persists a blanked entry.
- Category validation: an unknown category raises rather than writing to an
  arbitrary filename.
- Entry formatting / merge-not-clobber logic: the dedup check
  (``_entry_present``) and the append (``_append_entry``) that keep a
  re-append idempotent without ever re-deriving the write authority.
- Ledger-M16 (I-T4): the module's own read call site resolves via
  ``read_dir(MissionArtifactKind.TRACER_FILE)`` -- never
  ``read_dir(MissionArtifactKind.RETROSPECTIVE)`` (the forbidden short-circuit
  a lazy reuse of the retrospective generator's helper could introduce).
- ``append_tracer_finding`` routes exclusively through
  ``coordination.write_seam.write_artifact`` (the WP03 helper) -- never a
  bespoke compute-and-commit path -- with the artifact staged locally under
  the primary checkout's ``kitty-specs/<mission>/traces/<file>`` and residue
  cleanup requested for that same path.
- Fail-closed on an unmaterialised coord read (#4959 / WP02 / T006-T007):
  ``_read_current_coord_content`` must PROPAGATE
  ``CoordinationWorktreeUnmaterialized`` rather than degrade it to ``""``
  (which ``append_tracer_finding`` would then clobber with a from-scratch
  header), and must refuse (propagate) on an undecodable byte in an
  EXISTING file rather than treat corruption as "no content". See
  ``contracts/reader-partition-contract.md`` (AC-T1 / AC-T2 / AC-T3).
"""

from __future__ import annotations

from kernel.clock import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mission_runtime import ActionContextError, MissionArtifactKind
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.coordination.write_seam import WriteSeamResult
from specify_cli.retrospective import tracer_writer
from specify_cli.retrospective.tracer_writer import (
    TRACER_CATEGORIES,
    TracerAttributionError,
    TracerCategoryError,
    append_tracer_finding,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_SLUG = "tracer-writer-demo-01TESTMID"


def _policy() -> object:
    class _Policy:
        def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
            return False

    return _Policy()


# ---------------------------------------------------------------------------
# Attribution guard (#2960 / I-T2)
# ---------------------------------------------------------------------------


class TestAttributionGuard:
    @pytest.mark.parametrize("actor", ["", "   ", "\t\n"])
    def test_blank_actor_raises_and_never_reaches_write_artifact(
        self, tmp_path: Path, actor: str
    ) -> None:
        with patch(
            "specify_cli.retrospective.tracer_writer.write_artifact",
            side_effect=AssertionError("write_artifact must not be called on a blank actor"),
        ), pytest.raises(TracerAttributionError):
            append_tracer_finding(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                category="tooling-friction",
                entry="A CLI hung mid-write.",
                actor=actor,
                policy=_policy(),
            )

    def test_non_blank_actor_is_preserved_verbatim_in_entry(self) -> None:
        line = tracer_writer._format_entry_line(
            entry_date=date(2026, 7, 29),
            actor="claude",
            entry="the finding text",
        )
        assert "claude" in line
        assert line.startswith("2026-07-29")


# ---------------------------------------------------------------------------
# Category validation
# ---------------------------------------------------------------------------


class TestCategoryValidation:
    def test_unknown_category_raises(self, tmp_path: Path) -> None:
        with pytest.raises(TracerCategoryError):
            append_tracer_finding(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                category="not-a-real-category",
                entry="text",
                actor="claude",
                policy=_policy(),
            )

    def test_every_documented_category_has_a_filename(self) -> None:
        assert set(TRACER_CATEGORIES) == {
            "tooling-friction",
            "approach",
            "design-decisions",
        }
        for filename in TRACER_CATEGORIES.values():
            assert filename.endswith(".md")


# ---------------------------------------------------------------------------
# Entry formatting / merge-not-clobber logic
# ---------------------------------------------------------------------------


class TestEntryMergeLogic:
    def test_entry_present_detects_exact_line(self) -> None:
        content = "# Tracer: approach\n\n---\n\n2026-07-29 · claude · did the thing\n"
        line = "2026-07-29 · claude · did the thing"
        assert tracer_writer._entry_present(content, line)

    def test_entry_present_false_for_a_different_line(self) -> None:
        content = "# Tracer: approach\n\n---\n\n2026-07-29 · claude · did the thing\n"
        other = "2026-07-29 · claude · did a DIFFERENT thing"
        assert not tracer_writer._entry_present(content, other)

    def test_append_entry_adds_exactly_one_new_line(self) -> None:
        content = "# Tracer: approach\n\n---\n"
        line = "2026-07-29 · claude · first finding"
        merged = tracer_writer._append_entry(content, line)
        assert merged.count(line) == 1
        assert merged.endswith(line + "\n")

    def test_append_entry_twice_is_not_itself_deduping(self) -> None:
        """``_append_entry`` is a pure append -- callers must gate on
        ``_entry_present`` first (as ``append_tracer_finding`` does); this
        pins that ``_append_entry`` alone has no dedup opinion, so the
        dedup responsibility is legible at the ``append_tracer_finding``
        call site rather than silently split across two functions."""
        content = "# Tracer: approach\n\n---\n"
        line = "2026-07-29 · claude · repeated finding"
        once = tracer_writer._append_entry(content, line)
        twice = tracer_writer._append_entry(once, line)
        assert twice.count(line) == 2


# ---------------------------------------------------------------------------
# Ledger-M16 (I-T4): read call site uses TRACER_FILE, never RETROSPECTIVE
# ---------------------------------------------------------------------------


class TestLedgerM16ReadCallSite:
    def test_read_current_content_resolves_via_tracer_file_kind_only(
        self, tmp_path: Path
    ) -> None:
        seen_kinds: list[MissionArtifactKind] = []

        def _fake_read_dir(kind: MissionArtifactKind) -> Path:
            seen_kinds.append(kind)
            if kind is MissionArtifactKind.RETROSPECTIVE:
                raise AssertionError(
                    "must never resolve RETROSPECTIVE from the tracer read call site"
                )
            return tmp_path

        with patch("specify_cli.retrospective.tracer_writer.placement_seam") as seam_ctor:
            seam_ctor.return_value = MagicMock(read_dir=_fake_read_dir)
            content = tracer_writer._read_current_coord_content(
                tmp_path, _MISSION_SLUG, "tooling-friction.md"
            )

        assert content == ""  # no file at tmp_path/traces/tooling-friction.md
        assert seen_kinds == [MissionArtifactKind.TRACER_FILE]

    def test_unroutable_read_degrades_to_empty_base_not_a_raise(
        self, tmp_path: Path
    ) -> None:
        """A read-side resolution failure (no coord surface yet) degrades to an
        empty base -- the WRITE side's own FR-011 probe (inside
        ``write_artifact``) is the canonical authority for reporting an
        unroutable target; this read helper must not pre-empt it with its own
        raise."""
        with patch("specify_cli.retrospective.tracer_writer.placement_seam") as seam_ctor:
            seam_ctor.return_value = MagicMock(
                read_dir=MagicMock(
                    side_effect=ActionContextError(
                        "FEATURE_CONTEXT_UNRESOLVED", "mission does not resolve"
                    )
                )
            )
            content = tracer_writer._read_current_coord_content(
                tmp_path, _MISSION_SLUG, "tooling-friction.md"
            )
        assert content == ""


# ---------------------------------------------------------------------------
# Fail-closed on an unmaterialised coord read (#4959 / WP02 / T006-T007)
# ---------------------------------------------------------------------------


def _unmaterialized_error(mission_slug: str, tmp_path: Path) -> CoordinationWorktreeUnmaterialized:
    return CoordinationWorktreeUnmaterialized.for_mission(
        repo_root=tmp_path,
        mission_slug=mission_slug,
        mid8="01TESTMID",
        coordination_branch=f"kitty/mission-{mission_slug}",
        primary_candidate=tmp_path,
    )


class TestFailClosedOnUnmaterializedCoordRead:
    """AC-T1/AC-T2 (contracts/reader-partition-contract.md): a coord-partition
    read that cannot resolve because the coordination worktree is
    unmaterialised must PROPAGATE, never degrade to ``""`` -- the degrade is
    exactly what let ``append_tracer_finding`` clobber a real, already
    coord-committed ``traces/<cat>.md`` with a from-scratch header (module
    docstring "Why a read-before-write at all"; the #4959 bug class). An
    undecodable byte on an EXISTING file is likewise a refusal, not "no
    content"."""

    def test_unmaterialized_coord_raise_propagates_not_swallowed_to_empty(
        self, tmp_path: Path
    ) -> None:
        exc = _unmaterialized_error(_MISSION_SLUG, tmp_path)
        with patch(
            "specify_cli.retrospective.tracer_writer.placement_seam"
        ) as seam_ctor:
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(side_effect=exc))
            with pytest.raises(CoordinationWorktreeUnmaterialized):
                tracer_writer._read_current_coord_content(
                    tmp_path, _MISSION_SLUG, "tooling-friction.md"
                )

    def test_undecodable_existing_file_refuses_not_empty(self, tmp_path: Path) -> None:
        """Corruption is not "no content" (AC-T2): an existing traces file with
        an undecodable byte must raise, never silently degrade to ``""``."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        (traces_dir / "tooling-friction.md").write_bytes(
            b"# Tracer\n\n\xff\xfe not valid utf-8\n"
        )
        with patch(
            "specify_cli.retrospective.tracer_writer.placement_seam"
        ) as seam_ctor:
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(return_value=tmp_path))
            with pytest.raises(UnicodeDecodeError):
                tracer_writer._read_current_coord_content(
                    tmp_path, _MISSION_SLUG, "tooling-friction.md"
                )

    def test_append_tracer_finding_fails_closed_never_calls_write_artifact(
        self, tmp_path: Path
    ) -> None:
        """The propagated raise must stop ``append_tracer_finding`` BEFORE it
        ever reaches ``write_artifact`` (i.e. before staging/committing a
        from-scratch-header clobber) -- and must leave no local staging
        residue behind either."""
        exc = _unmaterialized_error(_MISSION_SLUG, tmp_path)
        with (
            patch(
                "specify_cli.retrospective.tracer_writer.placement_seam"
            ) as seam_ctor,
            patch(
                "specify_cli.retrospective.tracer_writer.write_artifact",
                side_effect=AssertionError(
                    "write_artifact must not be called when the coord read fails closed"
                ),
            ),
        ):
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(side_effect=exc))
            with pytest.raises(CoordinationWorktreeUnmaterialized):
                append_tracer_finding(
                    repo_root=tmp_path,
                    mission_slug=_MISSION_SLUG,
                    category="tooling-friction",
                    entry="A real finding that must never be lost.",
                    actor="claude",
                    policy=_policy(),
                )
        staged = (
            tmp_path / "kitty-specs" / _MISSION_SLUG / "traces" / "tooling-friction.md"
        )
        assert not staged.exists(), (
            "a fail-closed read must never materialize the local staging file"
        )

    def test_resolved_absent_file_still_returns_empty_first_write_regression(
        self, tmp_path: Path
    ) -> None:
        """T008 regression: a resolved-but-absent file (legitimate first
        append) must still degrade to ``""`` -- the narrowed catch must not
        overcorrect into refusing a genuine first write."""
        with patch(
            "specify_cli.retrospective.tracer_writer.placement_seam"
        ) as seam_ctor:
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(return_value=tmp_path))
            content = tracer_writer._read_current_coord_content(
                tmp_path, _MISSION_SLUG, "tooling-friction.md"
            )
        assert content == ""

    def test_resolved_present_file_returns_its_content_regression(
        self, tmp_path: Path
    ) -> None:
        """T008 regression: a materialised coord surface with a present file
        still returns its real content (normal-append path unaffected)."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()
        (traces_dir / "tooling-friction.md").write_text(
            "# Tracer: tooling-friction\n\n---\n\n"
            "2026-01-01 · claude · a pre-existing finding\n",
            encoding="utf-8",
        )
        with patch(
            "specify_cli.retrospective.tracer_writer.placement_seam"
        ) as seam_ctor:
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(return_value=tmp_path))
            content = tracer_writer._read_current_coord_content(
                tmp_path, _MISSION_SLUG, "tooling-friction.md"
            )
        assert "a pre-existing finding" in content


# ---------------------------------------------------------------------------
# append_tracer_finding routes exclusively through write_seam.write_artifact
# ---------------------------------------------------------------------------


class TestRoutesThroughWriteSeamHelper:
    def test_calls_write_artifact_with_tracer_file_kind_and_staged_local_path(
        self, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}

        def _fake_write_artifact(**kwargs: object) -> WriteSeamResult:
            captured.update(kwargs)
            return WriteSeamResult(
                status="committed",
                entry_id=str(kwargs["entry_id"]),
                destination_surface="kitty/mission-demo",
                commit_hash="deadbee",
            )

        with (
            patch(
                "specify_cli.retrospective.tracer_writer.placement_seam"
            ) as seam_ctor,
            patch(
                "specify_cli.retrospective.tracer_writer.write_artifact",
                side_effect=_fake_write_artifact,
            ),
        ):
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(return_value=tmp_path))

            result = append_tracer_finding(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                category="design-decisions",
                entry="Chose X over Y because Z.",
                actor="claude",
                policy=_policy(),
            )

        assert result.status == "committed"
        assert captured["kind"] is MissionArtifactKind.TRACER_FILE

        # WP04 / T015 (#3073 no-residue thunk): tracer_writer now passes a
        # ``stage=`` thunk, not pre-staged ``files=`` -- the mkdir+write_text
        # moved INTO the thunk so a refused write never touches disk. This
        # mock never routes through write_seam's real probe-before-stage
        # locus, so it invokes the captured thunk directly to verify what it
        # WOULD materialize (mirroring what write_artifact does internally
        # after a successful probe).
        assert "files" not in captured, (
            "tracer_writer must pass stage=, not the historical files= contract"
        )
        stage = captured["stage"]
        assert callable(stage)
        files = stage()
        assert isinstance(files, tuple) and len(files) == 1
        staged_path = files[0]
        assert isinstance(staged_path, Path)
        assert staged_path == (
            tmp_path
            / "kitty-specs"
            / _MISSION_SLUG
            / "traces"
            / "design-decisions.md"
        )
        assert staged_path.exists(), "invoking the thunk must materialize the local file on disk"
        assert "Chose X over Y because Z." in staged_path.read_text(encoding="utf-8")
        # Residue cleanup (R6): the staged local copy is eligible for post-stage
        # deletion so it never lingers as an untracked primary-checkout file.
        # This is populated eagerly (independent of the thunk -- the intended
        # local path is known before materialization), so it is already
        # correct even before ``stage()`` above is invoked.
        assert captured["primary_paths_created_this_invocation"] == frozenset({staged_path})

    def test_result_is_the_write_seam_result_returned_verbatim(self, tmp_path: Path) -> None:
        expected = WriteSeamResult(
            status="refused",
            entry_id="tooling-friction-abc123",
            destination_surface=None,
            diagnostic="refused: unroutable target",
        )
        with (
            patch(
                "specify_cli.retrospective.tracer_writer.placement_seam"
            ) as seam_ctor,
            patch(
                "specify_cli.retrospective.tracer_writer.write_artifact",
                return_value=expected,
            ),
        ):
            seam_ctor.return_value = MagicMock(read_dir=MagicMock(return_value=tmp_path))
            result = append_tracer_finding(
                repo_root=tmp_path,
                mission_slug=_MISSION_SLUG,
                category="tooling-friction",
                entry="text",
                actor="claude",
                policy=_policy(),
            )
        assert result is expected
