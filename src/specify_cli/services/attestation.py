"""Build-provenance verification for a pinned service release (#6909).

A release's ``SHA256SUMS`` is produced by the same workflow run whose build it describes, so
its digests prove integrity but not provenance. Both service repositories attest every asset
in ``SHA256SUMS`` (spec-kitty-events ADR 0003; spec-kitty-charter ADR-0046 decision 6), and
:func:`verify_release_attestation` is the one place core checks that statement, through
``gh attestation verify``.

It runs only from the vendor path, when a pin is written. An installed CLI fetches and
verifies the pinned digest alone and never calls ``gh``: the pin is the trust root. A
``file://`` repository has no attestation, and the caller skips this check for it.

The signer workflow and the source ref are pinned here, not optional: without both,
``gh attestation verify`` accepts an attestation from any workflow of the repository and any
ref, which is not the statement the release makes.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

__all__ = [
    "AttestationError",
    "verify_release_attestation",
]

SERVICE_ATTESTATION_UNSUPPORTED = "SERVICE_ATTESTATION_UNSUPPORTED"
SERVICE_ATTESTATION_UNAVAILABLE = "SERVICE_ATTESTATION_UNAVAILABLE"
SERVICE_ATTESTATION_FAILED = "SERVICE_ATTESTATION_FAILED"

#: The release workflow that attests a service release in both service repositories.
SIGNER_WORKFLOW = ".github/workflows/service-release.yml"
GH_EXECUTABLE = "gh"
_PREVIEW_SUFFIX = "refs/tags/"
_GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
_TIMEOUT_SECONDS = 120
_DETAIL_LIMIT = 200
_DIGEST_RE = re.compile(r"\b[0-9a-fA-F]{64}\b")
_USERINFO_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*://)[^/]*@")
_DETAIL_FALLBACK = "no diagnostic on stderr"


class AttestationError(RuntimeError):
    """A release asset's build provenance could not be verified; ``code`` is a stable ``SERVICE_ATTESTATION_*`` code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def github_slug(repository: str) -> str | None:
    """``owner/name`` for a GitHub ``https://`` repository URL, else ``None`` (no signer workflow can be derived)."""
    parts = urllib.parse.urlsplit(repository)
    if parts.scheme.lower() != "https" or (parts.hostname or "").lower() not in _GITHUB_HOSTS:
        return None
    segments = [segment for segment in parts.path.split("/") if segment]
    if len(segments) != 2:
        return None
    owner, name = segments
    if name.endswith(".git"):
        name = name[: -len(".git")]
    if not owner or not name:
        return None
    return f"{owner}/{name}"


def signer_workflow(slug: str) -> str:
    """The ``--signer-workflow`` value of *slug*: the release workflow in that repository."""
    return f"{slug}/{SIGNER_WORKFLOW}"


def _preview(repository: str) -> str:
    """*repository* with any ``user:secret@`` userinfo redacted, so a message never shows a credential."""
    return _USERINFO_RE.sub(r"\1***@", repository)


def attestation_args(asset: Path, *, repository: str, tag: str) -> tuple[str, ...]:
    """The ``gh`` arguments that verify *asset*'s provenance in *repository*'s *tag* release.

    Raises :class:`AttestationError` with ``SERVICE_ATTESTATION_UNSUPPORTED`` for a repository
    that has no GitHub signer workflow (a ``file://`` mirror, or a non-GitHub host).
    """
    slug = github_slug(repository)
    if slug is None:
        raise AttestationError(
            SERVICE_ATTESTATION_UNSUPPORTED,
            f"{_preview(repository)} is not a GitHub repository, so the build attestation of {asset.name} cannot be checked",
        )
    return (
        "attestation",
        "verify",
        str(asset),
        "--repo",
        slug,
        "--signer-workflow",
        signer_workflow(slug),
        "--source-ref",
        f"{_PREVIEW_SUFFIX}{tag}",
    )


def _gh() -> str | None:
    """The ``gh`` executable on this machine, or ``None``."""
    return shutil.which(GH_EXECUTABLE)


def _run(argv: tuple[str, ...], *, timeout: int) -> subprocess.CompletedProcess[str]:
    """Run *argv* with no shell; the seam tests replace (no user input reaches a shell)."""
    return subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)


def _detail(stderr: str) -> str:
    """One short line from ``gh``'s stderr, with any digest-shaped run redacted."""
    line = next((raw.strip() for raw in stderr.splitlines() if raw.strip()), "")
    if not line:
        return _DETAIL_FALLBACK
    line = _DIGEST_RE.sub("<digest>", line)
    return line if len(line) <= _DETAIL_LIMIT else f"{line[: _DETAIL_LIMIT - 3]}..."


def verify_release_attestation(asset: Path, *, repository: str, tag: str) -> None:
    """Verify that *asset* was built by *repository*'s release workflow for tag *tag*.

    ``gh attestation verify`` is asked for the pinned signer workflow and the tag's source ref,
    so an attestation from another workflow or ref does not pass. Nothing is written. A
    refusal is an :class:`AttestationError` naming the asset and the remedy; the message
    never echoes a digest or URL userinfo.
    """
    args = attestation_args(asset, repository=repository, tag=tag)
    executable = _gh()
    if executable is None:
        raise AttestationError(
            SERVICE_ATTESTATION_UNAVAILABLE,
            f"`{GH_EXECUTABLE}` is not on PATH, so the build attestation of {asset.name} cannot be checked; "
            f"install the GitHub CLI and run `{GH_EXECUTABLE} auth login`, or pass --no-attestation for an offline mirror",
        )
    try:
        completed = _run((executable, *args), timeout=_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AttestationError(
            SERVICE_ATTESTATION_UNAVAILABLE,
            f"`{GH_EXECUTABLE} attestation verify` could not run for {asset.name} ({type(exc).__name__}); "
            f"check `{GH_EXECUTABLE} auth status`, or pass --no-attestation for an offline mirror",
        ) from exc
    if completed.returncode != 0:
        raise AttestationError(
            SERVICE_ATTESTATION_FAILED,
            f"`{GH_EXECUTABLE} attestation verify` refused {asset.name} from {tag}: {_detail(completed.stderr)}",
        )
