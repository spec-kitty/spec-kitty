"""Red-first C/D diagnosability tests (WP03 / T017, mission
``meta-json-fail-closed-routing-01KZPJ1F``).

Sites **C** (``implement_cores._is_self_write_only_diff`` -- the worktree
``meta.json`` read at ``implement_cores.py``) and **D**
(``implement_cores._committed_meta_mapping`` -- the ``GitPort.show_blob`` bytes)
route their ``meta.json`` decode onto the kernel L1 authority
(``kernel.meta_decode.decode_meta``, fail-closed). This module pins the
post-routing contract per site (FR-003/FR-005/FR-007, NFR-005):

* **corrupt** bytes -> the shared :class:`MetaDecodeError` whose message names
  ``meta.json`` (the diagnosable failure that replaces the former silent
  ``None`` / ``return False``);
* **missing / empty / whitespace-only** -> the benign pre-routing outcome is
  preserved (``None`` at site D, ``False`` at site C) -- empty is NOT folded
  into the malformed channel (C-010 / FR-005);
* **valid** -> the site's pre-routing verdict is unchanged (behavior-preserving
  happy path, FR-005).

These are **unit** tests: NO ``git_repo`` marker. Site D injects the
``GitPort`` fake (``implement_cores`` defaults its ``git`` parameter to the
real subprocess port; the fake is the documented unit seam); site C reads an
on-disk ``tmp_path`` file. Captured **red** against the pre-routing tree (the
routing commit follows this test's commit) -- pre-routing, corrupt input is
silently absorbed and every ``pytest.raises(MetaDecodeError)`` below fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.meta_decode import MetaDecodeError
from specify_cli.cli.commands.implement_cores import (
    _committed_meta_mapping,
    _is_self_write_only_diff,
)

pytestmark = [pytest.mark.unit]

_META_REL = "kitty-specs/m/meta.json"
_CORRUPT_JSON = b"{not valid json"
_INVALID_UTF8 = b"\xff\xfe\x00"
_NON_OBJECT = b"[1, 2, 3]"


class _FakeGitPort:
    """In-memory ``GitPort`` -- no subprocess, no real repository."""

    def __init__(self, *, blobs: dict[tuple[str, str], bytes | None] | None = None) -> None:
        self._blobs = blobs or {}

    def status_entries(self, repo_root: Path, target: Path) -> tuple[()]:  # pragma: no cover - unused here
        return ()

    def show_blob(self, repo_root: Path, ref: str, repo_rel_path: str) -> bytes | None:
        return self._blobs.get((ref, repo_rel_path))


def _write_meta(tmp_path: Path, raw: bytes) -> Path:
    """Materialize ``kitty-specs/m/meta.json`` on disk with *raw* bytes."""
    meta_path = tmp_path / _META_REL
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_bytes(raw)
    return meta_path


# ---------------------------------------------------------------------------
# Site D -- ``_committed_meta_mapping`` (GitPort.show_blob bytes)
# ---------------------------------------------------------------------------


class TestSiteDCommittedMetaMapping:
    @pytest.mark.parametrize("blob", [_CORRUPT_JSON, _INVALID_UTF8, _NON_OBJECT])
    def test_corrupt_committed_blob_raises_naming_meta_json(self, tmp_path: Path, blob: bytes) -> None:
        """FR-007: a present-but-corrupt committed blob fails loud with the
        shared typed error naming ``meta.json`` (the ``ref:path`` blob spec),
        not the former silent ``None``."""
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): blob})
        with pytest.raises(MetaDecodeError, match="meta.json"):
            _committed_meta_mapping(tmp_path, _META_REL, None, git=fake)

    def test_absent_blob_stays_benign_none(self, tmp_path: Path) -> None:
        """FR-005: an absent committed blob (``None``) stays benign (``None``)."""
        fake = _FakeGitPort(blobs={})
        assert _committed_meta_mapping(tmp_path, _META_REL, None, git=fake) is None

    @pytest.mark.parametrize("blob", [b"", b"   \n\t"])
    def test_empty_or_whitespace_blob_stays_benign_none(self, tmp_path: Path, blob: bytes) -> None:
        """C-010 / FR-005: an empty/whitespace-only committed blob is NOT
        malformed -- it stays benign (``None``), never the fail-loud channel."""
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): blob})
        assert _committed_meta_mapping(tmp_path, _META_REL, None, git=fake) is None

    def test_valid_committed_blob_verdict_unchanged(self, tmp_path: Path) -> None:
        """FR-005 happy path: a valid committed blob decodes to its mapping,
        exactly as before routing."""
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): b'{"vcs": "git"}'})
        assert _committed_meta_mapping(tmp_path, _META_REL, None, git=fake) == {"vcs": "git"}


# ---------------------------------------------------------------------------
# Site C -- ``_is_self_write_only_diff`` (worktree meta.json read, inline)
# ---------------------------------------------------------------------------


class TestSiteCSelfWriteOnlyDiff:
    @pytest.mark.parametrize("raw", [_CORRUPT_JSON, _INVALID_UTF8, _NON_OBJECT])
    def test_corrupt_worktree_meta_raises_naming_meta_json(self, tmp_path: Path, raw: bytes) -> None:
        """FR-007: a present-but-corrupt worktree ``meta.json`` fails loud with
        the shared typed error naming ``meta.json`` (the filesystem path), not
        the former silent ``None`` -> ``return False``."""
        _write_meta(tmp_path, raw)
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): b'{"vcs": "git"}'})
        with pytest.raises(MetaDecodeError, match="meta.json"):
            _is_self_write_only_diff(tmp_path, _META_REL, None, git=fake)

    def test_missing_worktree_meta_stays_benign_false(self, tmp_path: Path) -> None:
        """FR-005: a missing worktree ``meta.json`` stays benign (``False`` --
        not a self-write, so the file is kept / the claim still blocks)."""
        (tmp_path / "kitty-specs" / "m").mkdir(parents=True)
        assert _is_self_write_only_diff(tmp_path, _META_REL, None, git=_FakeGitPort()) is False

    @pytest.mark.parametrize("raw", [b"", b"   \n\t"])
    def test_empty_or_whitespace_worktree_meta_stays_benign_false(self, tmp_path: Path, raw: bytes) -> None:
        """C-010 / FR-005: an empty/whitespace-only worktree ``meta.json`` is
        NOT malformed -- it stays benign (``False``), never the fail-loud
        channel."""
        _write_meta(tmp_path, raw)
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): b'{"vcs": "git"}'})
        assert _is_self_write_only_diff(tmp_path, _META_REL, None, git=fake) is False

    def test_valid_lock_only_diff_verdict_unchanged_true(self, tmp_path: Path) -> None:
        """FR-005 happy path: a valid lock-field-only diff still resolves to a
        self-write (``True``), exactly as before routing."""
        _write_meta(tmp_path, b'{"friendly_name": "a", "vcs": "git", "vcs_locked_at": "t0"}')
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): b'{"friendly_name": "a"}'})
        assert _is_self_write_only_diff(tmp_path, _META_REL, None, git=fake) is True

    def test_valid_non_lock_diff_verdict_unchanged_false(self, tmp_path: Path) -> None:
        """FR-005 happy path: a valid non-lock diff still blocks the claim
        (``False``), exactly as before routing."""
        _write_meta(tmp_path, b'{"friendly_name": "b"}')
        fake = _FakeGitPort(blobs={("HEAD", _META_REL): b'{"friendly_name": "a"}'})
        assert _is_self_write_only_diff(tmp_path, _META_REL, None, git=fake) is False
