"""record-analysis --report-only with an undeclared target on a non-primary branch (#6142).

Regression for the landing-review finding on the declaration-first entry: a Mission
whose ``meta.json`` has no ``target_branch``, in a repository with no ``origin/HEAD``,
where ``main`` exists but the checkout stands on ``release-2``. The entry answered
``main`` while the placement seam answered ``release-2``, so
``record_report_transaction`` refused with "Analysis report placement changed before
preflight". The command must hand the transaction the placement authority's answer and
record the report. Drives the REAL resolver (no stub of the entry or the seam).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.commands.agent.mission import app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

SLUG = "undeclared-target-01M38YDY"
REPORT = f"kitty-specs/{SLUG}/analysis-report.md"
BODY = "---\nschema: analysis-findings/v1\nfindings: []\ncounts: {critical: 0, high: 0, medium: 0, low: 0, info: 0}\n---\n\n# Analysis\nNo findings.\n"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from specify_cli.runtime import resolver

    monkeypatch.setattr(resolver, "get_kittify_home", lambda: tmp_path / "runtime-home")
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    charter = root / ".kittify/charter"
    charter.mkdir(parents=True)
    (root / ".kittify/config.yaml").write_text("charter: .kittify/charter/charter.yaml\n")
    (charter / "charter.yaml").write_text("mission_type_activations: [software-dev]\n")
    mission = root / "kitty-specs" / SLUG
    (mission / "tasks").mkdir(parents=True)
    for name in ("spec.md", "plan.md", "tasks.md"):
        (mission / name).write_text(f"# {name}\nMaterial definition.\n")
    (mission / "tasks/WP01-proof.md").write_text("---\nwork_package_id: WP01\ntitle: Proof\n---\nDefinition.\n")
    # No ``target_branch``: the undeclared shape.
    (mission / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M38YDY000000000000000001",
                "mission_slug": SLUG,
                "slug": SLUG,
                "mission_type": "software-dev",
                "topology": "single_branch",
            }
        )
    )
    git(root, "add", ".")
    git(root, "commit", "-qm", "seed")
    git(root, "checkout", "-q", "-b", "release-2")
    monkeypatch.chdir(root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    return root.resolve()


def test_report_only_hands_the_transaction_the_placement_target(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.git.report_transaction as report_transaction

    real = report_transaction.record_report_transaction
    seen: list[str] = []

    def _spy(**kwargs: Any) -> Any:
        seen.append(kwargs["target_branch"])
        return real(**kwargs)

    monkeypatch.setattr(report_transaction, "record_report_transaction", _spy)
    expected = placement_seam(repo, SLUG).write_target(MissionArtifactKind.ANALYSIS_REPORT).ref

    result = CliRunner().invoke(app, ["record-analysis", "--mission", SLUG, "--json", "--report-only"], input=BODY)

    assert "placement changed" not in result.output, result.output
    assert seen == [expected]
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["commit_status"] == "committed"
    assert git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() == [REPORT]
