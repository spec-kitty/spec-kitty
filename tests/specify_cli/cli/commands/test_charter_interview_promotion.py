"""End-to-end CLI test: `spec-kitty charter interview` promotes selections (WP07, T024, FR-007).

Proves the wiring between the `charter interview` command and
``charter.activation.activation_engine.promote_activations`` (via
``m_unify_charter_activation.resolve_selected_id_to_stem`` /
``load_default_pack_ids``) — the captured `selected_paradigms` /
`selected_directives` must be append-promoted into
``.kittify/config.yaml``'s ``activated_*`` keys after every interview run,
without dropping any pre-existing built-in when the key was previously
absent (the WP06 LAND-BLOCKER, exercised here at the live CLI call site).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.upgrade.migrations.m_unify_charter_activation import load_default_pack_ids

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

# Real built-in artifacts (this module never mocks resolve_doctrine_root()).
_DIRECTIVE_010_STEM = "010-specification-fidelity-requirement"
_DIRECTIVE_010_CANONICAL = "DIRECTIVE_010"
_PARADIGM_DDD = "domain-driven-design"


def _git_init(repo: Path) -> None:
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    for key, value in (
        ("user.email", "test@example.com"),
        ("user.name", "Test User"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(["git", "config", key, value], cwd=repo, check=True, capture_output=True)


def _read_config(repo_root: Path) -> dict[str, object]:
    config_path = repo_root / ".kittify" / "config.yaml"
    assert config_path.exists(), f"config.yaml not written at {config_path}"
    yaml = YAML(typ="safe")
    loaded = yaml.load(config_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_interview_promotes_selections_preserving_builtins_on_absent_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pre-existing config.yaml (absent-key state): promotion must union in
    the real built-in directive/paradigm set, not just the newly-selected ids.
    """
    _git_init(tmp_path)
    # Hermetic against a stray ``.kittify`` marker anywhere above ``tmp_path``
    # (e.g. a developer's home-dir kittify root, or another test's litter
    # under the OS temp dir): with no config.yaml at ``tmp_path`` yet,
    # ``locate_project_root``'s walk-up would otherwise happily resolve to
    # that ambient ancestor instead of this fixture's repo, and the
    # promoted config.yaml would land there instead of under tmp_path.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        [
            "interview",
            "--defaults",
            "--profile", "minimal",
            "--selected-directives", _DIRECTIVE_010_STEM,
            "--selected-paradigms", _PARADIGM_DDD,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"interview failed: stdout={result.stdout!r}"

    config = _read_config(tmp_path)
    real_builtin_directives = load_default_pack_ids().get("activated_directives", [])
    real_builtin_paradigms = load_default_pack_ids().get("activated_paradigms", [])
    assert real_builtin_directives and real_builtin_paradigms

    committed_directives = config["activated_directives"]
    committed_paradigms = config["activated_paradigms"]

    # Selected ids present.
    assert _DIRECTIVE_010_STEM in committed_directives
    assert _PARADIGM_DDD in committed_paradigms
    # Built-ins NOT dropped (the absent-key LAND-BLOCKER, at this call site).
    assert set(real_builtin_directives).issubset(set(committed_directives))
    assert set(real_builtin_paradigms).issubset(set(committed_paradigms))


def test_interview_normalizes_canonical_form_directive_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directive selected in canonical id form (DIRECTIVE_010) still promotes
    into config as its config-stem form (ID-form parity, WP01 resolver reuse).
    """
    _git_init(tmp_path)
    # See the hermeticity note in
    # test_interview_promotes_selections_preserving_builtins_on_absent_key.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        [
            "interview",
            "--defaults",
            "--profile", "minimal",
            "--selected-directives", _DIRECTIVE_010_CANONICAL,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout

    config = _read_config(tmp_path)
    assert _DIRECTIVE_010_STEM in config["activated_directives"]
    assert _DIRECTIVE_010_CANONICAL not in config["activated_directives"]


def test_interview_promotion_is_idempotent_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_path)
    # See the hermeticity note in
    # test_interview_promotes_selections_preserving_builtins_on_absent_key.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    args = [
        "interview",
        "--defaults",
        "--profile", "minimal",
        "--selected-directives", _DIRECTIVE_010_STEM,
    ]
    first = runner.invoke(charter_app, args, catch_exceptions=False)
    assert first.exit_code == 0
    second = runner.invoke(charter_app, args, catch_exceptions=False)
    assert second.exit_code == 0

    config = _read_config(tmp_path)
    assert config["activated_directives"].count(_DIRECTIVE_010_STEM) == 1


def test_interview_with_no_selections_leaves_config_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-007 is append-only: an interview run with no directive/paradigm
    selections must not fabricate config.yaml activation keys.
    """
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        [
            "interview",
            "--defaults",
            "--profile", "minimal",
            "--selected-directives", "",
            "--selected-paradigms", "",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout

    config_path = tmp_path / ".kittify" / "config.yaml"
    if config_path.exists():
        data = YAML(typ="safe").load(config_path.read_text(encoding="utf-8")) or {}
        assert "activated_directives" not in data
        assert "activated_paradigms" not in data
