"""``gh attestation verify`` seam: the command shape, stable codes and redaction (#6909).

No test here runs ``gh`` or touches the network: the module's ``_gh`` and ``_run`` seams are
replaced, so the assertions are about the arguments core passes and the refusal it reports.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.services import attestation as attestation_module
from specify_cli.services.attestation import (
    SERVICE_ATTESTATION_FAILED,
    SERVICE_ATTESTATION_UNAVAILABLE,
    SERVICE_ATTESTATION_UNSUPPORTED,
    AttestationError,
    attestation_args,
    github_slug,
    signer_workflow,
    verify_release_attestation,
)

pytestmark = pytest.mark.fast

TAG = "service-v0.1.0-rc.1"
CHARTER = "https://github.com/spec-kitty/spec-kitty-charter"
CHARTER_SLUG = "spec-kitty/spec-kitty-charter"
ASSET = Path("/scratch/assets/spec-kitty-charter-service-0.1.0-rc.1-linux-x64")
DIGEST = "a" * 64


def _completed(returncode: int, *, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=("gh",), returncode=returncode, stdout="", stderr=stderr)


@pytest.fixture
def fake_gh(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """A `gh` on PATH whose every invocation succeeds; returns the recorded argv lists."""
    calls: list[tuple[str, ...]] = []

    def run(argv: tuple[str, ...], *, timeout: int) -> subprocess.CompletedProcess[str]:
        assert timeout > 0
        calls.append(argv)
        return _completed(0)

    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(attestation_module, "_run", run)
    return calls


# -- slug and arguments ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("repository", "expected"),
    [
        (CHARTER, CHARTER_SLUG),
        ("https://github.com/spec-kitty/spec-kitty-events.git", "spec-kitty/spec-kitty-events"),
        ("https://www.github.com/spec-kitty/spec-kitty-events", "spec-kitty/spec-kitty-events"),
        ("https://github.com/spec-kitty", None),
        ("https://github.com/spec-kitty/spec-kitty-charter/tree/main", None),
        ("https://alice:s3cr3t@example.invalid/spec-kitty/charter", None),
        ("file:///tmp/releases", None),
        ("https://gitlab.com/spec-kitty/spec-kitty-charter", None),
    ],
)
def test_github_slug_accepts_only_a_github_repository_url(repository: str, expected: str | None) -> None:
    assert github_slug(repository) == expected


def test_signer_workflow_is_the_release_workflow_of_the_repository() -> None:
    assert signer_workflow(CHARTER_SLUG) == f"{CHARTER_SLUG}/.github/workflows/service-release.yml"


def test_the_attestation_arguments_pin_the_signer_and_the_tag_ref() -> None:
    """The two flags `gh` needs to make the check mean anything: signer workflow and source ref."""
    assert attestation_args(ASSET, repository=CHARTER, tag=TAG) == (
        "attestation",
        "verify",
        str(ASSET),
        "--repo",
        CHARTER_SLUG,
        "--signer-workflow",
        f"{CHARTER_SLUG}/.github/workflows/service-release.yml",
        "--source-ref",
        f"refs/tags/{TAG}",
    )


def test_a_non_github_repository_is_unsupported_before_any_command_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(attestation_module, "_run", lambda argv, *, timeout: calls.append(argv) or _completed(0))

    with pytest.raises(AttestationError) as excinfo:
        attestation_args(ASSET, repository="file:///tmp/releases", tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_UNSUPPORTED
    assert ASSET.name in excinfo.value.message
    assert calls == []


# -- refusal codes ---------------------------------------------------------------------------


def test_a_verified_asset_runs_gh_with_the_attestation_arguments(fake_gh: list[tuple[str, ...]]) -> None:
    verify_release_attestation(ASSET, repository=CHARTER, tag=TAG)

    assert fake_gh == [("/usr/bin/gh", *attestation_args(ASSET, repository=CHARTER, tag=TAG))]


def test_gh_missing_is_unavailable_and_names_the_remedy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attestation_module, "_gh", lambda: None)

    with pytest.raises(AttestationError) as excinfo:
        verify_release_attestation(ASSET, repository=CHARTER, tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_UNAVAILABLE
    assert "--no-attestation" in excinfo.value.message
    assert ASSET.name in excinfo.value.message


def test_gh_cannot_start_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(argv: tuple[str, ...], *, timeout: int) -> subprocess.CompletedProcess[str]:
        raise OSError(2, "No such file or directory")

    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(attestation_module, "_run", fail)

    with pytest.raises(AttestationError) as excinfo:
        verify_release_attestation(ASSET, repository=CHARTER, tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_UNAVAILABLE


def test_gh_timeout_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def time_out(argv: tuple[str, ...], *, timeout: int) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(attestation_module, "_run", time_out)

    with pytest.raises(AttestationError) as excinfo:
        verify_release_attestation(ASSET, repository=CHARTER, tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_UNAVAILABLE


def test_a_refused_attestation_names_the_asset_and_redacts_digests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(
        attestation_module,
        "_run",
        lambda argv, *, timeout: _completed(1, stderr=f"no attestations found for subject with digest {DIGEST}\n"),
    )

    with pytest.raises(AttestationError) as excinfo:
        verify_release_attestation(ASSET, repository=CHARTER, tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_FAILED
    assert ASSET.name in excinfo.value.message
    assert DIGEST not in excinfo.value.message
    assert excinfo.value.message.endswith("<digest>") or "<digest>" in excinfo.value.message


def test_a_refused_attestation_with_only_a_return_code_still_names_the_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(attestation_module, "_run", lambda argv, *, timeout: _completed(1))

    with pytest.raises(AttestationError) as excinfo:
        verify_release_attestation(ASSET, repository=CHARTER, tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_FAILED
    assert TAG in excinfo.value.message
    assert ASSET.name in excinfo.value.message


def test_an_unsupported_repository_never_parses_its_userinfo_into_the_message(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = "https://alice:s3cr3t-token@example.invalid/spec-kitty/charter"
    monkeypatch.setattr(attestation_module, "_gh", lambda: "/usr/bin/gh")
    monkeypatch.setattr(
        attestation_module,
        "_run",
        lambda argv, *, timeout: pytest.fail("a non-GitHub repository must not reach gh"),
    )

    with pytest.raises(AttestationError) as excinfo:
        verify_release_attestation(ASSET, repository=repository, tag=TAG)

    assert excinfo.value.code == SERVICE_ATTESTATION_UNSUPPORTED
    assert "s3cr3t-token" not in str(excinfo.value)
