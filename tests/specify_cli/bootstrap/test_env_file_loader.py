"""Tests for ``specify_cli.bootstrap.env_file`` -- the pre-import ``.kitty.env``
two-tier loader + the single ``config.yaml`` ``env_file`` pointer.

Covers C-LDR-1..7 from ``contracts/kitty-env-loader.md`` (WP02 T006-T010).
Import-purity (C-LDR-6's "stdlib + kernel only" invariant) is covered
separately by ``tests/architectural/test_bootstrap_import_purity.py`` -- this
file covers the loader's *behaviour*.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

from specify_cli.bootstrap import env_file
from specify_cli.bootstrap.env_file import (
    OperatorEnvFileUnreadableError,
    load_operator_env_file,
    parse_env_file,
)
from kernel.paths import get_runtime_state_root

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[3]


# --------------------------------------------------------------------------- #
# T006: KEY=VALUE parser
# --------------------------------------------------------------------------- #


class TestParseEnvFile:
    """The hand-rolled ``KEY=VALUE`` parser -- stdlib-only, never raises."""

    def test_basic_key_value(self) -> None:
        assert parse_env_file("FOO=bar\n") == {"FOO": "bar"}

    def test_multiple_lines(self) -> None:
        text = "FOO=bar\nBAZ=qux\n"
        assert parse_env_file(text) == {"FOO": "bar", "BAZ": "qux"}

    def test_export_prefix_is_stripped(self) -> None:
        assert parse_env_file("export FOO=bar\n") == {"FOO": "bar"}

    def test_blank_lines_skipped(self) -> None:
        assert parse_env_file("\n\nFOO=bar\n\n") == {"FOO": "bar"}

    def test_full_line_comment_skipped(self) -> None:
        assert parse_env_file("# a comment\nFOO=bar\n") == {"FOO": "bar"}

    def test_indented_full_line_comment_skipped(self) -> None:
        assert parse_env_file("   # indented comment\nFOO=bar\n") == {"FOO": "bar"}

    def test_double_quotes_stripped(self) -> None:
        assert parse_env_file('FOO="bar baz"\n') == {"FOO": "bar baz"}

    def test_single_quotes_stripped(self) -> None:
        assert parse_env_file("FOO='bar baz'\n") == {"FOO": "bar baz"}

    def test_mismatched_quotes_not_stripped(self) -> None:
        assert parse_env_file("FOO='bar\n") == {"FOO": "'bar"}

    def test_value_is_literal_no_in_value_interpolation(self) -> None:
        """No ``${VAR}``/``$VAR`` expansion inside a value -- literal only."""
        assert parse_env_file("FOO=$HOME/x\n") == {"FOO": "$HOME/x"}
        assert parse_env_file("FOO=${BAR}\n") == {"FOO": "${BAR}"}

    def test_line_without_equals_skipped_and_debug_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="specify_cli.bootstrap.env_file")
        result = parse_env_file("not-a-kv-line\nFOO=bar\n")
        assert result == {"FOO": "bar"}
        assert "malformed" in caplog.text.lower()

    @pytest.mark.parametrize("bad_key_line", ["1FOO=bar", "FOO-BAR=baz", "=novalue", "FOO BAR=baz"])
    def test_invalid_key_skipped_and_debug_logged(
        self, bad_key_line: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="specify_cli.bootstrap.env_file")
        result = parse_env_file(f"{bad_key_line}\nGOOD=value\n")
        assert result == {"GOOD": "value"}

    def test_empty_text_yields_empty_dict(self) -> None:
        assert parse_env_file("") == {}

    def test_never_raises_on_garbage_input(self) -> None:
        garbage = "\x00\x01=###\n===\nFOO=bar\n"
        result = parse_env_file(garbage)
        assert result.get("FOO") == "bar"


# --------------------------------------------------------------------------- #
# Fixtures for the tiered-loader (in-process) tests below.
# --------------------------------------------------------------------------- #


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    """A fresh, isolated fake repo root (has a ``.kittify/`` marker)."""
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    return repo


def _write_repo_env(repo: Path, contents: str) -> Path:
    path = repo / ".kittify" / ".kitty.env"
    path.write_text(contents, encoding="utf-8")
    return path


def _write_home_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, contents: str) -> Path:
    home = tmp_path / "state-home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    path = home / ".kitty.env"
    path.write_text(contents, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# C-LDR-1: merge-then-setdefault precedence (real-env > per-repo > home)
# --------------------------------------------------------------------------- #


class TestPrecedence:
    def test_repo_overrides_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path) -> None:
        _write_home_env(monkeypatch, tmp_path, "FOO=home_value\n")
        _write_repo_env(repo_dir, "FOO=repo_value\n")

        environ: dict[str, str] = {}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["FOO"] == "repo_value"

    def test_home_used_when_repo_does_not_set_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        _write_home_env(monkeypatch, tmp_path, "FOO=home_value\n")
        _write_repo_env(repo_dir, "OTHER=repo_value\n")

        environ: dict[str, str] = {}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["FOO"] == "home_value"
        assert environ["OTHER"] == "repo_value"

    def test_real_env_wins_over_both_tiers(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        _write_home_env(monkeypatch, tmp_path, "FOO=home_value\n")
        _write_repo_env(repo_dir, "FOO=repo_value\n")

        environ: dict[str, str] = {"FOO": "real_env_value"}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["FOO"] == "real_env_value"

    def test_naive_per_tier_setdefault_would_invert_repo_over_home(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        """Regression witness for the exact bug the merge-then-setdefault order fixes.

        A NAIVE implementation that ran ``environ.setdefault`` once per home
        values and again per repo values (rather than merging first) would
        let the home pass's value for FOO win, because by the time the repo
        pass runs, ``setdefault`` is a no-op for a key already seeded. This
        test would catch a regression back to that shape.
        """
        _write_home_env(monkeypatch, tmp_path, "FOO=home_value\n")
        _write_repo_env(repo_dir, "FOO=repo_value\n")

        environ: dict[str, str] = {}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["FOO"] != "home_value"
        assert environ["FOO"] == "repo_value"

    def test_no_repo_root_still_loads_home_tier(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Home tier is machine-wide -- it must load even outside any project."""
        _write_home_env(monkeypatch, tmp_path, "FOO=home_value\n")
        outside = tmp_path / "not-a-repo"
        outside.mkdir()

        environ: dict[str, str] = {}
        load_operator_env_file(start=outside, environ=environ)

        assert environ["FOO"] == "home_value"


# --------------------------------------------------------------------------- #
# C-LDR-3: fail policy (absent -> warn+continue; unreadable -> fail loud;
# malformed line -> skip+debug-log, bootstrap survives)
# --------------------------------------------------------------------------- #


class TestFailPolicy:
    def test_absent_home_file_continues_silently_at_user_level(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Absence is logged at DEBUG (not warned) -- see the loader's own
        docstring on ``_read_tier`` for why: an absent ``.kitty.env`` is the
        default state for nearly every project, so a ``UserWarning`` on every
        CLI invocation would be noise, and concretely breaks the
        clean-stderr-on-import contract pinned by the sibling subprocess
        tests ``test_bare_import_emits_no_stderr`` and
        ``test_bare_import_without_operator_env_file_is_silent`` below.
        """
        caplog.set_level(logging.DEBUG, logger="specify_cli.bootstrap.env_file")
        home = tmp_path / "state-home"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        # No .kitty.env written at home -- and no repo tier either.

        environ: dict[str, str] = {}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_operator_env_file(start=repo_dir, environ=environ)

        assert caught == []
        assert "No operator env file found" in caplog.text
        assert environ == {}

    def test_absent_repo_file_continues_silently_at_user_level(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="specify_cli.bootstrap.env_file")
        _write_home_env(monkeypatch, tmp_path, "FOO=home_value\n")
        # repo_dir has .kittify/ but no .kitty.env inside it.

        environ: dict[str, str] = {}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["FOO"] == "home_value"
        assert caught == []
        assert "No operator env file found" in caplog.text

    def test_present_but_unreadable_home_file_fails_loud_naming_the_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        home_env_path = _write_home_env(monkeypatch, tmp_path, "FOO=bar\n")
        home_env_path.chmod(0o000)
        try:
            if os.access(home_env_path, os.R_OK):
                pytest.skip("filesystem/user does not enforce chmod 000 (e.g. running as root)")

            with pytest.raises(OperatorEnvFileUnreadableError) as excinfo:
                load_operator_env_file(start=repo_dir, environ={})

            assert str(home_env_path) in str(excinfo.value)
        finally:
            home_env_path.chmod(0o644)

    def test_malformed_line_is_skipped_bootstrap_survives(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        _write_home_env(monkeypatch, tmp_path, "not-a-kv-line\nFOO=bar\n1BAD=x\n")

        environ: dict[str, str] = {}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["FOO"] == "bar"
        assert "1BAD" not in environ


# --------------------------------------------------------------------------- #
# C-LDR-4: locator recursion (SPEC_KITTY_HOME= inside .kitty.env is ignored)
# --------------------------------------------------------------------------- #


class TestLocatorRecursion:
    def test_spec_kitty_home_line_inside_file_is_ignored_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        _write_home_env(
            monkeypatch,
            tmp_path,
            f"SPEC_KITTY_HOME={tmp_path / 'somewhere-else'}\nFOO=bar\n",
        )

        environ: dict[str, str] = {}
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            load_operator_env_file(start=repo_dir, environ=environ)

        assert "SPEC_KITTY_HOME" not in environ
        assert environ["FOO"] == "bar"
        assert any("SPEC_KITTY_HOME" in str(w.message) for w in caught)

    def test_locator_recursion_in_repo_tier_also_ignored(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        home = tmp_path / "state-home"
        home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
        _write_repo_env(repo_dir, "SPEC_KITTY_HOME=/nope\nBAR=baz\n")

        environ: dict[str, str] = {}
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            load_operator_env_file(start=repo_dir, environ=environ)

        assert "SPEC_KITTY_HOME" not in environ
        assert environ["BAR"] == "baz"


# --------------------------------------------------------------------------- #
# #289: repo-tier .kitty.env is a checkout-controlled trust surface for the
# SaaS identity vars -- pinned as documented behaviour, not a bug in this
# loader (see docs/api/environment-variables.md, "The .kitty.env file", and
# specify_cli/saas_client/auth.py's module docstring).
# --------------------------------------------------------------------------- #


class TestRepoTierSaasVarsAreSeeded:
    """Unlike ``SPEC_KITTY_HOME`` (denied at every tier, C-LDR-4), this loader
    does not -- and per its charter should not -- special-case
    ``SPEC_KITTY_SAAS_URL``/``SPEC_KITTY_SAAS_TOKEN``/``SPEC_KITTY_TEAM_SLUG``.
    A committed ``.kittify/.kitty.env`` seeds them like any other governed
    var for anyone who clones the repo and runs ``spec-kitty`` inside it.
    This test pins that fact so a future change here is a deliberate,
    reviewed decision (#289's candidate resolution 2/3) rather than a silent
    behaviour change.
    """

    def test_repo_tier_seeds_saas_url_token_and_team_slug(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        _write_repo_env(
            repo_dir,
            "SPEC_KITTY_SAAS_URL=https://attacker.example\n"
            "SPEC_KITTY_SAAS_TOKEN=attacker-token\n"
            "SPEC_KITTY_TEAM_SLUG=attacker-team\n",
        )

        environ: dict[str, str] = {}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["SPEC_KITTY_SAAS_URL"] == "https://attacker.example"
        assert environ["SPEC_KITTY_SAAS_TOKEN"] == "attacker-token"
        assert environ["SPEC_KITTY_TEAM_SLUG"] == "attacker-team"

    def test_real_env_saas_url_still_wins_over_repo_tier(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        """Precedence (C-LDR-1) applies here too: an operator who already
        exported ``SPEC_KITTY_SAAS_URL`` in their own shell is not overridden
        by a cloned repo's ``.kitty.env``."""
        _write_repo_env(repo_dir, "SPEC_KITTY_SAAS_URL=https://attacker.example\n")

        environ: dict[str, str] = {"SPEC_KITTY_SAAS_URL": "https://operator.example"}
        load_operator_env_file(start=repo_dir, environ=environ)

        assert environ["SPEC_KITTY_SAAS_URL"] == "https://operator.example"


# --------------------------------------------------------------------------- #
# C-LDR-5: single config.yaml env_file pointer, resolved once
# --------------------------------------------------------------------------- #


class TestConfigEnvFilePointer:
    def test_default_when_no_config_yaml(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda _cls: tmp_path))

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == get_runtime_state_root() / ".kitty.env"
        assert "$" not in str(resolved)

    def test_default_when_config_yaml_has_no_env_file_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        (repo_dir / ".kittify" / "config.yaml").write_text("agents:\n  available: []\n", encoding="utf-8")
        state_home = tmp_path / "state-home"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(state_home))

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == state_home / ".kitty.env"

    def test_custom_env_file_pointer_is_resolved_once(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        state_home = tmp_path / "state-home"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(state_home))
        (repo_dir / ".kittify" / "config.yaml").write_text(
            "env_file: ${SPEC_KITTY_HOME}/custom.env\nagents:\n  available: []\n",
            encoding="utf-8",
        )

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == state_home / "custom.env"
        assert "$" not in str(resolved)

    def test_env_file_key_nested_under_another_section_is_not_picked_up(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        """Only the TOP-LEVEL ``env_file:`` key counts -- an indented lookalike must not."""
        state_home = tmp_path / "state-home"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(state_home))
        (repo_dir / ".kittify" / "config.yaml").write_text(
            "agents:\n  env_file: /should/not/be/used\n",
            encoding="utf-8",
        )

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == state_home / ".kitty.env"

    def test_env_file_key_lives_outside_the_doctrine_org_extra_forbid_block(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        """The env_file pointer must not break ``charter.offering.drg.org_pack_config.PackRegistry``.

        That model's ``model_config = ConfigDict(extra="forbid")``
        (src/charter/offering/drg/org_pack_config.py:307) validates ONLY the
        ``charter.offering.org`` subsection of config.yaml -- a sibling top-level
        ``env_file:`` key must be invisible to it (C-LDR-5).
        """
        from charter.offering.drg.org_pack_config import load_pack_registry

        state_home = tmp_path / "state-home"
        monkeypatch.setenv("SPEC_KITTY_HOME", str(state_home))
        (repo_dir / ".kittify" / "config.yaml").write_text(
            "env_file: ${SPEC_KITTY_HOME}/.kitty.env\n"
            "doctrine:\n"
            "  org:\n"
            "    packs: []\n",
            encoding="utf-8",
        )

        registry = load_pack_registry(repo_dir)  # must not raise ValidationError

        assert registry.packs == []
        resolved = env_file._resolve_home_tier_path(repo_dir, {})
        assert resolved == state_home / ".kitty.env"

    def test_unset_locator_default_does_not_raise(self, monkeypatch: pytest.MonkeyPatch, repo_dir: Path) -> None:
        """${SPEC_KITTY_HOME} unset must resolve to the state-root default, never raise."""
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == get_runtime_state_root() / ".kitty.env"


# --------------------------------------------------------------------------- #
# C-LDR-7: cross-platform, state-root (not .kittify) home
# --------------------------------------------------------------------------- #


class TestCrossPlatformStateRootHome:
    def test_posix_default_matches_state_root_primitive(
        self, monkeypatch: pytest.MonkeyPatch, repo_dir: Path
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == get_runtime_state_root() / ".kitty.env"
        assert resolved == Path.home() / ".spec-kitty" / ".kitty.env"
        assert ".kittify" not in resolved.parts

    def test_windows_default_matches_state_root_primitive(
        self, monkeypatch: pytest.MonkeyPatch, repo_dir: Path
    ) -> None:
        import platformdirs

        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
        monkeypatch.setattr(
            platformdirs,
            "user_data_dir",
            lambda *_a, **_kw: r"C:\Users\test\AppData\Local\spec-kitty",
        )

        resolved = env_file._resolve_home_tier_path(repo_dir, {})

        assert resolved == get_runtime_state_root() / ".kitty.env"
        assert resolved == Path(r"C:\Users\test\AppData\Local\spec-kitty") / ".kitty.env"


# --------------------------------------------------------------------------- #
# C-LDR-2: pre-import ordering (subprocess, real process boundary)
# --------------------------------------------------------------------------- #


def _subprocess_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    isolated_home = tmp_path / "home"
    isolated_home.mkdir(exist_ok=True)
    env.update(
        {
            "HOME": str(isolated_home),
            "USERPROFILE": str(isolated_home),
            "XDG_CONFIG_HOME": str(isolated_home / "config"),
            "XDG_DATA_HOME": str(isolated_home / "data"),
            "PYTHONPATH": str(_REPO_ROOT / "src"),
            "SPEC_KITTY_NO_UPGRADE_CHECK": "1",
        }
    )
    env.pop("SPEC_KITTY_HOME", None)
    env.pop("SPEC_KITTY_SYNC_MINIMAL_IMPORT", None)
    return env


_SEEDED_ENV_PROBE_SCRIPT = (
    "import os\n"
    "import specify_cli  # noqa: F401 -- the seed must be in os.environ BEFORE this runs\n"
    "print(os.environ.get('SPEC_KITTY_SYNC_MINIMAL_IMPORT', ''))\n"
)


@pytest.mark.integration
def test_sync_minimal_import_set_only_in_kitty_env_reaches_os_environ_before_import(
    tmp_path: Path,
) -> None:
    """C-LDR-2: SPEC_KITTY_SYNC_MINIMAL_IMPORT set ONLY in .kitty.env is visible in
    ``os.environ`` as soon as ``import specify_cli`` has run -- proving the loader's
    seed lands BEFORE any import-time consumer could read it.

    The consumer this used to observe was ``sync/__init__.py``'s import-time
    registration gate, which retired with the sync transport (issue #5). What is
    left to pin — and what the loader actually owns — is the ordering itself.
    """
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    (repo / ".kittify" / ".kitty.env").write_text(
        "SPEC_KITTY_SYNC_MINIMAL_IMPORT=1\n", encoding="utf-8"
    )
    env = _subprocess_env(tmp_path)
    assert "SPEC_KITTY_SYNC_MINIMAL_IMPORT" not in env, "must come from the file, not the real env"

    result = subprocess.run(
        [sys.executable, "-c", _SEEDED_ENV_PROBE_SCRIPT],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1", (
        f"expected SPEC_KITTY_SYNC_MINIMAL_IMPORT from .kitty.env to be seeded into "
        f"os.environ before `import specify_cli`; "
        f"got stdout={result.stdout!r} stderr={result.stderr}"
    )


@pytest.mark.integration
def test_control_without_kitty_env_seeds_nothing(tmp_path: Path) -> None:
    """Control for the test above: absent the file, nothing is seeded."""
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    env = _subprocess_env(tmp_path)

    result = subprocess.run(
        [sys.executable, "-c", _SEEDED_ENV_PROBE_SCRIPT],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", (
        "control run (no .kitty.env) must not seed SPEC_KITTY_SYNC_MINIMAL_IMPORT; "
        f"stdout={result.stdout!r} stderr={result.stderr}"
    )


@pytest.mark.integration
def test_bare_import_emits_no_stderr(tmp_path: Path) -> None:
    """A bare ``import specify_cli`` at a real process boundary is silent."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = _subprocess_env(tmp_path)
    env.pop("SPEC_KITTY_TEST_MODE", None)

    result = subprocess.run(
        [sys.executable, "-c", "import specify_cli"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == "", (
        "a bare import must not print to stdout or stderr; "
        f"stdout={result.stdout!r} stderr={result.stderr}"
    )


@pytest.mark.integration
def test_bare_import_without_operator_env_file_is_silent(tmp_path: Path) -> None:
    """A bare ``import specify_cli`` must print nothing when no file exists."""
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    env = _subprocess_env(tmp_path)

    result = subprocess.run(
        [sys.executable, "-c", "import specify_cli"],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


# --------------------------------------------------------------------------- #
# NFR-001: startup overhead budget (delta vs a no-.kitty.env baseline)
# --------------------------------------------------------------------------- #


class TestStartupOverheadBudget:
    """NFR-001 (spec.md): the pre-import load adds bounded overhead, measured
    as a delta against a no-file baseline, and does not regress the
    TAB-completion latency contract
    (``tests/specify_cli/cli/commands/test_completion_fast_path.py``, itself
    guarding the SC-003 500 ms completion budget). That suite has no
    wall-clock assertion to extend (it pins structure -- zero heavy CLI
    modules loaded -- not timing; see its own docstring and the repo-wide
    no-hard-timing-thresholds policy in
    docs/development/testing/testing-flakiness.md), so this is the
    micro-benchmark DoD's fallback clause calls for: a delta-vs-baseline
    measurement with a generous, flake-resistant bound rather than an
    absolute-ms assertion.
    """

    def test_loader_call_adds_no_heavy_third_party_import(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, repo_dir: Path
    ) -> None:
        """Structural half of the budget: the loader itself must never pull in
        typer/rich/httpx/requests/etc. -- those are exactly what the sibling
        completion-fast-path benchmark polices for the CLI's own entry point
        (``_HEAVY_MODULES`` in test_completion_fast_path.py). Checked directly
        here (not via subprocess) so it runs in the fast suite.
        """
        _write_repo_env(repo_dir, "FOO=bar\nBAZ=qux\nSPEC_KITTY_ENABLE_SAAS_SYNC=1\n")
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "state-home"))

        heavy = {"typer", "rich", "httpx", "requests", "websockets", "pydantic"}
        before = set(sys.modules)

        load_operator_env_file(start=repo_dir, environ={})

        newly_imported = set(sys.modules) - before
        heavy_hit = {m for m in newly_imported if m.split(".")[0] in heavy}
        assert heavy_hit == set(), f"loader call newly imported heavy module(s): {heavy_hit}"

    @pytest.mark.slow
    def test_loader_overhead_delta_vs_no_file_baseline_within_noise_floor(self, tmp_path: Path) -> None:
        """End-to-end delta: `import specify_cli` wall time with vs without a
        realistic ``.kitty.env`` present. Budget source: spec.md NFR-001
        ("bounded overhead ... delta against a no-file baseline ... does not
        regress the TAB-completion benchmark") + SC-003's 500 ms completion
        budget (test_completion_fast_path.py docstring). A `.kitty.env`
        parse is a handful of stdlib file reads + regex matches -- a few ms
        at most -- so a 150 ms median-delta bound is already generous
        headroom against process-launch noise, not a tight timing gate.
        """
        script = "import time\nt0 = time.perf_counter()\nimport specify_cli  # noqa: F401\nprint(time.perf_counter() - t0)\n"

        def _median_duration(*, with_env_file: bool) -> float:
            repo = tmp_path / ("with_env" if with_env_file else "without_env")
            (repo / ".kittify").mkdir(parents=True)
            if with_env_file:
                (repo / ".kittify" / ".kitty.env").write_text(
                    "FOO=bar\nBAZ=qux\nSPEC_KITTY_PRERELEASE=0\nSOME_OTHER_KEY=value\nYET_ANOTHER=1\n",
                    encoding="utf-8",
                )
            env = _subprocess_env(tmp_path)
            samples = []
            for _ in range(5):
                result = subprocess.run(
                    [sys.executable, "-c", script],
                    cwd=repo,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=60,
                )
                assert result.returncode == 0, result.stderr
                samples.append(float(result.stdout.strip()))
            samples.sort()
            return samples[len(samples) // 2]

        baseline_median = _median_duration(with_env_file=False)
        with_file_median = _median_duration(with_env_file=True)
        delta_ms = (with_file_median - baseline_median) * 1000

        assert delta_ms < 150, (
            f"loader overhead delta {delta_ms:.1f} ms exceeds the 150 ms noise-floor "
            f"budget (baseline={baseline_median * 1000:.1f} ms, with_file={with_file_median * 1000:.1f} ms)"
        )
