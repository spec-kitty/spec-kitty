"""WP08 — End-of-Interview Pending Pass tests (T040 / T041 / T042 / T045).

Tests cover:
- Empty pending list → no panel rendered (silent no-op).
- Non-empty pending list → §7 Panel rendered + entries resolved.
- Failed fetch → fallback DiscussionFetch used; entry still removed from store.
- Unexpected exception in run_candidate_review → entry stays pending for retry.
- T045: already-widened question prompt for [f]etch, [d]efer, local answer, !cancel paths.
- Charter interview end-of-interview pass integration.
"""

from __future__ import annotations

import json
from kernel.clock import now_utc
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from specify_cli.widen.interview_helpers import (
    _resolve_pending_entry,
    render_already_widened_prompt,
    run_end_of_interview_pending_pass,
)
from specify_cli.widen.models import WidenPendingEntry
from specify_cli.widen.state import WidenPendingStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-widen-eoi-mission"
MISSION_ID = "01KWIDENOITEST000000000001"


def _make_mission_dir(repo_root: Path) -> None:
    mission_dir = repo_root / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_slug": MISSION_SLUG, "mission_id": MISSION_ID}),
        encoding="utf-8",
    )


def _make_entry(decision_id: str = "dec-001", question: str = "What DB?") -> WidenPendingEntry:
    return WidenPendingEntry(
        decision_id=decision_id,
        mission_slug=MISSION_SLUG,
        question_id="charter.db_choice",
        question_text=question,
        entered_pending_at=now_utc(),
        widen_endpoint_response={},
    )


def _make_store(tmp_path: Path, entries: list[WidenPendingEntry] | None = None) -> WidenPendingStore:
    _make_mission_dir(tmp_path)
    store = WidenPendingStore(tmp_path, MISSION_SLUG)
    for entry in (entries or []):
        store.add_pending(entry)
    return store


def _capture_console() -> Console:
    """Return a Console that writes to an in-memory buffer."""
    from io import StringIO

    return Console(file=StringIO(), highlight=False, markup=False)


def _console_output(console: Console) -> str:
    return console.file.getvalue()  # type: ignore[union-attr]


def _make_decision_error() -> Exception:
    from specify_cli.decisions.models import DecisionErrorCode
    from specify_cli.decisions.service import DecisionError

    return DecisionError(code=DecisionErrorCode.TERMINAL_CONFLICT)


# ---------------------------------------------------------------------------
# T040 — run_end_of_interview_pending_pass
# ---------------------------------------------------------------------------


class TestRunEndOfInterviewPendingPassNoop:
    """Empty pending list → silent no-op."""

    def test_noop_when_store_is_none(self, tmp_path: Path) -> None:
        console = _capture_console()
        mock_dm = MagicMock()
        run_end_of_interview_pending_pass(
            widen_store=None,
            saas_client=MagicMock(),
            mission_slug=MISSION_SLUG,
            repo_root=tmp_path,
            console=console,
            dm_service=mock_dm,
            actor="test",
        )
        assert "Pending" not in _console_output(console)

    def test_noop_when_store_empty(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        console = _capture_console()
        run_end_of_interview_pending_pass(
            widen_store=store,
            saas_client=MagicMock(),
            mission_slug=MISSION_SLUG,
            repo_root=tmp_path,
            console=console,
            dm_service=MagicMock(),
            actor="test",
        )
        assert "Pending" not in _console_output(console)

    def test_noop_when_list_pending_raises(self, tmp_path: Path) -> None:
        bad_store = MagicMock()
        bad_store.list_pending.side_effect = RuntimeError("boom")
        console = _capture_console()
        run_end_of_interview_pending_pass(
            widen_store=bad_store,
            saas_client=MagicMock(),
            mission_slug=MISSION_SLUG,
            repo_root=tmp_path,
            console=console,
            dm_service=MagicMock(),
            actor="test",
        )
        assert "Pending" not in _console_output(console)


class TestRunEndOfInterviewPendingPassWithEntries:
    """Non-empty pending list → panel rendered + entries processed."""

    def test_panel_rendered_for_one_entry(self, tmp_path: Path) -> None:
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )
        with patch("specify_cli.widen.review.run_candidate_review", MagicMock(return_value=object())):
            run_end_of_interview_pending_pass(
                widen_store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        output = _console_output(console)
        assert "Pending Widened Questions" in output or "1 widened question" in output or "(1/1)" in output

    def test_entries_removed_after_pass(self, tmp_path: Path) -> None:
        """After pending pass, store must be empty (T042)."""
        entry1 = _make_entry("dec-001", "Q1?")
        entry2 = _make_entry("dec-002", "Q2?")
        store = _make_store(tmp_path, [entry1, entry2])
        console = _capture_console()

        # Mock run_candidate_review to return immediately (no stdin interaction)
        mock_fetch = MagicMock(return_value=MagicMock(
            participants=[], message_count=0, thread_url=None,
            messages=[], truncated=False,
        ))
        mock_review = MagicMock(return_value=object())

        with patch("specify_cli.widen.review.run_candidate_review", mock_review), \
             patch.object(
                 type(store._internal if hasattr(store, "_internal") else store),
                 "fetch_discussion",
                 mock_fetch,
                 create=True,
             ):
            # Patch saas_client.fetch_discussion directly
            mock_saas = MagicMock()
            from specify_cli.widen.models import DiscussionFetch

            mock_saas.fetch_discussion.return_value = DiscussionFetch(
                participants=[], message_count=0, thread_url=None,
                messages=[], truncated=False,
            )

            run_end_of_interview_pending_pass(
                widen_store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        assert store.list_pending() == [], "All entries should be removed from store after pending pass"

    def test_entry_stays_pending_on_review_exception(self, tmp_path: Path) -> None:
        """Regression G0085: candidate-review crashes must not clear pending state."""
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()

        mock_saas = MagicMock()
        from specify_cli.widen.models import DiscussionFetch

        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )

        with patch(
            "specify_cli.widen.review.run_candidate_review",
            side_effect=RuntimeError("unexpected"),
        ):
            run_end_of_interview_pending_pass(
                widen_store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id

    def test_fetch_failure_uses_fallback_discussion(self, tmp_path: Path) -> None:
        """Fetch failure → fallback DiscussionFetch; run_candidate_review still called."""
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()

        from specify_cli.saas_client import SaasClientError

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.side_effect = SaasClientError("network error")

        mock_review = MagicMock(return_value=object())
        with patch("specify_cli.widen.review.run_candidate_review", mock_review):
            run_end_of_interview_pending_pass(
                widen_store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        # run_candidate_review should still have been called with fallback discussion
        mock_review.assert_called_once()
        call_kwargs = mock_review.call_args
        discussion = (
            call_kwargs.kwargs.get("discussion_data")
            or (call_kwargs.args[0] if call_kwargs.args else None)
        )
        assert discussion is not None
        assert discussion.message_count == 0
        assert store.list_pending() == []

    def test_panel_noun_plurality(self, tmp_path: Path) -> None:
        """Singular vs plural noun in panel text."""
        # Single entry → "question is"
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console_singular = _capture_console()

        mock_saas = MagicMock()
        from specify_cli.widen.models import DiscussionFetch

        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )

        with patch("specify_cli.widen.review.run_candidate_review", MagicMock(return_value=object())):
            run_end_of_interview_pending_pass(
                widen_store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console_singular,
                dm_service=MagicMock(),
                actor="test",
            )

        output = _console_output(console_singular)
        assert "1 widened question is" in output

    def test_panel_plural(self, tmp_path: Path) -> None:
        """Multiple entries → 'questions are' in panel."""
        e1 = _make_entry("dec-001", "Q1?")
        e2 = _make_entry("dec-002", "Q2?")
        store = _make_store(tmp_path, [e1, e2])
        console = _capture_console()

        mock_saas = MagicMock()
        from specify_cli.widen.models import DiscussionFetch

        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )

        with patch("specify_cli.widen.review.run_candidate_review", MagicMock(return_value=object())):
            run_end_of_interview_pending_pass(
                widen_store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        output = _console_output(console)
        assert "2 widened questions are" in output


# ---------------------------------------------------------------------------
# T041 / T042 — _resolve_pending_entry
# ---------------------------------------------------------------------------


class TestResolvePendingEntry:
    """Unit tests for the _resolve_pending_entry helper."""

    def test_removes_entry_on_success(self, tmp_path: Path) -> None:
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=["Alice"], message_count=3, thread_url=None, messages=["Hi"], truncated=False,
        )

        with patch("specify_cli.widen.review.run_candidate_review", MagicMock(return_value=object())):
            _resolve_pending_entry(
                entry=entry,
                store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        assert store.list_pending() == []

    def test_keeps_entry_on_review_exception(self, tmp_path: Path) -> None:
        """Regression G0085: review/write-back crash leaves pending entry retryable."""
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )

        with patch(
            "specify_cli.widen.review.run_candidate_review",
            side_effect=RuntimeError("crash"),
        ):
            _resolve_pending_entry(
                entry=entry,
                store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id

    def test_keeps_entry_when_review_is_cancelled(self, tmp_path: Path) -> None:
        """A non-terminal candidate-review cancellation leaves pending state retryable."""
        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )

        with patch("specify_cli.widen.review.run_candidate_review", MagicMock(return_value=None)):
            _resolve_pending_entry(
                entry=entry,
                store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=MagicMock(),
                actor="test",
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id

    def test_keeps_entry_when_review_write_back_fails(self, tmp_path: Path) -> None:
        """Regression G0085: failed terminal write-back leaves pending entry retryable."""
        from specify_cli.decisions.models import DecisionErrorCode
        from specify_cli.decisions.service import DecisionError
        from specify_cli.widen.models import DiscussionFetch

        entry = _make_entry()
        store = _make_store(tmp_path, [entry])
        console = _capture_console()
        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=[], message_count=0, thread_url=None, messages=[], truncated=False,
        )
        mock_dm = MagicMock()
        mock_dm.resolve_decision.side_effect = DecisionError(
            code=DecisionErrorCode.TERMINAL_CONFLICT
        )
        llm_payload = {
            "candidate_summary": "Team chose Postgres",
            "candidate_answer": "PostgreSQL",
            "source_hint": "slack_extraction",
        }

        with patch.object(console, "input", return_value="a"), patch(
            "specify_cli.widen.review._read_llm_response", return_value=llm_payload
        ):
            _resolve_pending_entry(
                entry=entry,
                store=store,
                saas_client=mock_saas,
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                dm_service=mock_dm,
                actor="test",
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id


# ---------------------------------------------------------------------------
# T045 — render_already_widened_prompt
# ---------------------------------------------------------------------------


class TestRenderAlreadyWidenedPrompt:
    """Tests for the §1.3 already-widened prompt."""

    def _make_store_with_entry(self, tmp_path: Path, decision_id: str = "dec-001") -> tuple[WidenPendingStore, WidenPendingEntry]:
        entry = _make_entry(decision_id=decision_id)
        store = _make_store(tmp_path, [entry])
        return store, entry

    def test_local_answer_path(self, tmp_path: Path) -> None:
        """Plain text answer → resolve_decision called, entry removed."""
        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)

        mock_dm = MagicMock()
        mock_saas = MagicMock()

        with patch.object(console, "input", return_value="PostgreSQL"), \
             patch.object(console, "print"):
            render_already_widened_prompt(
                question_text="Which database?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=mock_saas,
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        mock_dm.resolve_decision.assert_called_once()
        assert store.list_pending() == []

    def test_local_answer_write_back_failure_keeps_pending_and_reprompts(self, tmp_path: Path) -> None:
        """Regression G0085: failed already-widened local resolve leaves pending."""
        import typer

        store, entry = self._make_store_with_entry(tmp_path)
        console = _capture_console()
        mock_dm = MagicMock()
        mock_dm.resolve_decision.side_effect = _make_decision_error()
        inputs = iter(["PostgreSQL", "!cancel"])

        with (
            patch.object(console, "input", side_effect=lambda _prompt="": next(inputs)),
            pytest.raises(typer.Exit),
        ):
            render_already_widened_prompt(
                question_text="Which database?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=MagicMock(),
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id
        output = _console_output(console).lower()
        assert "not saved" in output
        assert "resolved locally" not in output

    def test_defer_path(self, tmp_path: Path) -> None:
        """d input → defer_decision called, entry removed."""
        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)
        mock_dm = MagicMock()

        # First input: "d"; second input (rationale prompt): ""
        inputs_iter = iter(["d", ""])

        with patch.object(console, "input", side_effect=inputs_iter), \
             patch.object(console, "print"):
            render_already_widened_prompt(
                question_text="Tech stack?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=MagicMock(),
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        mock_dm.defer_decision.assert_called_once()
        assert store.list_pending() == []

    def test_defer_write_back_failure_keeps_pending_and_reprompts(self, tmp_path: Path) -> None:
        """Regression G0085: failed already-widened direct defer leaves pending."""
        import typer

        store, entry = self._make_store_with_entry(tmp_path)
        console = _capture_console()
        mock_dm = MagicMock()
        mock_dm.defer_decision.side_effect = _make_decision_error()
        inputs_iter = iter(["d", "not ready", "!cancel"])

        with (
            patch.object(console, "input", side_effect=inputs_iter),
            pytest.raises(typer.Exit),
        ):
            render_already_widened_prompt(
                question_text="Tech stack?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=MagicMock(),
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id
        output = _console_output(console).lower()
        assert "not saved" in output
        assert "decision deferred" not in output

    def test_fetch_path(self, tmp_path: Path) -> None:
        """f input → fetch + run_candidate_review, entry removed."""
        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)
        mock_dm = MagicMock()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=["Alice"], message_count=1,
            thread_url="https://slack.com/abc", messages=["Use PG"], truncated=False,
        )

        mock_review = MagicMock(return_value=object())
        with patch.object(console, "input", return_value="f"), \
             patch.object(console, "print"), \
             patch("specify_cli.widen.review.run_candidate_review", mock_review):
            render_already_widened_prompt(
                question_text="DB choice?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=mock_saas,
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        mock_review.assert_called_once()
        assert store.list_pending() == []

    def test_fetch_path_keeps_pending_on_review_exception(self, tmp_path: Path) -> None:
        """Regression G0085: already-widened fetch crash leaves pending entry retryable."""
        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)
        mock_dm = MagicMock()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=["Alice"], message_count=1,
            thread_url="https://slack.com/abc", messages=["Use PG"], truncated=False,
        )

        with patch.object(console, "input", return_value="f"), \
             patch.object(console, "print"), \
             patch(
                 "specify_cli.widen.review.run_candidate_review",
                 side_effect=RuntimeError("review crash"),
             ), \
             pytest.raises(RuntimeError, match="review crash"):
            render_already_widened_prompt(
                question_text="DB choice?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=mock_saas,
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id

    def test_fetch_path_keeps_pending_when_review_is_cancelled(self, tmp_path: Path) -> None:
        """A non-terminal already-widened review cancellation leaves pending state retryable."""
        import typer

        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)
        mock_dm = MagicMock()

        from specify_cli.widen.models import DiscussionFetch

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.return_value = DiscussionFetch(
            participants=["Alice"], message_count=1,
            thread_url="https://slack.com/abc", messages=["Use PG"], truncated=False,
        )

        inputs_iter = iter(["f", "!cancel"])

        with patch.object(console, "input", side_effect=inputs_iter), \
             patch.object(console, "print"), \
             patch(
                 "specify_cli.widen.review.run_candidate_review",
                 MagicMock(return_value=None),
             ), \
             pytest.raises(typer.Exit):
            render_already_widened_prompt(
                question_text="DB choice?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=mock_saas,
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        pending = store.list_pending()
        assert len(pending) == 1
        assert pending[0].decision_id == entry.decision_id

    def test_cancel_raises_exit(self, tmp_path: Path) -> None:
        """!cancel → typer.Exit raised."""
        import typer

        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)

        with patch.object(console, "input", return_value="!cancel"), \
             patch.object(console, "print"), \
             pytest.raises(typer.Exit):
            render_already_widened_prompt(
                    question_text="Any question?",
                    decision_id="dec-001",
                    mission_slug=MISSION_SLUG,
                    repo_root=tmp_path,
                    saas_client=MagicMock(),
                    widen_store=store,
                    dm_service=MagicMock(),
                    actor="test",
                    console=console,
                )

    def test_empty_input_reshows_hint(self, tmp_path: Path) -> None:
        """Empty input → hint re-shown; second input resolves."""
        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)
        mock_dm = MagicMock()

        # First input: "" (empty), second: "my answer"
        inputs_iter = iter(["", "my answer"])
        print_calls: list[Any] = []

        with patch.object(console, "input", side_effect=inputs_iter), \
             patch.object(console, "print", side_effect=lambda *a, **kw: print_calls.append(a)):
            render_already_widened_prompt(
                question_text="Q?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=MagicMock(),
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        mock_dm.resolve_decision.assert_called_once()
        assert store.list_pending() == []

    def test_fetch_failure_falls_back(self, tmp_path: Path) -> None:
        """f path with fetch failure → fallback discussion, review still called."""
        from specify_cli.saas_client import SaasClientError

        store, entry = self._make_store_with_entry(tmp_path)
        console = Console(highlight=False, markup=False)
        mock_dm = MagicMock()

        mock_saas = MagicMock()
        mock_saas.fetch_discussion.side_effect = SaasClientError("net error")

        mock_review = MagicMock(return_value=object())
        with patch.object(console, "input", return_value="f"), \
             patch.object(console, "print"), \
             patch("specify_cli.widen.review.run_candidate_review", mock_review):
            render_already_widened_prompt(
                question_text="DB?",
                decision_id="dec-001",
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                saas_client=mock_saas,
                widen_store=store,
                dm_service=mock_dm,
                actor="test",
                console=console,
            )

        mock_review.assert_called_once()
        # Fallback discussion has 0 messages
        discussion = mock_review.call_args.kwargs.get("discussion_data") or mock_review.call_args.args[0]
        assert discussion.message_count == 0
        assert store.list_pending() == []


# ---------------------------------------------------------------------------
# Charter interview integration — end-of-interview pass
# ---------------------------------------------------------------------------


class TestCharterEndOfInterviewPendingPass:
    """Integration: charter interview command invokes end-of-interview pass."""

    def _setup_repo(self, tmp_path: Path) -> Path:
        kittify = tmp_path / ".kittify"
        kittify.mkdir(parents=True, exist_ok=True)
        (kittify / "charter" / "interview").mkdir(parents=True, exist_ok=True)
        mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "meta.json").write_text(
            json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
            encoding="utf-8",
        )
        return tmp_path

    def test_pending_pass_not_called_when_widen_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without SAAS token, widen_store is None → pending pass never runs."""
        from charter.activation.interview import MINIMAL_QUESTION_ORDER
        from typer.testing import CliRunner

        from specify_cli.cli.commands.charter import app as charter_app

        self._setup_repo(tmp_path)
        n_questions = len(MINIMAL_QUESTION_ORDER)
        inputs = "\n".join([""] * n_questions + [""] * 3) + "\n"

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(
            charter_app,
            ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
            input=inputs,
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        # No "Pending Widened Questions" panel since widen is disabled
        assert "Pending Widened Questions" not in result.output

    def test_pending_pass_called_when_widen_enabled_and_store_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Widen enabled + empty store → interview completes without pending panel."""
        from charter.activation.interview import MINIMAL_QUESTION_ORDER
        from typer.testing import CliRunner

        from specify_cli.cli.commands.charter import app as charter_app
        from specify_cli.widen.models import PrereqState

        self._setup_repo(tmp_path)
        n_questions = len(MINIMAL_QUESTION_ORDER)
        inputs = "\n".join([""] * n_questions + [""] * 3) + "\n"

        prereq_ok = PrereqState(teamspace_ok=True, slack_ok=True, saas_reachable=True)

        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        with (
            patch("specify_cli.saas_client.client.SaasClient.from_env", return_value=MagicMock(_token="tok")),
            patch("specify_cli.widen.check_prereqs", return_value=prereq_ok),
            patch("specify_cli.widen.flow.WidenFlow", return_value=MagicMock()),
            patch("specify_cli.widen.state.WidenPendingStore") as mock_store_cls,
        ):
            mock_store = MagicMock()
            mock_store.list_pending.return_value = []
            mock_store_cls.return_value = mock_store

            result = runner.invoke(
                charter_app,
                ["interview", "--profile", "minimal", "--mission-slug", MISSION_SLUG],
                input=inputs,
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        # run_end_of_interview_pending_pass is called but returns silently (empty store)
        assert "Pending Widened Questions" not in result.output
