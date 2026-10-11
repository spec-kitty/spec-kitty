"""#5964 red-first: the 3.2.5 gitignore backfill must not untrack USER-authored team skills.

``AgentsSkillsGitignoreBackfillMigration`` adds ``.agents/skills/`` to ``.gitignore`` and
then runs ``git rm --cached`` over *everything* tracked under that prefix. That is correct
for the machine-local, spec-kitty-*projected* command skills (``.agents/skills/spec-kitty.*``),
whose ownership is recorded in ``.kittify/command-skills-manifest.json`` /
``.kittify/skills-manifest.json``. It is DATA LOSS for a team's own committed skill that
happens to live under the same prefix and is owned by NEITHER manifest: the migration stages
its deletion and the upgrade commit records it, so the team's reviewed content silently leaves
the tree (#5964).

This pins the invariant on real observable git state (``git ls-files`` / ``git status
--porcelain`` / the upgrade commit's own ``D`` entries), never on "a file was written". It
is RED at HEAD because the migration untracks the team path indiscriminately; WP02 scopes the
untrack to manifest-owned projected paths and turns it green.

Network-free: a throwaway ``git init`` repo built in ``tmp_path`` plus the real autocommit
selectors (``migration_index_untracks``) and the real upgrade-commit build
(``commit_touched_checkout``) — the exact seam the issue's rc6 / origin-main evidence used.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.skills import manifest_store
from specify_cli.skills.manifest import ManagedFileEntry, ManagedSkillManifest, save_manifest
from specify_cli.skills.manifest_store import ManifestEntry, SkillsManifest
from specify_cli.skills.ownership import is_projected_skills_path, manifest_owned_skills_paths
from specify_cli.upgrade.autocommit import (
    capture_upgrade_baseline,
    commit_touched_checkout,
    migration_index_untracks,
)
from specify_cli.upgrade.migrations.m_3_2_5_agents_skills_gitignore_backfill import (
    AgentsSkillsGitignoreBackfillMigration,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

# A user/team-authored skill under .agents/skills/ that spec-kitty did NOT project and that
# no manifest owns. Its name is not of the canonical ``spec-kitty.<command>`` shape.
_TEAM = ".agents/skills/team-review/SKILL.md"
_TEAM_BYTES = "# Team review skill\n\nOur own reviewed content.\n"
# A genuinely spec-kitty-projected command skill: canonical ``spec-kitty.*`` path, manifest-owned.
_PROJECTED = ".agents/skills/spec-kitty.implement/SKILL.md"
_PROJECTED_BYTES = "# spec-kitty.implement (projected)\n"


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "commit.gpgsign", "false")


def _ls_files(root: Path) -> set[str]:
    out = _git(root, "ls-files").stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def _porcelain(root: Path) -> list[str]:
    out = _git(root, "status", "--porcelain").stdout
    return [line for line in out.splitlines() if line.strip()]


def _staged_deletions(root: Path) -> set[str]:
    """Paths whose porcelain index column is ``D`` (a staged ``git rm --cached``)."""
    return {line[3:].strip() for line in _porcelain(root) if line[:1] == "D"}


def _head_deletions(root: Path) -> set[str]:
    """Paths deleted (``D``) by HEAD's own diff against its parent."""
    out = _git(root, "show", "--name-status", "--diff-filter=D", "--format=", "HEAD").stdout
    deletions: set[str] = set()
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if parts[0].startswith("D") and len(parts) >= 2:
            deletions.add(parts[1].strip())
    return deletions


def _build_repo_with_team_and_projected(root: Path) -> None:
    """A repo that committed one team-owned skill and one genuinely-projected command skill."""
    _init_repo(root)

    for rel, body in ((_TEAM, _TEAM_BYTES), (_PROJECTED, _PROJECTED_BYTES)):
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")

    # Record the projected command skill in command-skills-manifest.json (its ownership
    # authority). The team skill is recorded in NO manifest.
    manifest = SkillsManifest(
        entries=[
            ManifestEntry(
                path=_PROJECTED,
                content_hash=manifest_store.fingerprint_file(root / _PROJECTED),
                agents=("codex",),
                installed_at=now_utc_iso(),
                spec_kitty_version="3.2.5",
            )
        ]
    )
    manifest_store.save(root, manifest)

    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init (team skill + projected skill both committed)")


def test_team_skill_is_not_untracked_by_the_backfill(tmp_path: Path) -> None:
    """The team-owned, manifest-less skill must stay tracked; only the projected one is untracked."""
    root = tmp_path / "repo"
    _build_repo_with_team_and_projected(root)

    tracked_before = _ls_files(root)
    assert _TEAM in tracked_before, "fixture sanity: the team skill must start tracked"
    assert _PROJECTED in tracked_before, "fixture sanity: the projected skill must start tracked"

    migration = AgentsSkillsGitignoreBackfillMigration()
    assert migration.detect(root) is True
    result = migration.apply(root, dry_run=False)
    assert result.success is True

    staged_deletions = _staged_deletions(root)

    # The projected command skill IS untracked by the backfill (correct behaviour).
    assert _PROJECTED not in _ls_files(root), "the projected spec-kitty.implement skill must be untracked"
    assert _PROJECTED in staged_deletions, "fixture sanity: the projected skill is a staged deletion"

    # RED at HEAD: the migration also stages the team skill's deletion, so the following fail.
    assert _TEAM in _ls_files(root), (
        f"the user-authored team skill must stay git-tracked after the backfill (#5964); "
        f"tracked now: {sorted(p for p in _ls_files(root) if p.startswith('.agents/skills'))}"
    )
    assert _TEAM not in staged_deletions, f"the team skill must NOT be staged for deletion by the migration (#5964); staged deletions: {sorted(staged_deletions)}"


def test_team_skill_is_not_in_the_upgrade_commit_deletions(tmp_path: Path) -> None:
    """The upgrade commit the autocommit selectors build must not carry the team skill's deletion."""
    root = tmp_path / "repo"
    _build_repo_with_team_and_projected(root)

    baseline = capture_upgrade_baseline(root)
    assert baseline is not None

    migration = AgentsSkillsGitignoreBackfillMigration()
    assert migration.apply(root, dry_run=False).success is True

    # The selector that decides which staged deletions ride in the upgrade commit.
    index_untracks = {path.as_posix() for path in migration_index_untracks(root, baseline)}
    assert _PROJECTED in index_untracks, "fixture sanity: the projected skill is a migration untrack"
    # RED at HEAD: the team skill is selected into the upgrade commit's deletions too.
    assert _TEAM not in index_untracks, f"the team skill must NOT be selected into the upgrade commit's deletions (#5964); selected: {sorted(index_untracks)}"

    committed, _paths, _warning = commit_touched_checkout(root, baseline, "3.2.4", "3.2.5")
    assert committed is True, "the upgrade-commit build must have produced a commit"

    head_deletions = _head_deletions(root)
    assert _PROJECTED in head_deletions, "fixture sanity: the projected skill's deletion rode in the upgrade commit"
    # RED at HEAD: the team skill's deletion is recorded in the upgrade commit, so it leaves the tree.
    assert _TEAM not in head_deletions, f"the upgrade commit must NOT delete the user-authored team skill (#5964); commit deletions: {sorted(head_deletions)}"
    # Its bytes also remain on disk (the migration only ever does ``git rm --cached``).
    assert (root / _TEAM).read_text(encoding="utf-8") == _TEAM_BYTES


_PACK = ".agents/skills/acme-house-style/SKILL.md"


@pytest.mark.parametrize(
    ("path", "owned", "projected"),
    [
        pytest.param(_PROJECTED, set(), True, id="canonical-command-skill-by-pattern"),
        pytest.param(".agents/skills/spec-kitty.notacommand/SKILL.md", set(), False, id="unknown-spec-kitty-name"),
        pytest.param(_TEAM, set(), False, id="team-skill"),
        pytest.param(_PACK, {_PACK}, True, id="manifest-owned-pack-skill"),
        pytest.param(".agents/skills/spec-kitty.implement/sub/file.md", set(), False, id="nested-under-canonical-dir"),
        pytest.param(".agents\\skills\\spec-kitty.implement\\SKILL.md", set(), False, id="windows-backslash-path-fails-closed"),
    ],
)
def test_projected_skills_path_selection(path: str, owned: set[str], projected: bool) -> None:
    assert is_projected_skills_path(path, owned) is projected


def test_both_manifests_contribute_owned_paths(tmp_path: Path) -> None:
    manifest_store.save(
        tmp_path,
        SkillsManifest(
            entries=[
                ManifestEntry(
                    path=_PROJECTED,
                    content_hash="0" * 64,
                    agents=("codex",),
                    installed_at=now_utc_iso(),
                    spec_kitty_version="3.2.5",
                )
            ]
        ),
    )
    save_manifest(
        ManagedSkillManifest(
            entries=[
                ManagedFileEntry(
                    skill_name="acme-house-style",
                    source_file="SKILL.md",
                    installed_path=_PACK,
                    installation_class="shared-root-capable",
                    agent_key="codex",
                    content_hash="sha256:" + "0" * 64,
                    installed_at=now_utc_iso(),
                    origin="pack",
                )
            ]
        ),
        tmp_path,
    )

    assert manifest_owned_skills_paths(tmp_path) == {_PROJECTED, _PACK}


def test_corrupt_command_skills_manifest_is_fail_closed_toward_preservation(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "command-skills-manifest.json").write_text("{ not json", encoding="utf-8")

    owned = manifest_owned_skills_paths(tmp_path)

    assert owned == set()
    assert is_projected_skills_path(_TEAM, owned) is False
