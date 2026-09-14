"""Regression tests for ULID mission_id minting at creation time (T019 / FR-201..FR-206)."""

from __future__ import annotations

from contextlib import contextmanager
import json
import subprocess
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
from ulid import ULID

from specify_cli.core.mission_creation import create_mission_core
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CORE_MODULE = "specify_cli.core.mission_creation"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_git_repo(repo: Path) -> None:
    """Initialise a minimal git repo with .kittify and kitty-specs."""
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init", "--allow-empty"], cwd=repo, capture_output=True, check=True)
    # WP04 fail-closed follow-up: create_mission_core() hard-requires an
    # activated mission type; a bare git-init fixture never ran
    # `spec-kitty init`, so provision the same default charter surface here.
    provision_test_charter(repo)


def _mission_summary(slug: str) -> dict[str, str]:
    title = slug.replace("-", " ").strip() or "test mission"
    return {
        "friendly_name": title.title(),
        "purpose_tldr": f"Deliver {title} cleanly for the team.",
        "purpose_context": (
            f"This mission delivers {title} so product and engineering can move "
            "forward with a clear outcome and shared understanding."
        ),
    }


@contextmanager
def _patched_mission_creation_context(tmp_path: Path):
    """Patch side-effecting mission creation dependencies for identity tests."""
    with (
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=tmp_path),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
    ):
        yield


def _run_create(tmp_path: Path, slug: str) -> object:
    """Helper: call create_mission_core with standard mocks."""
    with _patched_mission_creation_context(tmp_path):
        return create_mission_core(tmp_path, slug, **_mission_summary(slug))


# ---------------------------------------------------------------------------
# T3.1 — mission_id minted at creation, ULID-shaped
# ---------------------------------------------------------------------------


def test_mission_id_minted_at_creation(tmp_path: Path) -> None:
    """create_mission_core writes a 26-char ULID mission_id to meta.json."""
    _init_git_repo(tmp_path)
    _run_create(tmp_path, "test-identity")

    mission_dir = next((tmp_path / "kitty-specs").iterdir())
    meta_path = mission_dir / "meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())

    assert "mission_id" in meta
    assert isinstance(meta["mission_id"], str)
    assert len(meta["mission_id"]) == 26, (
        f"Expected 26-char ULID, got {meta['mission_id']!r}"
    )
    # Parses without exception — proves it is a valid ULID
    ULID.from_str(meta["mission_id"])


def test_mission_id_present_in_result_meta(tmp_path: Path) -> None:
    """MissionCreationResult.meta contains mission_id."""
    _init_git_repo(tmp_path)
    result = _run_create(tmp_path, "test-meta-identity")

    assert "mission_id" in result.meta
    assert len(result.meta["mission_id"]) == 26
    ULID.from_str(result.meta["mission_id"])


# ---------------------------------------------------------------------------
# T3.2 — mission_id is NOT derived from prefix scan
# ---------------------------------------------------------------------------


def test_mission_id_is_not_derived_from_prefix_scan(tmp_path: Path) -> None:
    """Two missions with different numeric prefixes get different, independent ULIDs."""
    _init_git_repo(tmp_path)
    result_a = _run_create(tmp_path, "feature-alpha")
    result_b = _run_create(tmp_path, "feature-beta")

    id_a = result_a.meta["mission_id"]
    id_b = result_b.meta["mission_id"]

    assert id_a != id_b, "Two distinct missions must have different mission_ids"
    # Both must parse as valid ULIDs
    ULID.from_str(id_a)
    ULID.from_str(id_b)


# ---------------------------------------------------------------------------
# T3.3 — Concurrent creates do not collide
# ---------------------------------------------------------------------------


def test_concurrent_creates_no_collision(tmp_path: Path) -> None:
    """Spawning two threads each creating a different slug yields two distinct mission_ids."""
    _init_git_repo(tmp_path)
    results: list[dict] = []
    errors: list[Exception] = []

    def create_and_capture(slug: str) -> None:
        try:
            result = create_mission_core(tmp_path, slug, **_mission_summary(slug))
            results.append(result.meta)
        except Exception as exc:
            errors.append(exc)

    with _patched_mission_creation_context(tmp_path):
        t1 = threading.Thread(target=create_and_capture, args=("concurrent-alpha",))
        t2 = threading.Thread(target=create_and_capture, args=("concurrent-beta",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    assert not errors, f"Thread errors: {errors}"
    assert len(results) == 2
    id_0 = results[0]["mission_id"]
    id_1 = results[1]["mission_id"]
    assert id_0 != id_1, f"Collision detected: both missions got mission_id={id_0!r}"
    # Both must be valid ULIDs
    ULID.from_str(id_0)
    ULID.from_str(id_1)
