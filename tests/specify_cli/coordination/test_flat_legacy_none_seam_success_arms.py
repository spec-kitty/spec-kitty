"""#2650 (WP04) -- FR-006 characterization gate, real-git slice.

Extracted from ``test_partition_authority_characterization.py`` (which stays a
pure fast/unit gate) because this class drives a REAL ``git`` repo via
``subprocess`` and therefore must carry the ``git_repo`` marker (and must NOT
carry ``fast``) per the marker-correctness arch gate
(``tests/architectural/test_pytest_marker_correctness.py``). CI selects it with
``-m git_repo``.

The invariant it pins (INV-7, re-keyed by #5232): an unresolved placement with
no coordination ref on a flat mission -- NO ``coordination_branch`` in
``meta.json`` at all -- reaches the flat success arm and commits once to the
planning branch, not WP01's (#2648) narrow-triple fail-close. An unresolved
placement is NOT unconditionally degenerate (the #2463 guard).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


class TestFlatLegacyNoneAtSeamReachesSuccessArms:
    """T017 -- confirm WP01's (#2648) fail-close scope is the NARROW triple
    only. A real flat/legacy mission's unresolved placement with no
    coordination ref -- NO ``coordination_branch`` in meta.json at all --
    must still reach the flat SUCCESS arm and commit once to the planning
    branch, not the narrow-triple fail-close (INV-7).
    """

    @staticmethod
    def _git(repo: Path, *args: str) -> str:
        import subprocess

        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True, text=True
        ).stdout.strip()

    def _init_repo(self, repo: Path, *, branch: str) -> None:
        repo.mkdir()
        self._git(repo, "init", "-q", "-b", branch)
        self._git(repo, "config", "user.email", "t@example.com")
        self._git(repo, "config", "user.name", "Test")
        self._git(repo, "config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        self._git(repo, "add", "seed.txt")
        self._git(repo, "commit", "-q", "-m", "initial")

    def test_flat_legacy_placement_ref_none_commits_successfully_755(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        from specify_cli.cli.commands.implement_planning_commit import _commit_planning_artifacts_transaction
        from specify_cli.coordination.planning_commit import PlanningPlacement

        planning_branch = "mission/2650-wp04-flat-legacy-demo"
        repo = tmp_path / "repo"
        self._init_repo(repo, branch=planning_branch)

        mission_slug = "wp04-flat-legacy-demo"
        feature_dir = repo / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        # No "coordination_branch" key at all -- a genuinely flat/legacy
        # mission (not merely a coord mission with an unprotected branch).
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": "01J9WP04FLATLEGACYXXXXXXXX",
                    "mission_slug": mission_slug,
                    "mid8": "01J9WP04",
                    "mission_type": "software-dev",
                    "target_branch": planning_branch,
                    "created_at": "2026-07-15T00:00:00+00:00",
                    "friendly_name": "WP04 flat/legacy None-at-seam",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")

        calls: list[tuple[str, list[str]]] = []

        class _FakeTxn:
            def __init__(self, destination_ref: str) -> None:
                self._destination_ref = destination_ref
                self._paths: list[str] = []

            def __enter__(self) -> _FakeTxn:
                return self

            def __exit__(self, *_exc: object) -> None:
                calls.append((self._destination_ref, list(self._paths)))

            def write_artifact(self, repo_path: Path, _content: bytes) -> None:
                self._paths.append(repo_path.as_posix())

            def commit(self, _msg: str) -> None:
                return None

            def commit_idempotent(self, _msg: str) -> None:
                # write-path-integrity WP02 switched the production commit call
                # from ``txn.commit`` to ``txn.commit_idempotent`` (FR-001 crash-
                # recovery re-drive); the fake mirrors that so this flat/legacy
                # 755-arm characterization exercises the same seam (WP04 fold).
                return None

        class _FakeBookkeepingTransaction:
            @classmethod
            def acquire(cls, **kwargs: object) -> _FakeTxn:
                return _FakeTxn(str(kwargs["destination_ref"]))

        monkeypatch.setattr(
            "specify_cli.coordination.transaction.BookkeepingTransaction",
            _FakeBookkeepingTransaction,
        )

        spec_rel = f"kitty-specs/{mission_slug}/spec.md"

        # NOT the narrow triple: no coordination ref at all -- must not raise.
        _commit_planning_artifacts_transaction(
            repo_root=repo,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            planning_branch=planning_branch,
            files_to_commit=[spec_rel],
            commit_msg="chore: flat/legacy None-at-seam characterization",
            placement=PlanningPlacement(resolved=False, ref=None, coordination_ref=None),
        )

        assert calls == [(planning_branch, [spec_rel])], (
            "a flat/legacy mission's unresolved placement with no coordination ref "
            "must reach the flat SUCCESS arm, not the narrow-triple fail-close"
        )
