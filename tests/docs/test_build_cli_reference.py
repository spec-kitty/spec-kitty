"""Tests for ``scripts/docs/build_cli_reference.py`` and the Typer walker.

Coverage focuses on:

* The walker traverses a synthetic Typer app and emits deterministic entries.
* ANSI / whitespace normalization is correct.
* Each rendering mode (generated / hybrid / hand) produces the right shape.
* The integration smoke test on the real ``specify_cli.app`` lives in
  ``tests/architectural/test_docs_cli_reference_parity.py``; this module
  asserts only the visible-count tolerance from the synthetic walk.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer

from scripts.docs import build_cli_reference as build
from scripts.docs._typer_walker import CommandPathEntry, walk

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture(autouse=True)
def _pin_no_upgrade_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the upgrade-check opt-out set for every test (was a module-level ``setdefault``).

    ``build_cli_reference`` itself sets this env var at its own import time
    (SC-critical ordering it owns), so this fixture only preserves the
    test-local guarantee for tests that read the variable directly — it no
    longer needs to run before any import.
    """
    monkeypatch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", os.environ.get("SPEC_KITTY_NO_UPGRADE_CHECK", "1"))


# ---------------------------------------------------------------------------
# Synthetic Typer app fixture
# ---------------------------------------------------------------------------


def _make_synthetic_app() -> typer.Typer:
    """Build a tiny Typer app that exercises the walker rules."""
    app = typer.Typer()

    @app.command("foo", help="Run the foo command")
    def foo_cmd() -> None: ...

    @app.command("legacy-cmd", help="Deprecated: replaced by foo", deprecated=True)
    def legacy_cmd() -> None: ...

    @app.command("internal-only", help="Internal - dev-only helper", hidden=True)
    def internal_cmd() -> None: ...

    bar_app = typer.Typer()

    @bar_app.command("baz", help="Baz of bar")
    def baz_cmd() -> None: ...

    @bar_app.command("qux", help="Qux of bar")
    def qux_cmd() -> None: ...

    app.add_typer(bar_app, name="bar", help="Bar subcommand")

    tracker_app = typer.Typer()

    @tracker_app.command("list", help="List tracker items")
    def tracker_list() -> None: ...

    app.add_typer(tracker_app, name="tracker", help="Tracker root")

    @app.command("issue-search", help="Search issues")
    def issue_search() -> None: ...

    return app


@pytest.fixture()
def synthetic_app() -> typer.Typer:
    return _make_synthetic_app()


# ---------------------------------------------------------------------------
# Walker tests
# ---------------------------------------------------------------------------


class TestWalker:
    def test_walk_returns_deterministic_sorted_entries(self, synthetic_app: typer.Typer) -> None:
        first = walk(synthetic_app)
        second = walk(synthetic_app)
        assert first == second
        paths = [e.path for e in first]
        assert paths == sorted(paths)

    def test_walk_detects_visible_commands(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        visible = {e.path for e in entries if not e.hidden}
        assert ("foo",) in visible
        assert ("legacy-cmd",) in visible
        assert ("bar",) in visible
        assert ("bar", "baz") in visible
        assert ("bar", "qux") in visible
        assert ("tracker",) in visible
        assert ("tracker", "list") in visible
        assert ("issue-search",) in visible

    def test_walk_detects_hidden(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        hidden = [e for e in entries if e.hidden]
        assert any(e.path == ("internal-only",) for e in hidden)

    def test_walk_detects_deprecated_flag(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        deprecated = [e for e in entries if e.deprecated]
        assert any(e.path == ("legacy-cmd",) for e in deprecated)

    def test_walk_detects_deprecated_by_help_prefix(self) -> None:
        """A command whose help starts with 'Deprecated' is flagged."""
        app = typer.Typer()

        @app.command("old", help="Deprecated: legacy")
        def old_cmd() -> None: ...

        entries = walk(app)
        old = next(e for e in entries if e.path == ("old",))
        assert old.deprecated is True

    def test_walk_tags_saas_sync_paths(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        saas_paths = {e.path for e in entries if e.requires_saas_sync}
        assert ("tracker",) in saas_paths
        assert ("tracker", "list") in saas_paths
        assert ("issue-search",) in saas_paths
        # Non-saas
        assert ("foo",) not in saas_paths

    def test_walk_emits_kind_field(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        kinds = {e.path: e.kind for e in entries}
        assert kinds[("foo",)] == "command"
        assert kinds[("bar",)] == "group"
        assert kinds[("bar", "baz")] == "command"
        assert kinds[("tracker",)] == "group"

    def test_walk_records_help_summary(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        foo = next(e for e in entries if e.path == ("foo",))
        assert foo.help_summary == "Run the foo command"

    def test_walk_records_full_callback_docstring_when_help_is_inferred(self) -> None:
        app = typer.Typer()

        @app.command("body-only")
        def body_only() -> None:
            """Summary stays stable.

            This second paragraph is part of the full help body.
            """

        entry = next(e for e in walk(app) if e.path == ("body-only",))

        assert entry.help_summary == ""
        assert entry.help_body == ("Summary stays stable.\n\nThis second paragraph is part of the full help body.")

    def test_walk_normalizes_inferred_command_name_like_typer(self) -> None:
        app = typer.Typer()

        @app.command()
        def inferred_name() -> None: ...

        assert [entry.path for entry in walk(app)] == [("inferred-name",)]

    def test_walk_records_source_metadata(self, synthetic_app: typer.Typer) -> None:
        entries = walk(synthetic_app)
        foo = next(e for e in entries if e.path == ("foo",))
        assert foo.source_file is not None
        assert foo.source_function and foo.source_function.endswith("foo_cmd")

    def test_walk_skips_commands_without_name(self) -> None:
        app = typer.Typer()
        # Don't add anything; ensure walk returns []
        assert walk(app) == []

    def test_walk_dedupes_repeated_registration(self) -> None:
        """If the same sub-typer is re-added, the walker dedupes."""
        sub = typer.Typer()

        @sub.command("ping", help="Ping")
        def ping() -> None: ...

        app = typer.Typer()
        app.add_typer(sub, name="net")
        app.add_typer(sub, name="net")  # duplicate registration

        entries = walk(app)
        paths = [e.path for e in entries]
        assert paths.count(("net",)) == 1
        assert paths.count(("net", "ping")) == 1


# ---------------------------------------------------------------------------
# Normalization tests
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_strip_ansi_removes_csi(self) -> None:
        text = "\x1b[31mred\x1b[0m text"
        assert build.strip_ansi(text) == "red text"

    def test_strip_ansi_removes_osc(self) -> None:
        text = "\x1b]0;title\x07hello"
        assert build.strip_ansi(text) == "hello"

    def test_normalize_collapses_blank_lines(self) -> None:
        text = "line1\n\n\n\nline2\n"
        assert build.normalize_help_text(text) == "line1\n\nline2\n"

    def test_normalize_strips_trailing_whitespace(self) -> None:
        text = "alpha   \nbeta\t\n"
        assert build.normalize_help_text(text) == "alpha\nbeta\n"

    def test_normalize_strips_leading_and_trailing_blank_lines(self) -> None:
        text = "\n\nhello\nworld\n\n\n"
        assert build.normalize_help_text(text) == "hello\nworld\n"

    def test_normalize_empty_yields_empty(self) -> None:
        assert build.normalize_help_text("") == ""
        assert build.normalize_help_text("\n\n\n") == ""


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------


class TestRendering:
    def _entry(
        self,
        *,
        path: tuple[str, ...] = ("foo",),
        deprecated: bool = False,
        hidden: bool = False,
        summary: str = "Foo help",
    ) -> CommandPathEntry:
        return CommandPathEntry(
            path=path,
            kind="command",
            hidden=hidden,
            deprecated=deprecated,
            help_summary=summary,
            source_file=None,
            source_function=None,
            requires_saas_sync=False,
        )

    def test_render_section_emits_title(self) -> None:
        entry = self._entry()
        section = build.render_section(entry, "Usage: spec-kitty foo")
        assert section.body.startswith("## spec-kitty foo\n")
        assert "Usage: spec-kitty foo" in section.body

    def test_render_section_emits_deprecated_banner(self) -> None:
        entry = self._entry(deprecated=True, summary="Deprecated: use bar")
        section = build.render_section(entry, "Usage: spec-kitty foo")
        assert "> **Deprecated**:" in section.body

    def test_render_section_emits_internal_banner_for_hidden_command(self) -> None:
        entry = self._entry(hidden=True)
        section = build.render_section(entry, "Usage: spec-kitty foo")
        assert "> **Internal**:" in section.body

    def test_render_section_emits_summary_for_non_deprecated(self) -> None:
        entry = self._entry()
        section = build.render_section(entry, "X")
        assert "_Foo help_" in section.body

    def test_render_document_concatenates(self) -> None:
        sections = [
            build.render_section(self._entry(path=("a",)), "X"),
            build.render_section(self._entry(path=("b",)), "Y"),
        ]
        doc = build.render_document(sections, title="My Ref")
        assert doc.startswith("# My Ref\n")
        assert "## spec-kitty a" in doc
        assert "## spec-kitty b" in doc

    def test_render_document_with_hidden_appendix(self) -> None:
        hidden = [build.render_section(self._entry(path=("h",), hidden=True), "Z")]
        doc = build.render_document([], title="X", include_hidden_sections=hidden)
        assert "Internal / hidden commands" in doc
        assert "## spec-kitty h" in doc

    def test_wrap_with_markers_creates_new_block(self) -> None:
        result = build.wrap_with_markers("inner", existing=None)
        assert build.BEGIN_MARKER in result
        assert build.END_MARKER in result
        assert "inner" in result

    def test_wrap_with_markers_splices_existing(self) -> None:
        existing = f"# Title\n\nIntro prose\n\n{build.BEGIN_MARKER}\nold generated\n{build.END_MARKER}\n\nOutro prose\n"
        result = build.wrap_with_markers("NEW BLOCK", existing=existing)
        assert "Intro prose" in result
        assert "Outro prose" in result
        assert "NEW BLOCK" in result
        assert "old generated" not in result

    def test_wrap_with_markers_appends_when_no_envelope(self) -> None:
        existing = "# Title\n\nIntro prose only\n"
        result = build.wrap_with_markers("NEW", existing=existing)
        assert "Intro prose only" in result
        assert "NEW" in result
        assert build.BEGIN_MARKER in result


# ---------------------------------------------------------------------------
# Path partitioning
# ---------------------------------------------------------------------------


class TestPartition:
    def _entry(self, path: tuple[str, ...], *, hidden: bool = False) -> CommandPathEntry:
        return CommandPathEntry(
            path=path,
            kind="command",
            hidden=hidden,
            deprecated=False,
            help_summary="x",
            source_file=None,
            source_function=None,
            requires_saas_sync=False,
        )

    def test_partition_separates_agent_subtree(self) -> None:
        entries = [
            self._entry(("foo",)),
            self._entry(("agent", "tasks")),
            self._entry(("agent", "config", "list")),
            self._entry(("bar", "baz")),
        ]
        main, agents, hidden = build.partition_paths(entries, include_hidden=False)
        assert all(e.path[0] != "agent" for e in main)
        assert all(e.path[0] == "agent" for e in agents)
        assert hidden == []

    def test_partition_excludes_hidden_by_default(self) -> None:
        entries = [
            self._entry(("foo",)),
            self._entry(("inner",), hidden=True),
        ]
        main, _, hidden = build.partition_paths(entries, include_hidden=False)
        assert all(not e.hidden for e in main)
        assert hidden == []

    def test_partition_includes_hidden_when_requested(self) -> None:
        entries = [self._entry(("inner",), hidden=True)]
        main, _, hidden = build.partition_paths(entries, include_hidden=True)
        assert main == []
        assert frozenset(e.path for e in hidden) == frozenset({("inner",)})


# ---------------------------------------------------------------------------
# Builder CLI invocation
# ---------------------------------------------------------------------------


class TestBuildCli:
    """End-to-end tests of ``main()`` against a stubbed Typer app."""

    @pytest.fixture()
    def stub_specify_cli(self, monkeypatch: pytest.MonkeyPatch, synthetic_app: typer.Typer) -> Iterator[None]:
        """Substitute the live ``specify_cli`` import with the synthetic app."""

        import types

        fake_specify = types.ModuleType("specify_cli")
        fake_specify.app = synthetic_app  # type: ignore[attr-defined]

        fake_cmds = types.ModuleType("specify_cli.cli.commands")

        def register_commands(_app: typer.Typer) -> None:
            return None

        fake_cmds.register_commands = register_commands  # type: ignore[attr-defined]

        # Build out the parent packages so the dotted import resolves.
        fake_cli = types.ModuleType("specify_cli.cli")
        monkeypatch.setitem(__import__("sys").modules, "specify_cli", fake_specify)
        monkeypatch.setitem(__import__("sys").modules, "specify_cli.cli", fake_cli)
        monkeypatch.setitem(
            __import__("sys").modules,
            "specify_cli.cli.commands",
            fake_cmds,
        )
        yield

    def test_main_writes_to_output_in_generated_mode(
        self,
        tmp_path: Path,
        stub_specify_cli: None,
    ) -> None:
        out = tmp_path / "cli-commands.md"
        agent_out = tmp_path / "agent-subcommands.md"
        rc = build.main(
            [
                "--output",
                str(out),
                "--agent-output",
                str(agent_out),
                "--mode",
                "generated",
                "--repo-root",
                str(tmp_path),
                "--skip-help-capture",
            ]
        )
        assert rc == 0
        text = out.read_text(encoding="utf-8")
        assert "# CLI Command Reference" in text
        assert "## spec-kitty foo" in text
        assert "## spec-kitty bar" in text
        # Agent output should be present (synthetic app has no agent subtree)
        assert agent_out.exists()

    def test_main_writes_hybrid_preserves_outside_prose(
        self,
        tmp_path: Path,
        stub_specify_cli: None,
    ) -> None:
        out = tmp_path / "cli.md"
        agent_out = tmp_path / "agent.md"
        out.write_text(
            f"# Existing\n\nHand prose\n\n{build.BEGIN_MARKER}\nold\n{build.END_MARKER}\n\nOutro\n",
            encoding="utf-8",
        )
        rc = build.main(
            [
                "--output",
                str(out),
                "--agent-output",
                str(agent_out),
                "--mode",
                "hybrid",
                "--repo-root",
                str(tmp_path),
                "--skip-help-capture",
                "--force",
            ]
        )
        assert rc == 0
        text = out.read_text(encoding="utf-8")
        assert "Hand prose" in text
        assert "Outro" in text
        assert "## spec-kitty foo" in text
        assert "old" not in text

    def test_main_hand_mode_writes_classification_table(
        self,
        tmp_path: Path,
        stub_specify_cli: None,
    ) -> None:
        out = tmp_path / "cli.md"
        agent_out = tmp_path / "agent.md"
        rc = build.main(
            [
                "--output",
                str(out),
                "--agent-output",
                str(agent_out),
                "--mode",
                "hand",
                "--repo-root",
                str(tmp_path),
                "--skip-help-capture",
                "--include-hidden",
            ]
        )
        assert rc == 0
        text = out.read_text(encoding="utf-8")
        assert "Classification table" in text
        assert "deprecated" in text

    def test_main_refuses_env_flag_off(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        stub_specify_cli: None,
    ) -> None:
        monkeypatch.setitem(os.environ, "SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
        rc = build.main(
            [
                "--output",
                str(tmp_path / "a.md"),
                "--agent-output",
                str(tmp_path / "b.md"),
                "--repo-root",
                str(tmp_path),
                "--skip-help-capture",
            ]
        )
        assert rc == 3

    def test_main_dry_run_does_not_write(
        self,
        tmp_path: Path,
        stub_specify_cli: None,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        out = tmp_path / "cli.md"
        agent_out = tmp_path / "agent.md"
        rc = build.main(
            [
                "--output",
                str(out),
                "--agent-output",
                str(agent_out),
                "--mode",
                "generated",
                "--dry-run",
                "--repo-root",
                str(tmp_path),
                "--skip-help-capture",
            ]
        )
        assert rc == 0
        assert not out.exists()
        captured = capsys.readouterr()
        assert "## spec-kitty foo" in captured.out


# ---------------------------------------------------------------------------
# capture_help uses subprocess; smoke-test the wrapper with mocked subprocess.
# ---------------------------------------------------------------------------


class TestCaptureHelp:
    def test_capture_help_calls_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, Any] = {}

        class _Result:
            stdout = "Usage: spec-kitty foo [OPTIONS]\n"

        def _fake_run(cmd: list[str], **kwargs: object) -> _Result:
            captured["cmd"] = cmd
            captured["env"] = kwargs.get("env")
            return _Result()

        monkeypatch.setattr(build.subprocess, "run", _fake_run)
        result = build.capture_help(("foo",))
        assert "Usage: spec-kitty foo" in result
        assert captured["cmd"][-1] == "--help"
        env = captured["env"]
        assert isinstance(env, dict)
        assert env["SPEC_KITTY_ENABLE_SAAS_SYNC"] == "1"


# ---------------------------------------------------------------------------
# Dirty-target detection
# ---------------------------------------------------------------------------


class TestDirtyTarget:
    def test_is_dirty_returns_false_when_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "absent.md"
        assert build.is_target_dirty(target, repo_root=tmp_path) is False

    def test_is_dirty_handles_git_failure_gracefully(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exists.md"
        target.write_text("content", encoding="utf-8")

        def _raise(*args: object, **kwargs: object) -> object:
            raise OSError("git not found")

        monkeypatch.setattr(build.subprocess, "run", _raise)
        assert build.is_target_dirty(target, repo_root=tmp_path) is False

    def test_is_dirty_returns_true_when_git_reports_changes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "exists.md"
        target.write_text("content", encoding="utf-8")

        class _Result:
            stdout = " M docs/file.md\n"

        monkeypatch.setattr(build.subprocess, "run", lambda *a, **kw: _Result())
        assert build.is_target_dirty(target, repo_root=tmp_path) is True
