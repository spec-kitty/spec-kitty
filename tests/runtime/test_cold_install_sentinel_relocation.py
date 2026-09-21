"""Cold-install sentinel relocation (#4756, WP02, FR-002/003/011).

``_cold_install_sentinel`` used to place its lock file under the WORLD-SHARED
``tempfile.gettempdir()``, keyed by a deterministic hash of the anchor path --
a location AND filename any other local user could predict and pre-empt, and
whose parent directory was created by a bare ``mkdir(parents=True,
exist_ok=True)`` that never hardened its mode. This module proves the fix:
the RESOLVED sentinel path routes through a SIBLING of the per-user runtime
state root (``~/.spec-kitty-cold-install``, next to ``~/.spec-kitty``, never
``$TMPDIR`` and never NESTED inside the runtime root itself -- see
``_cold_install_sentinel``'s docstring for why nesting would corrupt
``assess_runtime``'s own drift tracking on a genuinely cold install) --
asserted on the resolved path, not a string check -- with its parent
directory hardened to ``0o700`` by ``kernel.locks``' ``_ensure_dir`` (the
canonical authority, not a second hand-rolled ``mkdir(0700)``), and that a
symlink planted at the resolved sentinel path -- exercised through the REAL
production cold-install entry point (``recheck_assets`` /
``_cold_install_sentinel``, never a reconstructed open) -- leaves the
victim's bytes untouched and the acquisition refuses.

**Honest red/green note on the symlink-plant assertion (T006):** the
plant-at-final-path scenario is ALREADY refused before this WP's relocation
change, because WP01's ``kernel.locks``/``kernel.no_follow`` O_NOFOLLOW
protection covers this call site regardless of the sentinel's directory --
verified empirically by running this exact test against the pre-relocation
``_cold_install_sentinel`` (captured in the WP02 handoff note). WP02 is
explicit defense-in-depth layered on top of that protection (the WP text:
"Pairs with WP01's O_NOFOLLOW for defense-in-depth") -- it closes the
WORLD-WRITABLE ancestry (so a different local user cannot even attempt a
plant at the un-relocated path) and the mode-hardening bug the bare
``mkdir(exist_ok=True)`` caused (see ``TestSentinelRelocatedToPerUserRuntimeRoot``
below, both genuinely RED on today's ``tempfile.gettempdir()``-based
sentinel -- confirmed by running this module before the fix).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import specify_cli.runtime.asset_preparation as ap
import specify_cli.runtime.bootstrap as bootstrap
from kernel.no_follow import NoFollowPathError
from kernel.paths import get_runtime_state_root
from specify_cli.runtime.bootstrap import assess_runtime
from specify_cli.tool_surface.operations import (
    FileState,
    OperationRoot,
    OwnershipProof,
    PhysicalEffect,
)

if TYPE_CHECKING:
    from specify_cli.tool_surface.operations import OwnerAssessment

pytestmark = [pytest.mark.unit, pytest.mark.fast]

FAKE_VERSION = "99.0.0-test"
_VICTIM_BYTES = b"do not disclose -- attacker-chosen victim content\n"


@pytest.fixture()
def fake_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal global asset tree so ``assess_runtime()`` reports a cold install."""
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")
    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")
    (pkg_root / "AGENTS.md").write_text("# Agents")
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


@pytest.fixture()
def cold_assessment(
    canonical_home: None,
    fake_assets: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> OwnerAssessment:
    """A real cold-install ``OwnerAssessment`` (effects present, no lock files yet)."""
    monkeypatch.setattr(bootstrap, "_get_cli_version", lambda: FAKE_VERSION)
    assessment = assess_runtime()
    assert assessment.effects, "setup guard: must be a cold install"
    prepared = assessment.prepared
    assert all(not p.exists() for p in prepared.lock_paths), "setup guard: cold install has no owner lock files yet"
    return assessment


class TestSentinelRelocatedToPerUserRuntimeRoot:
    """T007: the RESOLVED sentinel path is asserted under the per-user
    runtime root, never machine-shared temp -- not a string check."""

    def test_sentinel_path_resolves_under_runtime_state_root_not_tempdir(
        self,
        canonical_home: None,
        tmp_path: Path,
    ) -> None:
        anchor = tmp_path / "anchor"
        anchor.mkdir()

        sentinel = ap._cold_install_sentinel(anchor)
        resolved = sentinel.resolve()

        # A SIBLING of the per-user runtime root (never a child of it -- see
        # _cold_install_sentinel's docstring for why nesting under the home
        # root itself would corrupt assess_runtime's own drift tracking),
        # sharing its parent, which is always the per-user root (the real
        # $HOME, or a caller-supplied SPEC_KITTY_HOME's own parent).
        runtime_root = get_runtime_state_root().resolve()
        assert runtime_root.parent in resolved.parents, f"{resolved} must resolve under the per-user runtime root's parent {runtime_root.parent}"
        assert runtime_root not in (resolved, *resolved.parents), "sentinel must never nest INSIDE the runtime state root itself"

        # The pre-fix, world-shared location this sentinel used to resolve
        # under. A blanket "not under /tmp" check would be a false positive
        # in this very test process, since pytest's own isolated home lives
        # under /tmp too -- assert against the SPECIFIC retired shape instead.
        legacy_shared_dir = (Path(tempfile.gettempdir()) / "spec-kitty-cold-install").resolve()
        assert legacy_shared_dir not in (resolved, *resolved.parents), "sentinel must never resolve under the retired world-shared machine temp dir"

    @pytest.mark.skipif(os.name == "nt", reason="POSIX mode bits are not meaningful on Windows")
    def test_sentinel_parent_dir_is_hardened_to_0700_via_production_acquisition(
        self,
        cold_assessment: OwnerAssessment,
    ) -> None:
        prepared = cold_assessment.prepared
        sentinel = ap._cold_install_sentinel(prepared.anchor)
        assert not sentinel.parent.exists(), "setup guard: sentinel parent must not pre-exist"

        with ap.recheck_assets(cold_assessment):
            pass

        mode = sentinel.parent.stat().st_mode & 0o777
        assert mode == 0o700, f"sentinel parent dir must be hardened to 0o700 by kernel.locks, got {oct(mode)}"


class TestColdInstallSentinelSymlinkPlant:
    """T006: symlink-plant on the sentinel path via the REAL production
    cold-install entry point -- not a re-implementation of the open."""

    def test_planted_symlink_at_sentinel_path_leaves_victim_untouched_and_refuses(
        self,
        cold_assessment: OwnerAssessment,
        tmp_path: Path,
    ) -> None:
        prepared = cold_assessment.prepared
        sentinel = ap._cold_install_sentinel(prepared.anchor)

        victim = tmp_path / "victim-secret.txt"
        victim.write_bytes(_VICTIM_BYTES)

        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.symlink_to(victim)

        with pytest.raises(NoFollowPathError), ap.recheck_assets(cold_assessment):
            pytest.fail("cold-install acquisition must not succeed against a symlinked sentinel path")

        assert victim.read_bytes() == _VICTIM_BYTES, "victim file must be byte-for-byte unchanged"


class TestWriteAssetExistingDirectoryTolerance:
    """WP02 review-cycle-2 residual (#4756): the relocation moved the
    cold-install sentinel to a SIBLING of the per-user runtime state root
    (see ``_cold_install_sentinel``'s docstring), which exposed a
    same-process staleness race for callers of ``apply_assets`` outside the
    #4017 re-assess-under-lock seam -- a concurrent creator (this exact
    sentinel's own ``kernel.locks`` acquisition, or a benign peer) can
    materialize an ordinary directory at a "create" write's destination
    between the plan snapshot and this write. ``_write_asset`` tolerates
    ONLY that exact case (``FileExistsError`` + an ordinary, already-present
    directory); the ``is_symlink() or not is_dir()`` guard still refuses --
    no symlink-follow is reintroduced. Both branches were previously
    uncovered; these tests drive ``_write_asset`` directly (the real
    production function, not a re-implementation) to prove reachability and
    security-preservation.
    """

    @staticmethod
    def _directory_create_write(tmp_path: Path, name: str, *, mode: int) -> ap.AssetWrite:
        root = OperationRoot("test_owner", "global", tmp_path)
        effect = PhysicalEffect(
            owner="test_owner",
            phase="global_bootstrap",
            root=root,
            path=name,
            action="create",
            before=FileState("absent"),
            after=FileState("directory", mode=mode),
            reason="test-directory-create",
            ownership=(OwnershipProof("managed_path", "test_owner:directory"),),
            logical_owners=("test_owner",),
        )
        return ap.AssetWrite(effect, None)

    def test_write_asset_tolerates_already_materialized_ordinary_directory(
        self,
        tmp_path: Path,
    ) -> None:
        write = self._directory_create_write(tmp_path, "materialized-dir", mode=0o700)
        destination = write.effect.destination
        # Simulate a concurrent creator (e.g. this exact cold-install
        # sentinel's own kernel.locks acquisition, per _write_asset's
        # docstring) having already materialized an ORDINARY directory at
        # this path between this plan's snapshot and this write -- the
        # FileExistsError branch under test.
        destination.mkdir(mode=0o755)
        assert destination.is_dir() and not destination.is_symlink(), "setup guard: pre-existing plain directory"

        ap._write_asset(write)  # must NOT raise -- the tolerated race

        assert destination.is_dir() and not destination.is_symlink()
        if os.name != "nt":
            mode = destination.stat().st_mode & 0o777
            assert mode == 0o700, f"chmod must still apply to the tolerated pre-existing directory, got {oct(mode)}"

    def test_write_asset_refuses_symlink_planted_at_destination(
        self,
        tmp_path: Path,
    ) -> None:
        # The victim is itself a DIRECTORY (not a file) so that
        # ``path.is_dir()`` alone -- which follows a symlink to a real
        # directory -- would report True and (wrongly) tolerate the plant if
        # the ``is_symlink()`` half of the guard were ever dropped; only the
        # ``is_symlink()`` check on its own catches that case, proving this
        # test actually exercises it rather than the ``not is_dir()`` half.
        victim_dir = tmp_path / "victim-dir"
        victim_dir.mkdir(mode=0o700)
        victim_file = victim_dir / "secret.txt"
        victim_file.write_bytes(_VICTIM_BYTES)
        victim_mode_before = victim_dir.stat().st_mode & 0o777

        write = self._directory_create_write(tmp_path, "planted-dir", mode=0o755)
        destination = write.effect.destination
        destination.symlink_to(victim_dir)

        with pytest.raises(FileExistsError):
            ap._write_asset(write)  # must still refuse -- no symlink-follow

        assert destination.is_symlink(), "the planted symlink itself must be left untouched"
        assert victim_file.read_bytes() == _VICTIM_BYTES, "victim directory's contents must be byte-for-byte unchanged"
        assert (victim_dir.stat().st_mode & 0o777) == victim_mode_before, "victim directory's mode must be untouched -- no chmod through the symlink"
