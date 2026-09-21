"""WP07 / #4721 -- prompt temp dir per-user, no-follow, non-world-readable.

``runtime.next._tmp_namespace.prompt_tmp_dir`` used to root every prompt
writer at the flat, world-shared, predictable
``tempfile.gettempdir()/spec-kitty-prompts/<sha>`` (mode 0755, default
umask) -- a *distinct* instance of the #4756 world-shared-predictable-temp
class (folded in fully per the operator decision). Any local user could:

- pre-create or deny that shared directory ahead of this user (cross-user
  DoS -- SC-006), because the root was shared by every user on the box; and
- read world-readable (0644-ish) prompt files that may carry the full WP
  prompt / mission context (information disclosure -- SC-005).

This module proves the fix closes BOTH facets with assertions, not a note:

- DoS facet: :func:`prompt_tmp_dir` now resolves under the PER-USER runtime
  root (``~/.spec-kitty``, via ``kernel.paths.get_runtime_state_root`` --
  the pure resolver ``specify_cli.paths.get_runtime_root().base`` mirrors),
  isolated per-test via the canonical ``SPEC_KITTY_HOME`` owner fixture
  ``canonical_home`` -- never the legacy shared ``gettempdir()`` root.
- Info-disclosure facet: prompt files are written through
  :func:`write_prompt_file`, which routes through WP01's canonical
  ``kernel.no_follow.open_no_follow`` primitive at mode ``0600`` -- never
  group/other readable -- and refuses (rather than follows) a symlink
  planted at the prompt path.
"""

from __future__ import annotations

import stat
import tempfile
from pathlib import Path

import pytest

from kernel.no_follow import NoFollowPathError
from kernel.paths import get_runtime_state_root
from runtime.next._tmp_namespace import (
    SPEC_KITTY_PROMPT_NAMESPACE,
    prompt_tmp_dir,
    write_prompt_file,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_VICTIM_BYTES = b"do not disclose -- attacker-chosen victim content\n"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# ---------------------------------------------------------------------------
# DoS facet (SC-006): per-user isolation, never the shared gettempdir() root
# ---------------------------------------------------------------------------


class TestDosFacetPerUserIsolation:
    """Cross-user DoS: another local user can no longer plant/deny the
    prompt namespace ahead of this one, because it is no longer a shared
    root -- it is rooted under this user's own runtime home."""

    def test_prompt_dir_resolves_under_per_user_runtime_home(self, canonical_home: None, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        # ``canonical_home`` sets ``SPEC_KITTY_HOME`` to ``tmp_path / "home"`` --
        # ``get_runtime_state_root`` uses an explicit ``SPEC_KITTY_HOME`` VERBATIM
        # as the runtime root (no further ``.spec-kitty`` suffix; that suffix is
        # only appended in the ``Path.home()`` fallback branch).
        isolated_home = tmp_path / "home"

        result = prompt_tmp_dir(repo_root)

        assert result.is_relative_to(isolated_home), (
            f"{result} must resolve under the per-user runtime root {isolated_home} "
            "(SPEC_KITTY_HOME) -- the DoS facet is only closed once the root is "
            "per-user, not shared"
        )

    def test_prompt_dir_resolves_under_home_dot_spec_kitty_without_an_explicit_override(self, tmp_path: Path) -> None:
        """Without an explicit ``SPEC_KITTY_HOME`` override, the fallback branch
        appends ``.spec-kitty`` onto ``Path.home()`` -- the autouse per-worker
        HOME isolation (WP04) means ``Path.home()`` here is already this test's
        isolated fake home, never the developer's real ``$HOME``."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        result = prompt_tmp_dir(repo_root)

        assert result.is_relative_to(Path.home() / ".spec-kitty"), f"{result} must resolve under ~/.spec-kitty (isolated HOME); got {result}"

    def test_prompt_dir_is_not_the_legacy_shared_gettempdir_root(self, canonical_home: None, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        legacy_shared_root = Path(tempfile.gettempdir()) / SPEC_KITTY_PROMPT_NAMESPACE

        result = prompt_tmp_dir(repo_root)

        assert not result.is_relative_to(legacy_shared_root), (
            f"{result} must not fall under the retired world-shared root {legacy_shared_root} "
            "-- that shared, predictable root is exactly the cross-user DoS surface this WP closes"
        )

    def test_prompt_dir_is_created_owner_only(self, canonical_home: None, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        result = prompt_tmp_dir(repo_root)

        assert _mode(result) == 0o700, f"prompt dir {result} must be owner-only (0700); got {oct(_mode(result))}"

    def test_prompt_dir_first_run_hardens_the_runtime_root_not_just_the_leaf(self, canonical_home: None, tmp_path: Path) -> None:
        """WP07 cycle-2 / FR-011 residual (#4721): on a FRESH machine with no
        prior credential write, ``prompt_tmp_dir`` must not leave the runtime
        ROOT (``get_runtime_state_root()``) at the ambient umask (0755) while
        only chmod'ing its own leaf subdir. Before the fold, ``mkdir(parents=True,
        exist_ok=True)`` created any missing ancestor -- including the root --
        at the ambient umask, and only the leaf was ever re-chmod'd; a
        prompt-only workload (this test's exact shape: no credential write
        precedes the call) left the root at whatever mode it was already at.
        Red before the fold, green after.

        The ``canonical_home`` fixture pre-creates the isolated home directory
        (unrelated to this fold -- it needs somewhere to point
        ``SPEC_KITTY_HOME`` at) at the ambient umask, never ``0700`` -- this
        test's own precondition assertion below confirms that starting point
        so the later 0700 assertion is proof of the fold, not an accident of
        fixture setup.
        """
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        root = get_runtime_state_root()
        assert root.is_dir(), "precondition: canonical_home already created the isolated runtime root"
        assert _mode(root) != 0o700, (
            f"precondition: runtime root {root} must start at the fixture's ambient (non-0700) mode "
            f"for this test to prove prompt_tmp_dir() is what hardens it; got {oct(_mode(root))}"
        )

        prompt_tmp_dir(repo_root)

        assert _mode(root) == 0o700, f"runtime root {root} must be owner-only (0700) after a prompt-only first run; got {oct(_mode(root))}"


# ---------------------------------------------------------------------------
# Info-disclosure facet (SC-005): prompt files never world- or group-readable
# ---------------------------------------------------------------------------


class TestInfoDisclosureFacetFileMode:
    """Prompt content (often the full WP prompt / mission context) must
    never be group- or other-readable."""

    def test_write_prompt_file_creates_owner_only_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "prompt.md"

        write_prompt_file(path, "prompt content")

        assert _mode(path) == 0o600, f"{path} must be mode 0600; got {oct(_mode(path))}"

    def test_write_prompt_file_writes_content(self, tmp_path: Path) -> None:
        path = tmp_path / "prompt.md"

        write_prompt_file(path, "prompt content")

        assert path.read_text(encoding="utf-8") == "prompt content"

    def test_write_to_temp_consumer_produces_owner_only_mode(self, tmp_path: Path) -> None:
        """``prompt_builder._write_to_temp`` writes the actual WP prompt --
        the highest-value target for #4721's info-disclosure facet. It must
        route through :func:`write_prompt_file`, not a bare
        ``Path.write_text`` (mode ~0644 under a typical umask)."""
        from runtime.next.prompt_builder import _write_to_temp

        path = _write_to_temp(
            "implement",
            "WP07",
            "wp prompt content",
            agent="claude",
            mission_slug="042-feat",
            repo_root=tmp_path,
        )
        try:
            assert _mode(path) == 0o600, f"{path} must be mode 0600; got {oct(_mode(path))}"
        finally:
            path.unlink(missing_ok=True)

    def test_write_prompt_to_file_consumer_produces_owner_only_mode(self, tmp_path: Path) -> None:
        """``workflow_executor.write_prompt_to_file`` writes the
        implement/review prompt handed to the agent -- must also route
        through :func:`write_prompt_file`."""
        from specify_cli.cli.commands.agent.workflow_executor import write_prompt_to_file

        path = write_prompt_to_file("implement", "042-feat", "WP07", "full prompt content", repo_root=tmp_path)
        try:
            assert _mode(path) == 0o600, f"{path} must be mode 0600; got {oct(_mode(path))}"
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# T023 -- red-first symlink-plant: refused, victim bytes intact
# ---------------------------------------------------------------------------


class TestSymlinkPlantRefused:
    def test_write_prompt_file_on_planted_symlink_refuses_and_leaves_victim_untouched(self, tmp_path: Path) -> None:
        victim = tmp_path / "victim-secret.txt"
        victim.write_bytes(_VICTIM_BYTES)
        prompt_path = tmp_path / "spec-kitty-implement-042-feat-WP01.md"
        prompt_path.symlink_to(victim)

        with pytest.raises(NoFollowPathError):
            write_prompt_file(prompt_path, "attacker-controlled prompt content")

        assert victim.read_bytes() == _VICTIM_BYTES, "victim file must be byte-for-byte unchanged"

    def test_write_prompt_file_on_planted_symlink_leaves_the_symlink_unfollowed(self, tmp_path: Path) -> None:
        victim = tmp_path / "victim-secret.txt"
        victim.write_bytes(_VICTIM_BYTES)
        prompt_path = tmp_path / "spec-kitty-review-042-feat-WP02.md"
        prompt_path.symlink_to(victim)

        with pytest.raises(NoFollowPathError):
            write_prompt_file(prompt_path, "attacker-controlled prompt content")

        assert prompt_path.is_symlink(), "the planted symlink itself must be left in place, unfollowed"
