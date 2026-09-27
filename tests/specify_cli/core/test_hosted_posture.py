"""Contract for the hosted drain + ledger posture reader.

Pins the truth table in ``contracts/hosted-posture.md`` (charter C-011).

Every real-file test below carries ``@pytest.mark.real_drain_posture`` (at
class scope) so the root autouse fixture (``tests/conftest.py``) does
not replace the reader under test with a monkeypatched stub -- this file
exercises the real, file-based ``drain_posture``/``ledger_posture``/
``set_personal_drain``. The two "proof of patch" tests at the bottom
(``TestRootFixtureProof``) deliberately carry NO marker: they exist to prove
the autouse fixture and the ``drain_off`` fixture actually patch this
module's ``drain_posture`` attribute.

Isolating ``SPEC_KITTY_HOME`` for the personal-scope tests goes through the
canonical ``canonical_home`` fixture (``tests/conftest.py``) -- the ONE
sanctioned ``SPEC_KITTY_HOME`` owner (R1a, #3121) -- rather than a local
``monkeypatch.setenv("SPEC_KITTY_HOME", ...)``: the isolated-home-pin-guard
census (``tests/architectural/test_spec_kitty_home_pin_census.py``) tracks
every such call site across ``tests/``, and a second, ad-hoc site is exactly
the drift that guard exists to catch. ``canonical_home`` pins
``SPEC_KITTY_HOME`` to ``tmp_path / "home"``, so ``_home()`` below only
prepares that same directory's ``config.toml`` -- it does no env I/O itself.

**Hermetic against the ambient environment.** The
orchestrator that runs this suite may itself run with
``SPEC_KITTY_NO_MOMENT_HANDLERS=1`` (or the kill switch, or the deprecated
minimal-import alias) set in its own process environment. Left alone, that
would narrow every real ``drain_posture()`` call in this file regardless of
what the test itself arranges. The module-local autouse
``_clear_moment_handler_env`` fixture below ``delenv``'s every name in
``specify_cli.core.env.MOMENT_HANDLER_DISABLE_ENV_VARS`` before each test, so
only a test's OWN explicit ``monkeypatch.setenv`` (as
``test_narrower_env_var_forces_off_via_real_env_read`` does) can narrow.

Truth table (contracts/hosted-posture.md): ``enabled == (repo is True and
personal is True and no env narrower is set)``.
"""

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path

import pytest
from ruamel.yaml.error import YAMLError

from specify_cli.core import hosted_posture
from specify_cli.core.env import MOMENT_HANDLER_DISABLE_ENV_VARS
from specify_cli.core.hosted_posture import (
    DrainDisabled,
    drain_posture,
    ledger_posture,
    require_drain,
    set_personal_drain,
    set_repo_drain,
)


@pytest.fixture(autouse=True)
def _clear_moment_handler_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep every test in this module hermetic against ambient env narrowers
    -- see the module docstring."""
    for name in MOMENT_HANDLER_DISABLE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _repo(tmp_path: Path, *, yaml_text: str | None = None) -> Path:
    """A tmp-path repo with a ``.kittify/`` marker and an optional config.yaml."""
    root = tmp_path / "repo"
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    if yaml_text is not None:
        (kittify / "config.yaml").write_text(yaml_text, encoding="utf-8")
    return root


def _home(tmp_path: Path, *, toml_text: str | None = None) -> Path:
    """The personal ``config.toml`` under the ``canonical_home``-pinned
    ``SPEC_KITTY_HOME`` (``tmp_path / "home"``). The caller must have already
    requested the ``canonical_home`` fixture so the directory exists and the
    env var is pinned before this runs."""
    home = tmp_path / "home"
    if toml_text is not None:
        (home / "config.toml").write_text(toml_text, encoding="utf-8")
    return home


# ---------------------------------------------------------------------------
# Truth table (contracts/hosted-posture.md)
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestTruthTable:
    def test_repo_true_personal_true_no_narrower_is_enabled(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is True
        assert posture.narrowed_by is None
        assert posture.repo_value is True
        assert posture.personal_value is True

    def test_narrower_forces_off_even_when_both_scopes_are_on(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        monkeypatch.setattr(
            "specify_cli.core.env.moment_handlers_disabled_reason",
            lambda: "SPEC_KITTY_NO_MOMENT_HANDLERS is set",
        )

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.narrowed_by == "SPEC_KITTY_NO_MOMENT_HANDLERS is set"
        assert "SPEC_KITTY_NO_MOMENT_HANDLERS is set" in posture.reason

    def test_narrower_env_var_forces_off_via_real_env_read(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pins the actual env->narrower integration, not only the ``moment_handlers_disabled_reason`` function seam: sets
        the REAL environment variable and lets ``drain_posture`` read it
        through the real, unpatched ``specify_cli.core.env`` module."""
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        monkeypatch.setenv("SPEC_KITTY_NO_MOMENT_HANDLERS", "1")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.narrowed_by == "SPEC_KITTY_NO_MOMENT_HANDLERS is set"

    @pytest.mark.parametrize(
        "personal_toml",
        [None, "[hosted]\ndrain = false\n"],
        ids=["absent", "false"],
    )
    def test_repo_true_personal_off_or_absent_is_disabled(self, tmp_path: Path, canonical_home: None, personal_toml: str | None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text=personal_toml)

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert "personal" in posture.reason.lower()

    @pytest.mark.parametrize(
        "repo_yaml",
        [None, "hosted:\n  drain: false\n"],
        ids=["absent", "false"],
    )
    def test_repo_off_or_absent_is_disabled_regardless_of_personal(self, tmp_path: Path, canonical_home: None, repo_yaml: str | None) -> None:
        repo = _repo(tmp_path, yaml_text=repo_yaml)
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert "repositor" in posture.reason.lower()


# ---------------------------------------------------------------------------
# R-1: no environment variable can enable drain in either scope
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestEnvCannotEnable:
    def test_env_vars_that_look_like_they_enable_drain_are_ignored(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: false\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = false\n")

        without_env = drain_posture(project_root=repo)

        monkeypatch.setenv("SPEC_KITTY_HOSTED_DRAIN", "1")
        monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://example.test")

        with_env = drain_posture(project_root=repo)

        assert with_env == without_env
        assert with_env.enabled is False

    def test_specify_repo_root_redirect_cannot_supply_personal_activation(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``.kitty.env``-style ``SPECIFY_REPO_ROOT`` redirect must not let an
        attacker-controlled directory supply the personal activation: the
        personal file always comes from the runtime root (``SPEC_KITTY_HOME``),
        never from any repo-relative path."""
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = false\n")
        decoy_repo_root = tmp_path / "attacker-controlled"
        decoy_kittify = decoy_repo_root / ".kittify"
        decoy_kittify.mkdir(parents=True)
        (decoy_kittify / "config.yaml").write_text("hosted:\n  drain: true\n", encoding="utf-8")
        monkeypatch.setenv("SPECIFY_REPO_ROOT", str(decoy_repo_root))

        # project_root is passed explicitly (the real repo), but the personal
        # scope must still resolve from SPEC_KITTY_HOME regardless -- the decoy
        # only proves a redirect present in the environment has no bearing on
        # personal-scope resolution.
        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.personal_value is not True


# ---------------------------------------------------------------------------
# No resolvable repo root (project_root=None and locate_project_root() -> None)
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestNoResolvableRepoRoot:
    """``locate_project_root`` patched directly (this module's own imported
    name) rather than arranging a real rootless CWD: a real walk-up is
    filesystem-position-dependent and risks picking up a stray ``.kittify``/
    ``.git`` in a shared ancestor (the same class of flake the resolver's own
    docstring warns about), where patching the seam this module actually
    calls is deterministic and exercises the identical code path."""

    def test_drain_posture_with_no_resolvable_root(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.core.hosted_posture.locate_project_root", lambda: None)
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        posture = drain_posture()

        assert posture.enabled is False
        assert posture.repo_value is None
        assert posture.repo_source == "no repository root resolved"

    def test_ledger_posture_with_no_resolvable_root(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("specify_cli.core.hosted_posture.locate_project_root", lambda: None)

        posture = ledger_posture()

        assert posture.enabled is True
        assert posture.source == "no repository root resolved"


# ---------------------------------------------------------------------------
# B1: an explicit project_root is a starting point, never trusted verbatim
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestExplicitRootIsCanonicalisedNotTrustedVerbatim:
    """B1 (adversarial review finding): every real caller of
    :func:`drain_posture`/:func:`resolve_credentials` that passes an explicit
    ``project_root`` hands it a *starting point* under the repo -- a lifecycle
    envelope's ``cwd`` is ``kitty-specs/<mission>/``, a runtime moment's is
    ``.kittify/runtime/runs/<id>/`` -- never the repo root itself. Before the
    fix, ``_resolve_repo_root`` returned that path verbatim, so
    ``<subdir>/.kittify/config.yaml`` (which never exists) always read as
    absent and every such caller was permanently drain-off regardless of the
    real repo's configured posture.
    """

    def test_a_mission_subdir_of_a_real_git_repo_resolves_to_the_repo_root(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        mission_subdir = repo / "kitty-specs" / "mission-01"
        mission_subdir.mkdir(parents=True)

        posture = drain_posture(project_root=mission_subdir)

        assert posture.enabled is True
        assert posture.repo_value is True

    def test_a_mission_subdir_of_a_kittify_only_repo_with_no_git_still_resolves(self, tmp_path: Path, canonical_home: None) -> None:
        """No ``.git`` at all (a project that predates or omits one, exactly
        this reader's own ``.kittify``-only test fixtures) -- the
        ``.kittify``-marker fallback tier must still find the root from a
        subdirectory, not only when given the root verbatim."""
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        mission_subdir = repo / "kitty-specs" / "mission-01"
        mission_subdir.mkdir(parents=True)

        posture = drain_posture(project_root=mission_subdir)

        assert posture.enabled is True
        assert posture.repo_value is True

    def test_an_unresolvable_explicit_root_is_drain_off_never_the_cwd(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        """The process CWD is a real, drain-ON repo, but the explicit root
        passed to ``drain_posture`` has no ``.git``/``.kittify`` anywhere
        above it. This must fail closed (drain off), never silently fall
        back to reading the CWD repo's posture instead -- an explicit root
        that cannot resolve is never conflated with "no root was given"."""
        cwd_repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        subprocess.run(["git", "init", "-q"], cwd=cwd_repo, check=True, capture_output=True)
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        monkeypatch.chdir(cwd_repo)
        rootless = tmp_path / "elsewhere" / "rootless"
        rootless.mkdir(parents=True)

        posture = drain_posture(project_root=rootless)

        assert posture.enabled is False
        assert posture.repo_value is None
        assert posture.repo_source == "no repository root resolved"


# ---------------------------------------------------------------------------
# Repo config.yaml shapes that read as absent, not as a parse error
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestRepoConfigShapeVariations:
    """A non-mapping at the top level, at the section, or a section missing
    the key: all read as unset/absent, distinct from a present-but-non-bool
    VALUE (which warns, covered by ``TestParseErrorsFailClosed``)."""

    def test_non_mapping_top_level_yaml_is_absent(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="- just\n- a\n- list\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.repo_value is None

    def test_hosted_section_non_mapping_is_absent(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted: not-a-mapping\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.repo_value is None

    def test_hosted_section_missing_drain_key_is_absent(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  other: 1\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.repo_value is None

    def test_personal_hosted_section_missing_drain_key_is_absent(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\nother_key = 1\n")

        posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert posture.personal_value is None


# ---------------------------------------------------------------------------
# Fail-closed parsing (spec.md Edge Cases)
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestParseErrorsFailClosed:
    def test_malformed_repo_yaml_fails_closed_with_one_warning(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path)
        (repo / ".kittify" / "config.yaml").write_text("hosted: [unterminated\n", encoding="utf-8")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        with pytest.warns(UserWarning) as caught:
            posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert len(caught) == 1

    def test_malformed_personal_toml_fails_closed_with_one_warning(self, tmp_path: Path, canonical_home: None) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        home = _home(tmp_path)
        (home / "config.toml").write_text("not [ valid toml", encoding="utf-8")

        with pytest.warns(UserWarning) as caught:
            posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert len(caught) == 1

    @pytest.mark.parametrize("raw", ['"yes"', "1"], ids=["string", "int"])
    def test_repo_non_bool_fails_closed_with_one_warning(self, tmp_path: Path, canonical_home: None, raw: str) -> None:
        repo = _repo(tmp_path, yaml_text=f"hosted:\n  drain: {raw}\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")

        with pytest.warns(UserWarning) as caught:
            posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert len(caught) == 1

    @pytest.mark.parametrize("raw", ['"yes"', "1"], ids=["string", "int"])
    def test_personal_non_bool_fails_closed_with_one_warning(self, tmp_path: Path, canonical_home: None, raw: str) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text=f"[hosted]\ndrain = {raw}\n")

        with pytest.warns(UserWarning) as caught:
            posture = drain_posture(project_root=repo)

        assert posture.enabled is False
        assert len(caught) == 1


# ---------------------------------------------------------------------------
# ledger_posture
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestLedgerPosture:
    def test_default_true_when_key_absent(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")

        posture = ledger_posture(project_root=repo)

        assert posture.enabled is True

    def test_false_when_projection_is_false(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="ledger:\n  projection: false\n")

        posture = ledger_posture(project_root=repo)

        assert posture.enabled is False

    def test_default_true_with_a_warning_when_non_boolean(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text='ledger:\n  projection: "nope"\n')

        with pytest.warns(UserWarning):
            posture = ledger_posture(project_root=repo)

        assert posture.enabled is True

    def test_default_true_when_config_file_missing(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)  # .kittify/ exists but config.yaml itself does not

        posture = ledger_posture(project_root=repo)

        assert posture.enabled is True

    def test_malformed_yaml_defaults_true_with_one_warning(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        (repo / ".kittify" / "config.yaml").write_text("ledger: [unterminated\n", encoding="utf-8")

        with pytest.warns(UserWarning) as caught:
            posture = ledger_posture(project_root=repo)

        assert posture.enabled is True
        assert len(caught) == 1

    def test_non_mapping_top_level_yaml_defaults_true(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="- a\n- list\n")

        posture = ledger_posture(project_root=repo)

        assert posture.enabled is True


# ---------------------------------------------------------------------------
# require_drain
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestRequireDrain:
    def test_raises_drain_disabled_when_off(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: false\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        monkeypatch.chdir(repo)

        with pytest.raises(DrainDisabled) as excinfo:
            require_drain("some-context")

        assert "some-context" in str(excinfo.value)

    def test_returns_none_when_enabled(self, tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
        repo = _repo(tmp_path, yaml_text="hosted:\n  drain: true\n")
        _home(tmp_path, toml_text="[hosted]\ndrain = true\n")
        monkeypatch.chdir(repo)

        assert require_drain("some-context") is None


# ---------------------------------------------------------------------------
# D7: set_personal_drain is a strict writer
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestSetPersonalDrainStrictWriter:
    def test_toggle_preserves_sync_and_other_tables(self, tmp_path: Path, canonical_home: None) -> None:
        home = _home(
            tmp_path,
            toml_text=('[sync]\nserver_url = "https://example.test"\n[other]\nkeep = true\n'),
        )

        set_personal_drain(True)
        set_personal_drain(False)

        with (home / "config.toml").open("rb") as fh:
            document = tomllib.load(fh)
        assert document["sync"] == {"server_url": "https://example.test"}
        assert document["other"] == {"keep": True}
        assert document["hosted"] == {"drain": False}

    def test_refuses_to_overwrite_an_unparseable_file(self, tmp_path: Path, canonical_home: None) -> None:
        home = _home(tmp_path)
        config_path = home / "config.toml"
        config_path.write_bytes(b"not [ valid toml")
        original_bytes = config_path.read_bytes()

        with pytest.raises(tomllib.TOMLDecodeError):
            set_personal_drain(True)

        assert config_path.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# set_repo_drain
# ---------------------------------------------------------------------------


@pytest.mark.real_drain_posture
class TestSetRepoDrain:
    def test_preserves_comments_and_other_keys_and_round_trips(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path)
        config_path = repo / ".kittify" / "config.yaml"
        config_path.write_text(
            "# a comment\nproject:\n  uuid: abc-123\nhosted:\n  drain: false\n",
            encoding="utf-8",
        )

        written = set_repo_drain(repo, True)

        assert written == config_path
        text = config_path.read_text(encoding="utf-8")
        assert "# a comment" in text
        assert "uuid: abc-123" in text
        assert drain_posture(project_root=repo).repo_value is True

    def test_creates_a_missing_config_yaml_when_kittify_exists(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        (repo / ".kittify").mkdir(parents=True)
        config_path = repo / ".kittify" / "config.yaml"
        assert not config_path.exists()

        written = set_repo_drain(repo, True)

        assert written == config_path
        assert config_path.exists()
        assert drain_posture(project_root=repo).repo_value is True

    def test_replaces_a_non_mapping_hosted_section(self, tmp_path: Path) -> None:
        repo = _repo(tmp_path, yaml_text="hosted: not-a-mapping\n")

        set_repo_drain(repo, True)

        assert drain_posture(project_root=repo).repo_value is True

    def test_raises_on_unparseable_yaml_and_leaves_bytes_unchanged(self, tmp_path: Path) -> None:
        """Intentionally fail-loud (see the ``set_repo_drain`` docstring):
        an existing but unparseable ``config.yaml`` propagates ruamel's
        ``YAMLError`` and writes nothing, rather than being silently
        replaced by an empty document."""
        repo = _repo(tmp_path)
        config_path = repo / ".kittify" / "config.yaml"
        original = b"hosted: [unterminated\n"
        config_path.write_bytes(original)

        with pytest.raises(YAMLError):
            set_repo_drain(repo, True)

        assert config_path.read_bytes() == original


# ---------------------------------------------------------------------------
# Proof that the root autouse fixture patches the right target
# ---------------------------------------------------------------------------


class TestRootFixtureProof:
    """No ``real_drain_posture`` marker here on purpose: these tests exist to
    prove the root autouse fixture (and ``drain_off``) actually patch
    ``specify_cli.core.hosted_posture.drain_posture``."""

    def test_autouse_fixture_enables_drain_by_default(self) -> None:
        assert hosted_posture.drain_posture().enabled is True
        assert hosted_posture.require_drain("x") is None

    def test_drain_off_fixture_flips_both_reads(self, drain_off: None) -> None:
        assert hosted_posture.drain_posture().enabled is False
        with pytest.raises(DrainDisabled):
            hosted_posture.require_drain("x")
