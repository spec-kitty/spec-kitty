"""Unit tests for the Claude Code plugin runtime bootstrap wrapper (WP05).

Covers:
    - write_wrappers creates bin/spec-kitty-wrapper (bash) and .cmd (Windows)
    - Version placeholder is substituted with the real version
    - bash wrapper is executable (mode 700)
    - wrapper_bash_content / wrapper_cmd_content helper functions
    - Empty version raises ValueError
    - Wrappers are idempotent (second call overwrites cleanly)
    - Wrapper content contains PATH-check and uvx-fallback logic
    - marketplace.json is written by ClaudeBundleProjector.build()
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.tool_surface.bundles.claude_wrapper import (
    supported_series,
    uvx_requirements,
    write_wrappers,
    wrapper_bash_content,
    wrapper_cmd_content,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# write_wrappers — filesystem tests
# ---------------------------------------------------------------------------


class TestWriteWrappers:
    def test_creates_bash_wrapper(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        assert (tmp_path / "bin" / "spec-kitty-wrapper").is_file()

    def test_creates_cmd_wrapper(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        assert (tmp_path / "bin" / "spec-kitty-wrapper.cmd").is_file()

    def test_creates_bin_dir(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path / "bundle", "1.0.0")
        assert (tmp_path / "bundle" / "bin").is_dir()

    def test_bash_version_substituted(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        content = (tmp_path / "bin" / "spec-kitty-wrapper").read_text(encoding="utf-8")
        assert "3.2.0" in content
        assert "__SPEC_KITTY_VERSION__" not in content

    def test_cmd_version_substituted(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        content = (tmp_path / "bin" / "spec-kitty-wrapper.cmd").read_text(encoding="utf-8")
        assert "3.2.0" in content
        assert "__SPEC_KITTY_VERSION__" not in content

    def test_bash_wrapper_is_executable(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        bash_path = tmp_path / "bin" / "spec-kitty-wrapper"
        mode = os.stat(bash_path).st_mode
        # Must be executable by owner (user bit).
        assert mode & stat.S_IXUSR, "bash wrapper must be owner-executable"
        # Must not grant execute access outside the current user.
        assert not (mode & stat.S_IXGRP), "bash wrapper must not be group-executable"
        assert not (mode & stat.S_IXOTH), "bash wrapper must not be world-executable"

    def test_raises_on_empty_version(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            write_wrappers(tmp_path, "")

    def test_retained_wrapper_apply_does_not_render(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.tool_surface.bundles import claude_wrapper

        def forbidden(*args: object, **kwargs: object) -> str:
            raise AssertionError("Retained wrapper rendered again")

        monkeypatch.setattr(claude_wrapper, "wrapper_bash_content", forbidden)
        monkeypatch.setattr(claude_wrapper, "wrapper_cmd_content", forbidden)
        (tmp_path / "bin").mkdir()
        path = tmp_path / "bin/spec-kitty-wrapper"
        write_wrappers(tmp_path, prepared=(path, b"retained bytes", 0o700))
        assert path.read_bytes() == b"retained bytes"
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        with pytest.raises(ValueError, match="outside the wrapper layout"):
            write_wrappers(tmp_path, prepared=(tmp_path / "other", b"invalid", 0o644))

    def test_idempotent_second_write(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        first = (tmp_path / "bin" / "spec-kitty-wrapper").read_bytes()
        write_wrappers(tmp_path, "3.2.0")
        second = (tmp_path / "bin" / "spec-kitty-wrapper").read_bytes()
        assert first == second

    def test_second_write_replaces_broad_existing_permissions(self, tmp_path: Path) -> None:
        write_wrappers(tmp_path, "3.2.0")
        bash_path = tmp_path / "bin" / "spec-kitty-wrapper"
        os.chmod(bash_path, 0o755)

        write_wrappers(tmp_path, "3.2.0")

        mode = os.stat(bash_path).st_mode
        assert mode & stat.S_IXUSR
        assert not (mode & stat.S_IXGRP)
        assert not (mode & stat.S_IXOTH)


# ---------------------------------------------------------------------------
# wrapper content helpers (pure, no I/O)
# ---------------------------------------------------------------------------


class TestWrapperBashContent:
    def test_contains_shebang(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert content.startswith("#!/usr/bin/env bash")

    def test_version_present(self) -> None:
        content = wrapper_bash_content("2.5.3")
        assert "2.5.3" in content

    def test_series_present_next_to_the_version(self) -> None:
        """The rendered script carries the series its PATH gate compares to."""
        content = wrapper_bash_content("2.5.3")
        assert 'SERIES="2.5"' in content

    def test_path_check_present(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert "command -v spec-kitty" in content

    def test_path_probe_reads_the_installed_version(self) -> None:
        """A PATH hit is only usable when its version can be read (#497)."""
        content = wrapper_bash_content("1.0.0")
        assert 'installed="$(spec-kitty --version 2>/dev/null || true)"' in content

    def test_path_cli_must_match_the_bundle_series(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert 'SERIES="1.0"' in content
        assert '[ "$installed_series" = "$SERIES" ]' in content

    def test_uvx_fallback_uses_from(self) -> None:
        """The fallback must name the executable, not just the distribution.

        ``uvx spec-kitty-cli==<version>`` runs an executable named after the
        distribution; the distribution ships only ``spec-kitty``, so uvx exits
        1 without running anything (#6476).
        """
        content = wrapper_bash_content("1.0.0")
        assert "command -v uvx" in content
        assert 'uvx --from "$from_spec" spec-kitty "$@"' in content
        assert 'uvx "spec-kitty-cli' not in content
        assert "uvx spec-kitty-cli" not in content

    def test_uvx_requirements_carry_pin_and_series_range(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert 'PINNED_SPEC="spec-kitty-cli==1.0.0"' in content
        assert 'SERIES_SPEC="spec-kitty-cli>=1.0.0,<1.1"' in content

    def test_error_message_present(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert "uv tool install spec-kitty-cli" in content
        assert "pipx install spec-kitty-cli" in content
        assert "pip install spec-kitty-cli" not in content

    def test_exec_delegates_to_spec_kitty(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert 'exec spec-kitty "$@"' in content

    def test_set_euo_pipefail(self) -> None:
        content = wrapper_bash_content("1.0.0")
        assert "set -euo pipefail" in content


class TestWrapperCmdContent:
    def test_starts_with_echo_off(self) -> None:
        content = wrapper_cmd_content("1.0.0")
        assert content.startswith("@echo off")

    def test_version_present(self) -> None:
        content = wrapper_cmd_content("2.5.3")
        assert "2.5.3" in content

    def test_where_spec_kitty_check(self) -> None:
        content = wrapper_cmd_content("1.0.0")
        assert "where spec-kitty" in content

    def test_path_probe_reads_the_installed_version(self) -> None:
        content = wrapper_cmd_content("1.0.0")
        assert "spec-kitty --version" in content
        assert 'findstr /C:" %SERIES%."' in content

    def test_path_cli_must_match_the_bundle_series(self) -> None:
        content = wrapper_cmd_content("1.0.0")
        assert 'SET "SERIES=1.0"' in content

    def test_uvx_fallback_uses_from(self) -> None:
        """Both wrappers must name the executable the distribution ships."""
        content = wrapper_cmd_content("1.0.0")
        assert "where uvx" in content
        assert 'uvx --from "%PINNED_SPEC%" spec-kitty %*' in content
        assert "uvx spec-kitty-cli" not in content

    def test_series_range_requirement_is_quoted(self) -> None:
        """`>` and `<` are cmd.exe redirection operators, so quote the range."""
        content = wrapper_cmd_content("1.0.0")
        assert 'SET "SERIES_SPEC=spec-kitty-cli>=1.0.0,<1.1"' in content
        assert 'uvx --from "%SERIES_SPEC%" spec-kitty %*' in content

    def test_error_message_present(self) -> None:
        content = wrapper_cmd_content("1.0.0")
        assert "uv tool install spec-kitty-cli" in content
        assert "pip install spec-kitty-cli" not in content

    def test_percent_star_argument_forwarding(self) -> None:
        """Windows CMD uses %* to forward arguments."""
        content = wrapper_cmd_content("1.0.0")
        assert "%*" in content

    def test_exit_b_errorlevel_not_inside_parenthesized_block(self) -> None:
        """EXIT /B %ERRORLEVEL% must never be nested inside `IF ... ( ... )`.

        cmd.exe expands %VAR% in a parenthesized compound statement at parse
        time, so an EXIT /B %ERRORLEVEL% written inside one always reports the
        errorlevel current when the block was entered (the preceding `where`
        probe's 0) rather than the real exit code of the delegated command.
        """
        content = wrapper_cmd_content("1.0.0")
        lines = content.splitlines()
        depth = 0
        for line in lines:
            stripped = line.strip()
            if "EXIT /B %ERRORLEVEL%" in stripped:
                assert depth == 0, f"EXIT /B %ERRORLEVEL% is nested inside a parenthesized block (depth={depth}): {stripped!r}"
            depth += stripped.count("(") - stripped.count(")")

    def test_no_parenthesized_if_blocks(self) -> None:
        """The wrapper uses GOTO, not `IF ... ( ... )`, around EXIT /B.

        A parenthesized IF block is exactly the construct that causes
        cmd.exe's parse-time %ERRORLEVEL% expansion bug; asserting it is
        gone (rather than only asserting EXIT /B's depth above) prevents a
        future edit from reintroducing it around some other guarded exit.
        """
        content = wrapper_cmd_content("1.0.0")
        assert "IF NOT ERRORLEVEL 1 (" not in content
        assert ") (" not in content

    def test_goto_labels_defined_and_referenced(self) -> None:
        content = wrapper_cmd_content("1.0.0")
        assert "GOTO try_pinned" in content
        assert ":try_pinned" in content
        assert "GOTO try_series" in content
        assert ":try_series" in content
        assert "GOTO no_runtime" in content
        assert ":no_runtime" in content


class TestVersionSeries:
    """One authority derives the supported series and the uvx requirements."""

    @pytest.mark.parametrize(
        ("version", "expected"),
        [
            ("4.0.0rc8", "4.0"),
            ("4.0.0", "4.0"),
            ("3.2.7", "3.2"),
            ("10.11.0.dev1", "10.11"),
        ],
    )
    def test_supported_series(self, version: str, expected: str) -> None:
        assert supported_series(version) == expected

    @pytest.mark.parametrize("version", ["", "unknown", "v4", "4"])
    def test_supported_series_is_none_when_unparseable(self, version: str) -> None:
        assert supported_series(version) is None

    def test_uvx_requirements_pin_then_series(self) -> None:
        assert uvx_requirements("4.0.0rc8") == (
            "spec-kitty-cli==4.0.0rc8",
            "spec-kitty-cli>=4.0.0rc8,<4.1",
        )

    def test_uvx_requirements_roll_the_minor_over(self) -> None:
        assert uvx_requirements("3.9.4")[1] == "spec-kitty-cli>=3.9.4,<3.10"

    def test_uvx_requirements_without_a_range_when_unparseable(self) -> None:
        assert uvx_requirements("unknown") == ("spec-kitty-cli==unknown", "")


def _stub(bin_dir: Path, name: str, body: str) -> Path:
    """Write an executable stub script into *bin_dir*."""
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _uvx_stub(bin_dir: Path, *, fail_exact_pin: bool = False) -> Path:
    """A `uvx` double that prints the argv it was handed.

    With *fail_exact_pin*, an exact `==` requirement exits 1 (the shape uv uses
    for an unpublished pin) while a range requirement resolves, so the test can
    observe the series-range retry.
    """
    guard = '\ncase "$2" in\n  *==*) exit 1 ;;\nesac' if fail_exact_pin else ""
    return _stub(bin_dir, "uvx", f"#!/bin/sh\nprintf 'uvx %s\\n' \"$*\"{guard}\n")


def _spec_kitty_stub(bin_dir: Path, version: str) -> Path:
    """A `spec-kitty` double that reports *version* and marks delegation."""
    return _stub(
        bin_dir,
        "spec-kitty",
        f'#!/bin/sh\nif [ "$1" = "--version" ]; then\n  printf \'spec-kitty-cli version {version}\\n\'\n  exit 0\nfi\nprintf \'PATH-CLI %s\\n\' "$*"\n',
    )


def _system_tools_dir(tmp_path: Path) -> Path:
    """A PATH entry holding only the POSIX tools the wrapper needs (`awk`).

    Building it here keeps the runtime tests hermetic: no directory that could
    hold a real `spec-kitty` or `uvx` is ever on the wrapper's PATH, so a test
    cannot pass (or fail) because of what the developer machine has installed.
    """
    tools = tmp_path / "system-tools"
    tools.mkdir()
    awk = shutil.which("awk")
    assert awk is not None, "the wrapper's version probe needs awk"
    (tools / "awk").symlink_to(awk)
    return tools


def _run_bash_wrapper(tmp_path: Path, fake_bin: Path, *args: str) -> subprocess.CompletedProcess[str]:
    bash_path = shutil.which("bash")
    assert bash_path is not None
    path_dirs = [str(fake_bin), str(_system_tools_dir(tmp_path))]
    return subprocess.run(
        [bash_path, str(tmp_path / "bin" / "spec-kitty-wrapper"), *args],
        capture_output=True,
        text=True,
        env={"PATH": ":".join(path_dirs)},
    )


class TestWrapperRuntimeFallback:
    """Run the generated script, not only the helper that renders it."""

    def _bundle(self, tmp_path: Path, version: str = "9.9.9") -> Path:
        fake_bin = tmp_path / "fake-bin"
        fake_bin.mkdir()
        write_wrappers(tmp_path, version)
        return fake_bin

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_falls_back_to_pinned_uvx_when_no_cli_on_path(self, tmp_path: Path) -> None:
        fake_bin = self._bundle(tmp_path)
        _uvx_stub(fake_bin)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode == 0
        assert result.stdout == ("uvx --from spec-kitty-cli==9.9.9 spec-kitty mission list\n")

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_falls_back_to_uvx_when_path_shim_is_unreachable(self, tmp_path: Path) -> None:
        fake_bin = self._bundle(tmp_path)
        _stub(fake_bin, "spec-kitty", "#!/bin/sh\nexit 127\n")
        _uvx_stub(fake_bin)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode == 0
        assert result.stdout == ("uvx --from spec-kitty-cli==9.9.9 spec-kitty mission list\n")

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_retries_within_the_series_when_the_pin_is_unpublished(self, tmp_path: Path) -> None:
        fake_bin = self._bundle(tmp_path)
        _uvx_stub(fake_bin, fail_exact_pin=True)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode == 0
        assert result.stdout == ("uvx --from spec-kitty-cli>=9.9.9,<9.10 spec-kitty mission list\n")

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_prefers_path_cli_inside_the_supported_series(self, tmp_path: Path) -> None:
        fake_bin = self._bundle(tmp_path)
        _spec_kitty_stub(fake_bin, "9.9.3")
        _uvx_stub(fake_bin)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode == 0
        assert result.stdout == "PATH-CLI mission list\n"
        assert "uvx" not in result.stdout

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_uses_a_path_cli_that_prints_a_bare_version(self, tmp_path: Path) -> None:
        """A version line with no program-name prefix still matches the series.

        The Windows wrapper accepts both shapes, so the POSIX probe must too;
        `spec-kitty --version` prints a prefixed line today, but a wrapper or
        alias that prints a bare version must not silently fall back to uvx.
        """
        fake_bin = self._bundle(tmp_path)
        _stub(
            fake_bin,
            "spec-kitty",
            '#!/bin/sh\nif [ "$1" = "--version" ]; then\n  printf \'9.9.3\\n\'\n  exit 0\nfi\nprintf \'PATH-CLI %s\\n\' "$*"\n',
        )
        _uvx_stub(fake_bin)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode == 0
        assert result.stdout == "PATH-CLI mission list\n"

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_ignores_path_cli_from_another_series(self, tmp_path: Path) -> None:
        fake_bin = self._bundle(tmp_path)
        _spec_kitty_stub(fake_bin, "3.2.0")
        _uvx_stub(fake_bin)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode == 0
        assert "PATH-CLI" not in result.stdout
        assert result.stdout == ("uvx --from spec-kitty-cli==9.9.9 spec-kitty mission list\n")

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell wrapper")
    def test_bash_reports_the_uv_remedy_when_no_runtime_is_available(self, tmp_path: Path) -> None:
        fake_bin = self._bundle(tmp_path)

        result = _run_bash_wrapper(tmp_path, fake_bin, "mission", "list")

        assert result.returncode != 0
        assert "uv tool install spec-kitty-cli" in result.stderr
        assert "pip install spec-kitty-cli" not in result.stderr


# ---------------------------------------------------------------------------
# marketplace.json generation via ClaudeBundleProjector
# ---------------------------------------------------------------------------


class TestMarketplaceJson:
    def _run_build(self, tmp_path: Path) -> Path:
        from specify_cli.tool_surface.bundles.claude import ClaudeBundleProjector

        bundle_dir: Path = ClaudeBundleProjector(tmp_path / "dist").build(skip_validate=True)
        return bundle_dir

    def test_marketplace_json_exists(self, tmp_path: Path) -> None:
        self._run_build(tmp_path)
        assert (tmp_path / "dist" / "marketplace.json").is_file()

    def test_marketplace_json_schema(self, tmp_path: Path) -> None:
        self._run_build(tmp_path)
        payload = json.loads((tmp_path / "dist" / "marketplace.json").read_text(encoding="utf-8"))
        assert payload["name"] == "spec-kitty-plugins"
        assert payload.get("owner") == {"name": "Spec Kitty"}
        assert payload.get("description") == "Spec Kitty skills, agent profiles, and runtime wrappers for Claude Code."
        assert "interface" not in payload
        assert "plugins" in payload
        assert len(payload["plugins"]) == 1
        plugin = payload["plugins"][0]
        assert plugin["name"] == "spec-kitty"
        assert "policy" not in plugin
        assert plugin["source"]["source"] == "git-subdir"
        assert plugin["source"]["url"] == "https://github.com/spec-kitty/spec-kitty.git"

    def test_marketplace_json_not_inside_bundle(self, tmp_path: Path) -> None:
        """marketplace.json lives alongside the bundle dir, not inside it."""
        bundle_dir = self._run_build(tmp_path)
        # Must NOT appear inside the claude-code bundle directory.
        assert not (bundle_dir / "marketplace.json").exists()
        # Must appear one level up, in the output_dir.
        assert (bundle_dir.parent / "marketplace.json").is_file()


# ---------------------------------------------------------------------------
# Wrappers generated by ClaudeBundleProjector.build()
# ---------------------------------------------------------------------------


class TestBuildIncludesWrappers:
    def _run_build(self, tmp_path: Path) -> Path:
        from specify_cli.tool_surface.bundles.claude import ClaudeBundleProjector

        bundle_dir: Path = ClaudeBundleProjector(tmp_path / "dist").build(skip_validate=True)
        return bundle_dir

    def test_bash_wrapper_in_bundle(self, tmp_path: Path) -> None:
        bundle_dir = self._run_build(tmp_path)
        assert (bundle_dir / "bin" / "spec-kitty-wrapper").is_file()

    def test_cmd_wrapper_in_bundle(self, tmp_path: Path) -> None:
        bundle_dir = self._run_build(tmp_path)
        assert (bundle_dir / "bin" / "spec-kitty-wrapper.cmd").is_file()

    def test_wrapper_version_matches_plugin_json(self, tmp_path: Path) -> None:
        bundle_dir = self._run_build(tmp_path)
        plugin_json = json.loads((bundle_dir / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        assert plugin_json["author"] == {
            "name": "Spec Kitty",
            "url": "https://github.com/spec-kitty/spec-kitty",
        }
        version = plugin_json["version"]
        bash_content = (bundle_dir / "bin" / "spec-kitty-wrapper").read_text(encoding="utf-8")
        assert version in bash_content

    def test_build_is_still_idempotent_with_wrappers(self, tmp_path: Path) -> None:
        """Second build must produce byte-identical wrapper files."""
        projector_cls = __import__(
            "specify_cli.tool_surface.bundles.claude",
            fromlist=["ClaudeBundleProjector"],
        ).ClaudeBundleProjector
        projector = projector_cls(tmp_path / "dist")
        bd1 = projector.build(skip_validate=True)
        snap1 = {str(f.relative_to(bd1)): f.read_bytes() for f in sorted(bd1.rglob("*")) if f.is_file()}
        bd2 = projector.build(skip_validate=True)
        snap2 = {str(f.relative_to(bd2)): f.read_bytes() for f in sorted(bd2.rglob("*")) if f.is_file()}
        assert snap1 == snap2
