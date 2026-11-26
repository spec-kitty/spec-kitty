"""A throwaway OpenPGP signing key for tests that need signed commits (#5604 review fold R1).

``log.showSignature=true`` changes what ``git show`` / ``git log`` print only for a signed commit,
so a regression test for that exposure needs one. The key lives in a fresh ``GNUPGHOME`` under the
test's ``tmp_path``; nothing outside it is read or written.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

SIGNING_IDENTITY = "t@example.invalid"


def use_throwaway_signing_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point ``GNUPGHOME`` at a new directory holding one passphrase-less ed25519 signing key; skip without ``gpg``."""
    if shutil.which("gpg") is None:
        pytest.skip("gpg is not installed")
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    monkeypatch.setenv("GNUPGHOME", str(home))
    subprocess.run(
        ["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "", "--quick-gen-key", f"T <{SIGNING_IDENTITY}>", "ed25519", "sign", "never"],
        capture_output=True,
        check=True,
    )


def sign_commits_and_show_signatures(repo: Path) -> None:
    """Configure *repo* to sign every commit with the throwaway key and to show signatures in ``log`` / ``show``."""
    for key, value in (("gpg.format", "openpgp"), ("user.signingkey", SIGNING_IDENTITY), ("commit.gpgsign", "true"), ("log.showSignature", "true")):
        subprocess.run(["git", "-C", str(repo), "config", key, value], capture_output=True, check=True)
