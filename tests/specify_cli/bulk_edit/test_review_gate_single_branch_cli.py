"""#7726 red-first, end to end: ``agent action review`` refuses a forbidden edit on ``single_branch``.

Before #7726 the bulk-edit review gate diffed ``lanes.json mission_branch .. review workspace
branch``; on ``single_branch`` both name the same branch, so it diffed ``X..X``, passed having
checked nothing, and ``agent action review`` went on to claim the work package.

This module deliberately imports no symbol #7726 introduced (only the shared single_branch
harness, unchanged by #7726), so it collects and runs on the pre-fix code and shows the red
there. The subprocess imports ``specify_cli`` from ``sys.path``: run it with
``PYTHONPATH=<checkout>/src`` so it exercises the checkout under test, not an installed copy.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.integration import single_branch_window_support as sb

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_HARNESS_VARIABLES = ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NON_INTERACTIVE", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS")

# serialized_keys is do_not_change: an edit of the existing ``config.yaml`` (which carries the term)
# is a violation.
_OCCURRENCE_MAP = """\
target:
  term: oldName
  operation: rename
categories:
  code_symbols:
    action: rename
  import_paths:
    action: rename
  filesystem_paths:
    action: rename
  serialized_keys:
    action: do_not_change
  cli_commands:
    action: rename
  user_facing_strings:
    action: rename
  tests_fixtures:
    action: rename
  logs_telemetry:
    action: rename
"""


def _bulk_edit_mission(base: Path, flavour: str) -> tuple[Path, str]:
    repo, slug = sb.build_template(base, commit_to_target=flavour == "ctt")
    feature_dir = repo / "kitty-specs" / slug
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["change_mode"] = "bulk_edit"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (feature_dir / "occurrence_map.yaml").write_text(_OCCURRENCE_MAP, encoding="utf-8")
    (repo / "config.yaml").write_text("oldName: true\n", encoding="utf-8")
    sb.git(repo, "add", "-A")
    sb.git(repo, "commit", "-qm", "test: declare the Mission bulk_edit")
    return repo, slug


@pytest.mark.parametrize("flavour", ["minted", "ctt"])
def test_agent_action_review_refuses_a_forbidden_edit_on_single_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flavour: str) -> None:
    """Red on main: the gate diffed ``X..X`` and ``agent action review`` went on to claim the WP."""
    for key in _HARNESS_VARIABLES:
        monkeypatch.delenv(key, raising=False)
    source, slug = _bulk_edit_mission(tmp_path / "template", flavour)
    repo = tmp_path / "repo"
    shutil.copytree(source, repo, symlinks=True)
    monkeypatch.chdir(repo)
    for key, value in sb.cli_env(tmp_path).items():
        if key.startswith(("HOME", "XDG_", "SPEC_KITTY_")):
            monkeypatch.setenv(key, value)
    m = sb.Mission(repo, slug, tmp_path)

    sb.claim(m, "WP01")
    sb.implement(m, "WP01")
    sb.commit_file(m, "config.yaml", "oldName: false\n", "feat(WP01): touch a do_not_change key")
    sb.emit(m, "WP01", "for_review", "alice", "--force", "--reason", "handed to review")

    proc = subprocess.run(
        [*sb._CLI, "agent", "action", "review", "WP01", "--agent", "bob", "--mission", m.slug],
        cwd=m.repo,
        env=m.env,
        capture_output=True,
        text=True,
        timeout=400,
    )
    output = " ".join((proc.stdout + "\n" + proc.stderr).split())

    assert proc.returncode != 0, output
    assert "config.yaml" in output, output
    assert "do_not_change" in output, output
