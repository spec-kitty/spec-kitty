"""Create-mode proof for the tracker plaintext-secret credential transport.

Mission ``local-write-safety-01M2ZPZD`` WP06 (#4812 / #4760, D7):
``tracker/credentials.py`` must be "0600-by-construction" — owner-only *at
creation*, never a ``write_text``/``O_TRUNC`` write followed by a trailing
``chmod`` that narrows a briefly-wider mode. (The zeitgeist_client transport
this mission also covered was removed from open-core in #6164.)

A post-hoc ``stat().st_mode == 0o600`` assertion is explicitly rejected as
non-fakeable proof here (SC-005): tracker's pre-fix ``write_text`` +
``os.chmod(0o600)`` already ends at the right final mode, so that assertion
is green on the bug. Every test below instead proves the *creation* itself:

- **Structural**: the create call goes through ``os.open(...,
  O_CREAT|O_EXCL|O_WRONLY, 0o600)`` (via
  :func:`kernel.no_follow.open_no_follow`) and ``os.chmod`` is never called
  against the credential file itself.
- **Interception**: ``os.open`` is spied to capture the literal creation-mode
  argument and assert it is ``0o600``.
- **Symlink refusal** (SC-001): a symlink planted at the temp/target write
  path is refused rather than written through.

Every test runs under an isolated ``SPEC_KITTY_HOME`` (never the real
developer home).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.tracker.credentials import TrackerCredentialError, TrackerCredentialStore

pytestmark = [pytest.mark.fast, pytest.mark.unit]


# ---------------------------------------------------------------------------
# Shared spies
# ---------------------------------------------------------------------------


class _OpenSpy:
    """Records every ``os.open`` call: ``(path, flags, mode)``."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: list[tuple[str, int, int]] = []
        original = os.open

        def _spy(path: object, flags: int, mode: int = 0o777, *args: object, **kwargs: object) -> int:
            self.calls.append((str(path), flags, mode))
            return original(path, flags, mode, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "open", _spy)

    def matching(self, substr: str) -> list[tuple[str, int, int]]:
        return [call for call in self.calls if substr in call[0]]


class _ChmodSpy:
    """Records every ``os.chmod`` target path (also fires for
    ``Path.chmod``, which is implemented on top of ``os.chmod``)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.targets: list[str] = []
        original = os.chmod

        def _spy(path: object, mode: int, *args: object, **kwargs: object) -> None:
            self.targets.append(str(path))
            original(path, mode, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(os, "chmod", _spy)


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect every runtime-root resolution to a fresh, isolated
    directory — never the real developer ``~/.spec-kitty``."""
    home = tmp_path / "spec-kitty-home"
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return home


CREATE_FLAGS = os.O_CREAT | os.O_EXCL | os.O_WRONLY


def _has_create_flags(flags: int) -> bool:
    return (flags & CREATE_FLAGS) == CREATE_FLAGS


# ---------------------------------------------------------------------------
# T019 — tracker/credentials.py
# ---------------------------------------------------------------------------


def test_tracker_credential_write_is_0600_by_construction_structural(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The create call itself is ``O_CREAT|O_EXCL|O_WRONLY`` at ``0o600`` —
    and no ``os.chmod`` ever touches the credential file (no post-hoc
    narrowing). Red on the pre-fix ``write_text``+``chmod`` code (which
    calls ``os.chmod`` on the credential path and never passes
    ``O_EXCL``)."""
    # Arrange
    open_spy = _OpenSpy(monkeypatch)
    chmod_spy = _ChmodSpy(monkeypatch)
    store = TrackerCredentialStore()  # default path -> exercises ensure_runtime_root too
    assert not store.path.exists(), "must be a fresh, isolated HOME"

    # Act
    store.set_provider("beads", {"command": "beads", "workspace": "demo"})

    # Assert: structural -- the credential file's create call used O_EXCL.
    create_calls = [call for call in open_spy.matching(store.path.name) if _has_create_flags(call[1])]
    assert create_calls, f"no O_CREAT|O_EXCL|O_WRONLY create observed among {open_spy.calls!r}"
    assert all(mode == 0o600 for _, _, mode in create_calls)

    # Assert: no post-hoc chmod ever narrows the credential FILE itself.
    assert str(store.path) not in chmod_spy.targets


def test_tracker_credential_create_mode_argument_is_0600_interception(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Interception proof: the literal mode argument passed to ``os.open``
    for the credential file's creation is ``0o600``."""
    # Arrange
    open_spy = _OpenSpy(monkeypatch)
    store = TrackerCredentialStore()

    # Act
    store.set_provider("beads", {"command": "beads", "workspace": "demo"})

    # Assert
    matching = open_spy.matching(store.path.name)
    assert matching, "expected at least one os.open call touching the credential file"
    for _, flags, mode in matching:
        if flags & os.O_CREAT:
            assert mode == 0o600, f"creation mode was {oct(mode)}, expected 0o600"


def test_tracker_credentials_file_mode_is_0600_on_disk(isolated_home: Path) -> None:
    """Sanity companion to the structural/interception proofs above: the
    resulting file really is 0600 on POSIX (not the non-fakeable proof by
    itself -- see module docstring)."""
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX-only permission check")
    store = TrackerCredentialStore()

    store.set_provider("beads", {"command": "beads", "workspace": "demo"})

    import stat

    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600


def test_tracker_credential_write_refuses_a_symlink_planted_at_the_temp_path(isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001: a symlink swapped in for the write's temp file is refused --
    the secret it points at is never disclosed/overwritten."""
    store = TrackerCredentialStore()
    store.path.parent.mkdir(parents=True, exist_ok=True)
    secret = store.path.parent / "secret.txt"
    secret.write_text("do not disclose\n", encoding="utf-8")

    original_open = os.open
    planted: list[str] = []

    def _plant_then_open(path: object, flags: int, mode: int = 0o777, *args: object, **kwargs: object) -> int:
        candidate = Path(str(path))
        if flags & os.O_EXCL and f"{store.path.name}.tmp." in candidate.name and not planted:
            candidate.symlink_to(secret)
            planted.append(str(candidate))
        return original_open(path, flags, mode, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", _plant_then_open)

    # Act / Assert
    with pytest.raises(TrackerCredentialError):
        store.set_provider("beads", {"command": "beads", "workspace": "demo"})

    assert planted, "the symlink-plant interception never fired"
    assert secret.read_text(encoding="utf-8") == "do not disclose\n"
    assert not store.path.exists()


def test_tracker_ensure_runtime_root_is_single_owner_of_the_shared_root(isolated_home: Path) -> None:
    """FR-011: the shared runtime root is 0o700 after a tracker write, and
    that establishment came from the single canonical door
    (``ensure_runtime_root``), not a per-file re-establishment."""
    if not hasattr(os, "getuid"):
        pytest.skip("POSIX-only permission check")
    import stat

    from specify_cli.paths import get_runtime_root

    store = TrackerCredentialStore()
    store.set_provider("beads", {"command": "beads", "workspace": "demo"})

    assert stat.S_IMODE(get_runtime_root().base.stat().st_mode) == 0o700


def test_tracker_injected_path_never_touches_the_real_runtime_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller-supplied ``path`` (e.g. test isolation elsewhere in the
    suite) is not the shared production location -- ``save()`` must not
    call ``ensure_runtime_root`` (and therefore must not mkdir/chmod the
    real runtime root) on its behalf."""
    # Deliberately do NOT set SPEC_KITTY_HOME: prove the real root is
    # never touched even though it is resolvable.
    from specify_cli.paths import get_runtime_root

    real_root = get_runtime_root().base
    assert real_root != tmp_path

    calls: list[str] = []
    original_mkdir = Path.mkdir

    def _spy_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        calls.append(str(self))
        original_mkdir(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "mkdir", _spy_mkdir)

    store = TrackerCredentialStore(path=tmp_path / "credentials")
    store.set_provider("beads", {"command": "beads", "workspace": "demo"})

    assert str(real_root) not in calls
