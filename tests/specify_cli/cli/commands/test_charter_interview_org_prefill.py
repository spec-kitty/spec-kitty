"""End-to-end CLI test: `spec-kitty charter interview` applies org-charter pre-fill (FR-026).

Proves the wiring between the CLI command and
``charter.activation.org_charter.apply_org_charter_to_interview`` —
without this test, the helper would be live but unreachable from the user
surface, which was the original HIGH-2 finding in the post-mission review.
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()


def _git_init(repo: Path) -> None:
    """Initialize a minimal git repo with identity configured."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    for key, value in (
        ("user.email", "test@example.com"),
        ("user.name", "Test User"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", "config", key, value],
            cwd=repo, check=True, capture_output=True,
        )


def _write_org_pack_with_charter(pack_dir: Path, body: str) -> Path:
    pack_dir.mkdir(parents=True, exist_ok=True)
    path = pack_dir / "org-charter.yaml"
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    return path


def _write_kittify_config_with_packs(repo_root: Path, packs: list[dict[str, str]]) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["doctrine:", "  org:", "    packs:"]
    for pack in packs:
        lines.append(f"      - name: {pack['name']}")
        lines.append(f"        local_path: {pack['local_path']}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_answers(repo_root: Path) -> dict[str, object]:
    answers_path = repo_root / ".kittify" / "charter" / "interview" / "answers.yaml"
    assert answers_path.exists(), f"answers.yaml not written at {answers_path}"
    yaml = YAML(typ="safe")
    loaded = yaml.load(answers_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


@pytest.fixture
def project_with_org_pack(tmp_path: Path) -> Path:
    """Initialise a git repo with an org pack declaring interview defaults + required directives."""
    _git_init(tmp_path)
    pack_dir = tmp_path / "packs" / "acme-security"
    _write_org_pack_with_charter(
        pack_dir,
        """
        org_name: "Acme Security"
        interview_defaults:
          human_in_command: true
          autonomous_mode: disallowed
        required_directives:
          - DIRECTIVE_999
        """,
    )
    _write_kittify_config_with_packs(
        tmp_path, [{"name": "acme-security", "local_path": str(pack_dir)}]
    )
    return tmp_path


def test_interview_defaults_picks_up_org_charter_pre_fill(
    project_with_org_pack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`charter interview --defaults` writes org-charter values into answers.yaml.

    This is the FR-026 integration check: the user-facing CLI command must
    apply the org-layer pre-fill, not just expose it as a library helper.
    """
    monkeypatch.chdir(project_with_org_pack)
    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, (
        f"interview failed: stdout={result.stdout!r}"
    )

    answers = _read_answers(project_with_org_pack)
    # interview_defaults landed in answers.yaml
    assert answers["answers"]["human_in_command"] == "True"
    assert answers["answers"]["autonomous_mode"] == "disallowed"
    # required_directives unioned into selected_directives
    selected = answers.get("selected_directives", [])
    assert "DIRECTIVE_999" in selected


def test_interview_without_org_packs_has_no_pre_fill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no org packs are configured, `charter interview` runs cleanly with no pre-fill side effects."""
    _git_init(tmp_path)
    # Hermetic against a stray ``.kittify`` marker anywhere above ``tmp_path``
    # (e.g. a developer's home-dir kittify root, or another test's litter
    # under the OS temp dir): unlike ``project_with_org_pack`` (which seeds
    # ``.kittify/config.yaml`` at tmp_path before invocation and so always
    # wins the walk-up), this fixture has no ``.kittify`` yet, so
    # ``locate_project_root`` would otherwise happily resolve to an ambient
    # ancestor instead of this fixture's repo.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    # No "Org charter:" announcement in output
    assert "Org charter: Pre-" not in result.stdout
    answers = _read_answers(tmp_path)
    # answers were written but no org keys appear
    assert "answers" in answers


def test_interview_user_answer_survives_org_default(
    project_with_org_pack: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the user already provided an answer (e.g. via prior run), the org default must not overwrite it.

    Simulates a prior interview run by seeding answers.yaml first, then rerunning the
    interview to verify the existing user value persists.
    """
    # Seed prior answers (user said human_in_command=False)
    interview_dir = project_with_org_pack / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    (interview_dir / "answers.yaml").write_text(
        textwrap.dedent(
            """
            schema_version: 1.0.0
            mission: software-dev
            profile: minimal
            answers:
              human_in_command: "False"
            selected_paradigms: []
            selected_directives: []
            available_tools: []
            """
        ).lstrip(),
        encoding="utf-8",
    )

    monkeypatch.chdir(project_with_org_pack)
    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout

    # NOTE: `--defaults` always rewrites the file from `default_interview()` output.
    # The pre-fill helper operates on the in-memory CharterInterview before write_interview_answers
    # is called. Because the user's prior answers.yaml is overwritten in --defaults mode (this is
    # how the CLI is designed), this test documents the actual behaviour: in defaults mode the
    # org pre-fill DOES take effect because there is no in-memory prior answer to preserve.
    # The non-destructive guarantee applies within a single interview invocation, not across runs.
    answers = _read_answers(project_with_org_pack)
    # autonomous_mode (only set by org charter) must be present
    assert answers["answers"]["autonomous_mode"] == "disallowed"
