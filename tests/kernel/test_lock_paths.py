"""The one owner of the anchor-keyed lock-path rule (#6727).

``kernel.locks.anchored_lock_path`` is the single implementation of
"resolve the anchor -> ``os.path.normcase`` -> digest -> place the result under
``<git-common-dir>/spec-kitty-locks/``". The three families that used to carry their
own copy are pinned by value here, independently of the helper: the expected digest
is recomputed in the test with a literal ``hashlib`` expression, so a change to the
resolution order, the normalisation, the algorithm, the truncation or the join fails.

The goldens match the family tests these shapes came from on purpose:
``tests/kernel/test_event_log_append.py::test_lock_path_digest_golden_value`` (the
name the Java writer, #6193, must reproduce) and
``tests/status/test_checkout_claim_lock.py::test_key_is_the_normcased_resolved_checkout_digest``.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

import kernel.locks as locks_module
from kernel.locks import LOCK_DIRECTORY, anchored_lock_path

pytestmark = pytest.mark.unit


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    return path.resolve()


def _identity(anchor: Path) -> str:
    """The digest input: resolved, case-normalised, UTF-8."""
    return os.path.normcase(str(anchor.resolve()))


def _sha256(anchor: Path, length: int = 32) -> str:
    return hashlib.sha256(_identity(anchor).encode("utf-8")).hexdigest()[:length]  # noqa: TID251 — reproducing the anchor lock-name digest, not the charter hash


def _sha1(anchor: Path, length: int = 16) -> str:
    return hashlib.sha1(_identity(anchor).encode("utf-8"), usedforsecurity=False).hexdigest()[:length]


# ---------------------------------------------------------------------------
# The three shapes that exist in src/
# ---------------------------------------------------------------------------


def test_event_log_shape(tmp_path: Path) -> None:
    """Event-log lock: `<common>/spec-kitty-locks/event-logs/<sha256[:32]>.lock`."""
    common_dir = tmp_path / ".git"
    anchor = tmp_path / "kitty-specs" / "m" / "decisions.events.jsonl"

    assert anchored_lock_path(anchor, common_dir=common_dir, subdirectory="event-logs") == (common_dir / LOCK_DIRECTORY / "event-logs" / f"{_sha256(anchor)}.lock")


@pytest.mark.skipif(os.name != "posix", reason="POSIX absolute path; normcase is the identity there")
def test_event_log_golden_digest(tmp_path: Path) -> None:
    """The name the Java write service (#6193) must compute for the same anchor."""
    anchor = Path("/srv/repo/kitty-specs/m/decisions.events.jsonl")

    assert anchored_lock_path(anchor, common_dir=tmp_path, subdirectory="event-logs") == (
        tmp_path / LOCK_DIRECTORY / "event-logs" / "5d011f83a018c89fa185a10c696c8293.lock"
    )


def test_synthesis_shape(tmp_path: Path) -> None:
    """Charter synthesis lock: `<common>/spec-kitty-locks/charter-synthesis/<sha256[:32]>.lock`."""
    common_dir = tmp_path / ".git"
    root = tmp_path / "repo"

    assert anchored_lock_path(root, subdirectory="charter-synthesis", common_dir=common_dir) == (
        common_dir / LOCK_DIRECTORY / "charter-synthesis" / f"{_sha256(root)}.lock"
    )


def test_checkout_claim_shape(tmp_path: Path) -> None:
    """Mission checkout-claim lock: `<common>/spec-kitty-locks/__checkout-<sha1[:16]>__.status.lock`."""
    checkout = tmp_path / "repo"
    common_dir = checkout / ".git"

    assert anchored_lock_path(
        checkout,
        common_dir=common_dir,
        prefix="__checkout-",
        suffix="__.status.lock",
        digest_algorithm="sha1",
        digest_hex_length=16,
    ) == (common_dir / LOCK_DIRECTORY / f"__checkout-{_sha1(checkout)}__.status.lock")


def test_subdirectory_is_optional_and_the_default_name_is_the_digest(tmp_path: Path) -> None:
    assert anchored_lock_path(tmp_path, common_dir=tmp_path / ".git") == (tmp_path / ".git" / LOCK_DIRECTORY / f"{_sha256(tmp_path)}.lock")


def test_two_families_share_one_digest_for_one_anchor(tmp_path: Path) -> None:
    """The invariant behind the consolidation: identity is per anchor, not per family."""
    repo = _init_repo(tmp_path / "repo")

    common_dir = repo / ".git"
    event_log = anchored_lock_path(repo, common_dir=common_dir, subdirectory="event-logs")
    synthesis = anchored_lock_path(repo, common_dir=common_dir, subdirectory="charter-synthesis")

    assert event_log.stem == synthesis.stem
    assert event_log.name == f"{_sha256(repo)}.lock"
    assert event_log.parent.name == "event-logs"
    assert synthesis.parent.name == "charter-synthesis"
    assert event_log.parent.parent == synthesis.parent.parent == common_dir / LOCK_DIRECTORY


# ---------------------------------------------------------------------------
# The caller owns the probe
# ---------------------------------------------------------------------------


def test_common_dir_is_required_and_the_helper_runs_no_git(tmp_path: Path) -> None:
    """The probe and its failure policy stay with the family; the helper only names.

    ``kernel.locks`` therefore carries no git probe at all, so a caller cannot
    accidentally get a probe error, a fallback or a degrade from inside it.
    """
    with pytest.raises(TypeError, match="common_dir"):
        anchored_lock_path(tmp_path)  # type: ignore[call-arg]

    assert not hasattr(locks_module, "git_common_dir"), "the helper must not probe git; the family owns the probe and its policy"


def test_anchor_is_resolved_once_and_normcased(tmp_path: Path) -> None:
    """A symlinked anchor and its target name one lock; the digest sees the resolved path."""
    repo = _init_repo(tmp_path / "repo")
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)
    common_dir = repo / ".git"

    assert anchored_lock_path(link, common_dir=common_dir, subdirectory="event-logs") == anchored_lock_path(repo, common_dir=common_dir, subdirectory="event-logs")
    assert anchored_lock_path(link, common_dir=common_dir, subdirectory="event-logs").name == f"{_sha256(repo)}.lock"


def test_the_working_directory_does_not_matter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _init_repo(tmp_path / "repo")
    log = repo / "kitty-specs" / "m" / "decisions.events.jsonl"
    log.parent.mkdir(parents=True)  # the append creates the log; the probe only needs its parent
    common_dir = repo / ".git"
    from_repo = anchored_lock_path(log, common_dir=common_dir, subdirectory="event-logs")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    assert anchored_lock_path(log, common_dir=common_dir, subdirectory="event-logs") == from_repo


# ---------------------------------------------------------------------------
# Refusals: the helper never mints a name it cannot reproduce
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("algorithm", ["md5", "sha512", "not-a-hash", ""])
def test_unknown_digest_algorithm_is_refused(tmp_path: Path, algorithm: str) -> None:
    with pytest.raises(ValueError, match="digest algorithm"):
        anchored_lock_path(tmp_path, common_dir=tmp_path / ".git", digest_algorithm=algorithm)


@pytest.mark.parametrize("length", [0, -1, 65])
def test_digest_length_outside_the_supported_range_is_refused(tmp_path: Path, length: int) -> None:
    with pytest.raises(ValueError, match="digest length"):
        anchored_lock_path(tmp_path, common_dir=tmp_path / ".git", digest_hex_length=length)


@pytest.mark.parametrize("length", [1, 16, 32, 64])
def test_supported_digest_lengths_are_truncations_of_the_full_digest(tmp_path: Path, length: int) -> None:
    anchor = tmp_path / "repo"

    assert anchored_lock_path(anchor, common_dir=tmp_path / ".git", digest_hex_length=length).stem == _sha256(anchor, length)
