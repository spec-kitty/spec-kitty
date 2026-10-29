"""The audit engine keeps its own Mission rule (#5875, FR-008, C-004).

``doctor identity`` reports a spec.md-only folder as ``residue``. The audit
engine does not: it decides Mission-ness with the looser ``is_mission_dir`` (a
tracked ``spec.md``, or any marker on a non-git root, makes a Mission), so such
a folder must keep its identity, prefix and selector findings there.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.audit import AuditOptions, run_audit


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _findings(repo: Path) -> dict[str, list[tuple[str, str, str | None, str | None]]]:
    report = run_audit(AuditOptions(repo_root=repo))
    return {m.mission_slug: [(f.code, str(f.severity), f.artifact_path, f.detail) for f in m.findings] for m in report.missions}


@pytest.mark.git_repo
def test_committed_spec_only_folder_keeps_identity_prefix_and_selector_findings(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "T")
    specs = tmp_path / "kitty-specs"
    (specs / "001-mission").mkdir(parents=True)
    (specs / "001-mission" / "meta.json").write_text(
        json.dumps({"mission_id": "01KNXQS9ATWWFXS3K5ZJ9E5008", "mission_slug": "001-mission", "mission_number": 1}),
        encoding="utf-8",
    )
    (specs / "001-spec-tracked").mkdir()
    (specs / "001-spec-tracked" / "spec.md").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "fixture")

    assert _findings(tmp_path) == {
        "001-mission": [
            ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '001' also matches: 001-spec-tracked"),
            ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '001' shared with: 001-spec-tracked"),
        ],
        "001-spec-tracked": [
            ("AMBIGUOUS_SELECTOR", "warning", "meta.json", "handle '001' also matches: 001-mission"),
            ("DUPLICATE_PREFIX", "warning", "meta.json", "prefix '001' shared with: 001-mission"),
            ("IDENTITY_MISSING", "error", "meta.json", "meta.json absent"),
        ],
    }


def test_spec_only_folder_on_a_non_git_root_keeps_identity_missing(tmp_path: Path) -> None:
    folder = tmp_path / "kitty-specs" / "002-spec-only"
    folder.mkdir(parents=True)
    (folder / "spec.md").write_text("x", encoding="utf-8")

    assert _findings(tmp_path) == {"002-spec-only": [("IDENTITY_MISSING", "error", "meta.json", "meta.json absent")]}
