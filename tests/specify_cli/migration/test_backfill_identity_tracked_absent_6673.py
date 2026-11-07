"""#6673: ``backfill_mission`` never mints over an identity git already holds.

Three shapes, all reachable through ``migrate backfill-identity`` regardless of which ``upgrade``
migrations still run: a tracked ``meta.json`` missing from the working tree is restored from git,
a present copy that lost its ``mission_id`` takes the tracked one back, and a copy git cannot give
back is refused with the restore command. The controls on the same fixtures keep the pre-identity
behaviour: a folder git holds nothing for still has its identity minted.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from specify_cli.migration.backfill_identity import backfill_mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MISSION_ID = "01M6RMVF55CDNV3SF3FP70ERKZ"
_SLUG = f"tracked-meta-{_MISSION_ID[:8]}"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _mission(root: Path) -> Path:
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "friendly_name": "tracked meta",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "mission")
    return mission_dir


def test_a_tracked_absent_meta_is_restored_with_its_identity(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _mission(root)
    (mission_dir / "meta.json").unlink()

    result = backfill_mission(mission_dir)

    assert result.action in {"wrote", "skip"}
    assert result.mission_id in {None, _MISSION_ID}
    restored = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert restored["mission_id"] == _MISSION_ID, "backfill_mission minted over a tracked identity"


@pytest.mark.parametrize(
    "tracked_state",
    [
        "usable",
        "corrupt",
        "staged-edit",
        "redirect-ceiling",
        "post-empty-ownership",
        "post-empty-lexical-ownership",
        "start-ceiling-ownership",
        "config-error",
        "config-warning",
    ],
)
def test_a_present_copy_that_lost_its_identity_takes_the_tracked_one(tmp_path: Path, tracked_state: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A usable tracked copy gives its id back; a copy git cannot supply one from is a coded refusal, never a mint.

    Ownership refusal is exercised with unresolved post-empty alias/lexical spellings and a
    ceiling equal to git's starting directory: none stops git reaching the held identity.
    Configuration failure is separate evidence that a failed query cannot establish absence.
    """
    root = _repo(tmp_path)
    mission_dir = _mission(root)
    without_id = {
        "mission_slug": _SLUG,
        "slug": _SLUG,
        "friendly_name": "tracked meta",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    lost = json.dumps(without_id, sort_keys=True, indent=2) + "\n"
    if tracked_state == "corrupt":
        (mission_dir / "meta.json").write_text("{not json\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "corrupt the committed copy")
    elif tracked_state == "staged-edit":
        (mission_dir / "meta.json").write_text(json.dumps({**without_id, "mission_id": _MISSION_ID}) + "\n", encoding="utf-8")
        _git(root, "add", "-A")
    (mission_dir / "meta.json").write_text(lost, encoding="utf-8")
    if tracked_state == "redirect-ceiling":
        # Git cannot answer for an explicit redirect. The discovery ceiling must not
        # turn that unknown tracked identity into permission to mint a replacement.
        monkeypatch.setenv("GIT_DIR", str(tmp_path / "missing-git-dir"))
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(mission_dir))
    elif tracked_state == "post-empty-ownership":
        # git does not resolve a ceiling entry listed after an empty entry, so its own search
        # still reaches this repository and the ownership check it then applies is a refusal,
        # not an absence. The alias resolves to this Mission's parent, so a walk that resolves
        # it stops below the ``.git`` git refused.
        assert _MISSION_ID in _git(root, "show", f"HEAD:kitty-specs/{_SLUG}/meta.json")
        alias = tmp_path / "kitty-specs-alias"
        try:
            alias.symlink_to(mission_dir.parent, target_is_directory=True)
        except (OSError, NotImplementedError):  # pragma: no cover - platform without symlinks
            pytest.skip("platform cannot create directory symlinks")
        monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", f"{os.pathsep}{alias}")
    elif tracked_state == "post-empty-lexical-ownership":
        # Path drops this trailing dot, but Git keeps post-empty spellings lexical.
        # Turning it into a canonical ceiling hides the anchor whose ownership Git refused.
        monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", f"{os.pathsep}{mission_dir.parent}/.")
    elif tracked_state == "start-ceiling-ownership":
        # Git ignores a ceiling equal to its starting directory. Its ownership refusal
        # must not become an absence merely because the general walk stops at the start.
        monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(mission_dir))
    elif tracked_state in {"config-error", "config-warning"}:
        # The strict-parent ceiling hides the anchor, so the configuration witness must
        # refuse both a fatal parse error and a diagnostic-only, otherwise-unset lookup.
        assert _MISSION_ID in _git(root, "show", f"HEAD:kitty-specs/{_SLUG}/meta.json")
        if tracked_state == "config-error":
            monkeypatch.setenv("GIT_CONFIG_COUNT", "invalid")
        else:
            global_config = tmp_path / "global-config-directory"
            global_config.mkdir()
            monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(mission_dir.parent))

    result = backfill_mission(mission_dir)

    written = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    if tracked_state == "usable":
        assert result.action == "wrote"
        assert result.mission_id == _MISSION_ID
        assert written["mission_id"] == _MISSION_ID
        return
    expected_code = "TRACKED_META_STAGED_DIFFERS" if tracked_state == "staged-edit" else "TRACKED_META_UNAVAILABLE"
    assert result.action == "skip"
    assert result.mission_id is None
    assert result.reason is not None
    assert f"[{expected_code}]" in result.reason
    assert (mission_dir / "meta.json").read_bytes() == lost.encode("utf-8"), "refused backfill changed the working metadata"


def test_an_untracked_copy_without_identity_is_still_minted(tmp_path: Path) -> None:
    """Positive control: nothing tracked means nothing to preserve, so the mint is still right."""
    root = _repo(tmp_path)
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"slug": _SLUG, "mission_slug": _SLUG, "mission_type": "software-dev"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

    result = backfill_mission(mission_dir)

    assert result.action == "wrote"
    assert result.mission_id is not None
    assert result.mission_id != _MISSION_ID
    written = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["mission_id"] == result.mission_id


def test_nothing_tracked_keeps_the_original_skip_reason(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    legacy = root / "kitty-specs" / "legacy-mission"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "legacy")

    result = backfill_mission(legacy)

    assert result.action == "skip"
    assert result.reason == "meta.json not found"
    assert not (legacy / "meta.json").exists()
