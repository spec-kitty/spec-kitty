"""``spec-kitty service vendor``: the one path that rewrites a service pin lockfile (#6590, FR-013, US4).

Every release here is a ``file://`` fixture built by ``tests/kernel/service_release_fixture``;
``file://`` has no git remote, so ``commit`` is always given. Nothing touches the network.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path

import pytest

from kernel.git.remote import RemoteUnreachable
from kernel.git.runner import GitCommandError
from kernel.service_artifacts import sha256_file
from kernel.service_pin import ServiceAsset, ServicePin, ServiceTarget, load_service_pin, write_service_pin
from specify_cli.services import vendor as vendor_module
from specify_cli.services.vendor import VendorError, check_pin, vendor_pin
from tests.kernel.service_release_fixture import FIXTURE_COMMIT, SUMS_FILE, build_release, pin_path

pytestmark = pytest.mark.fast

TAG = "service-v0.1.0"
CORE = "4.0.0rc9"
OTHER_COMMIT = "fedcba9876543210fedcba9876543210fedcba98"


def _add_to_release(release_dir: Path, name: str, data: bytes) -> str:
    """Add *name* to the release and to its ``SHA256SUMS``; return its digest."""
    path = release_dir / name
    path.write_bytes(data)
    digest = sha256_file(path)
    with (release_dir / SUMS_FILE).open("a", encoding="utf-8") as sums:
        sums.write(f"{digest}  {name}\n")
    return digest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "core"
    root.mkdir()
    return root


@pytest.fixture
def release(tmp_path: Path) -> tuple[ServicePin, Path]:
    return build_release(tmp_path / "releases", tag=TAG)


_FROM_PIN = "<from the pin>"


def _vendor(
    repo: Path,
    pin: ServicePin,
    *,
    service: str = "write-service",
    tag: str = TAG,
    repository: str | None = _FROM_PIN,
    commit: str | None = FIXTURE_COMMIT,
    protocol_versions: Sequence[int] = (1,),
    asset_prefix: str | None = None,
) -> vendor_module.VendorResult:
    return vendor_pin(
        pins_dir=repo / "pins",
        service=service,
        tag=tag,
        repository=pin.repository if repository == _FROM_PIN else repository,
        commit=commit,
        protocol_versions=protocol_versions,
        asset_prefix_override=asset_prefix,
        core_version=CORE,
    )


def _seed_lockfile(repo: Path, pin: ServicePin, *, requires_core: str | None = None) -> bytes:
    """Write an older pin as the current lockfile and return its bytes."""
    path = pin_path(repo, pin.service)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_service_pin(dataclasses.replace(pin, tag="service-v0.0.9", requires_core=requires_core or pin.requires_core), path)
    return path.read_bytes()


# -- the bump ------------------------------------------------------------------------------------


def test_vendor_writes_the_expected_pin(repo: Path, release: tuple[ServicePin, Path], tmp_path: Path) -> None:
    pin, release_dir = release
    contracts = _add_to_release(release_dir, "contract-bundles-0.1.0.tar.gz", b"contracts")
    tools = _add_to_release(release_dir, "contract-tools-0.1.0.tar.gz", b"tools")
    fixtures = _add_to_release(release_dir, "conformance-fixtures-0.1.0.tar.gz", b"fixtures")

    result = _vendor(repo, pin)

    expected = dataclasses.replace(
        pin,
        requires_core=">=4.0.0rc9,<5",
        extras={
            "contracts": ServiceAsset("contract-bundles-0.1.0.tar.gz", contracts),
            "contract_tools": ServiceAsset("contract-tools-0.1.0.tar.gz", tools),
            "fixtures": ServiceAsset("conformance-fixtures-0.1.0.tar.gz", fixtures),
        },
    )
    reference = tmp_path / "reference" / "write-service.source.yaml"
    reference.parent.mkdir()
    write_service_pin(expected, reference)
    assert pin_path(repo, "write-service").read_bytes() == reference.read_bytes()
    assert load_service_pin(pin_path(repo, "write-service")) == result.pin
    assert result.ignored == ()


def test_an_existing_lockfile_keeps_its_requires_core(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _seed_lockfile(repo, pin, requires_core=">=4.0.0rc1,<5")

    assert _vendor(repo, pin).pin.requires_core == ">=4.0.0rc1,<5"


def test_the_default_repository_is_the_current_pins(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _seed_lockfile(repo, pin)

    assert _vendor(repo, pin, repository=None).pin.repository == pin.repository


def test_vendoring_twice_is_byte_stable(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _vendor(repo, pin)
    first = pin_path(repo, "write-service").read_bytes()
    _vendor(repo, pin)
    assert pin_path(repo, "write-service").read_bytes() == first


def test_an_unknown_asset_in_sha256sums_is_ignored(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    _add_to_release(release_dir, "RELEASE-NOTES.txt", b"notes")

    result = _vendor(repo, pin)

    assert result.ignored == ("RELEASE-NOTES.txt",)
    assert "RELEASE-NOTES.txt" not in pin_path(repo, "write-service").read_text(encoding="utf-8")


def test_targets_the_service_lacks_are_omitted_never_borrowed_from_another_service(repo: Path, tmp_path: Path) -> None:
    """The release carries both Java services; write-service has no macos-arm64 build and no jar."""
    root = tmp_path / "both"
    write_pin, _ = build_release(root, tag=TAG, assets={ServiceTarget.LINUX_X64: b"write"})
    read_pin, _ = build_release(
        root,
        service="read-service",
        tag=TAG,
        assets={ServiceTarget.LINUX_X64: b"read", ServiceTarget.MACOS_ARM64: b"read-mac", ServiceTarget.JVM: b"read-jar"},
    )

    result = _vendor(repo, write_pin)

    assert set(result.pin.assets) == {ServiceTarget.LINUX_X64}
    assert result.pin.assets[ServiceTarget.LINUX_X64] == write_pin.assets[ServiceTarget.LINUX_X64]
    lockfile = pin_path(repo, "write-service").read_text(encoding="utf-8")
    for asset in read_pin.assets.values():
        assert asset.name not in lockfile
        assert asset.name in result.ignored


def test_the_read_service_is_vendored_from_its_own_builds(repo: Path, tmp_path: Path) -> None:
    root = tmp_path / "both"
    build_release(root, tag=TAG)
    read_pin, _ = build_release(root, service="read-service", tag=TAG)

    result = _vendor(repo, read_pin, service="read-service")

    assert dict(result.pin.assets) == dict(read_pin.assets)
    assert all(asset.name.startswith("mission-status-api-0.1.0") for asset in result.pin.assets.values())


def test_a_build_of_another_version_is_ignored(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    _add_to_release(release_dir, "command-cli-0.2.0-macos-arm64", b"newer")
    _add_to_release(release_dir, "contract-bundles-0.0.9.tar.gz", b"older")

    result = _vendor(repo, pin)

    assert ServiceTarget.MACOS_ARM64 not in result.pin.assets
    assert result.pin.extras == {}
    assert set(result.ignored) == {"command-cli-0.2.0-macos-arm64", "contract-bundles-0.0.9.tar.gz"}


def test_a_near_miss_name_is_ignored(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    _add_to_release(release_dir, "command-cli-0.1.0-debug-linux-x64", b"debug")

    result = _vendor(repo, pin)

    assert result.pin.assets[ServiceTarget.LINUX_X64] == pin.assets[ServiceTarget.LINUX_X64]
    assert result.ignored == ("command-cli-0.1.0-debug-linux-x64",)


def test_an_asset_prefix_override_selects_those_builds(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "custom", tag=TAG, prefix="write-svc")

    result = _vendor(repo, pin, asset_prefix="write-svc")

    assert dict(result.pin.assets) == dict(pin.assets)
    with pytest.raises(VendorError) as excinfo:  # the default prefix finds no build in that release
        _vendor(repo, pin)
    assert excinfo.value.code == vendor_module.VENDOR_RELEASE_INVALID


def test_a_pre_release_tag_maps_its_version(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "rc", tag="service-v0.1.0-rc.1")

    result = _vendor(repo, pin, tag="service-v0.1.0-rc.1")

    assert result.pin.assets[ServiceTarget.LINUX_X64].name == "command-cli-0.1.0-rc.1-linux-x64"


@pytest.mark.parametrize("tag", ["v0.1.0", "service-v0.1", "service-v0.1.0+build", "service-v0.1.0-"])
def test_a_malformed_tag_is_a_usage_error(repo: Path, release: tuple[ServicePin, Path], tag: str) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, tag=tag)
    assert excinfo.value.code == vendor_module.VENDOR_USAGE


def test_a_malformed_asset_prefix_is_a_usage_error(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, asset_prefix="../escape")
    assert excinfo.value.code == vendor_module.VENDOR_USAGE


# -- refusals leave the lockfile byte-identical ----------------------------------------------------


def test_a_corrupt_asset_refuses_and_leaves_the_lockfile_unchanged(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    before = _seed_lockfile(repo, pin)
    (release_dir / pin.assets[ServiceTarget.LINUX_X64].name).write_bytes(b"tampered")

    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin)

    assert excinfo.value.code == vendor_module.VENDOR_DIGEST_MISMATCH
    assert pin.assets[ServiceTarget.LINUX_X64].name in str(excinfo.value)
    assert pin_path(repo, "write-service").read_bytes() == before


def test_unmet_requires_core_refuses_naming_the_specifier(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    before = _seed_lockfile(repo, pin, requires_core=">=9,<10")

    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin)

    assert excinfo.value.code == vendor_module.VENDOR_REQUIRES_CORE
    assert ">=9,<10" in str(excinfo.value)
    assert CORE in str(excinfo.value)
    assert pin_path(repo, "write-service").read_bytes() == before


def test_an_invalid_requires_core_refuses(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    before = _seed_lockfile(repo, pin, requires_core="not a specifier")

    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin)

    assert excinfo.value.code == vendor_module.VENDOR_REQUIRES_CORE
    assert pin_path(repo, "write-service").read_bytes() == before


def test_a_missing_release_refuses(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, tag="service-v0.2.0")
    assert excinfo.value.code == vendor_module.VENDOR_RELEASE_UNAVAILABLE
    assert not pin_path(repo, "write-service").exists()


def test_a_malformed_sha256sums_refuses(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    with (release_dir / SUMS_FILE).open("a", encoding="utf-8") as sums:
        sums.write("not-a-digest  something\n")
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin)
    assert excinfo.value.code == vendor_module.VENDOR_RELEASE_INVALID


def test_a_release_without_any_build_refuses(repo: Path, tmp_path: Path) -> None:
    root = tmp_path / "empty"
    (root / TAG).mkdir(parents=True)
    (root / TAG / SUMS_FILE).write_text(f"{'a' * 64}  RELEASE-NOTES.txt\n", encoding="utf-8")
    with pytest.raises(VendorError) as excinfo:
        vendor_pin(pins_dir=repo / "pins", service="write-service", tag=TAG, repository=root.as_uri(), commit=FIXTURE_COMMIT, core_version=CORE)
    assert excinfo.value.code == vendor_module.VENDOR_RELEASE_INVALID


def test_a_file_repository_requires_an_explicit_commit(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, commit=None)
    assert excinfo.value.code == vendor_module.VENDOR_COMMIT_REQUIRED
    assert "--commit" in str(excinfo.value)


def test_an_unknown_service_refuses(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, service="mystery-service")
    assert excinfo.value.code == vendor_module.VENDOR_USAGE


@pytest.mark.parametrize("repository", ["https://alice:s3cr3t-value@github.com/spec-kitty/spec-kitty-events", "https://ghp_s3cr3tvalue@github.com/x/y"])
def test_a_repository_url_carrying_credentials_refuses_without_echoing_them(repo: Path, release: tuple[ServicePin, Path], repository: str) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, repository=repository)
    assert excinfo.value.code == vendor_module.VENDOR_USAGE
    assert "repository" in str(excinfo.value)
    assert "s3cr3t" not in str(excinfo.value)
    assert not pin_path(repo, "write-service").exists()


def test_a_repository_with_another_scheme_refuses(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, repository="http://example.invalid/x")
    assert excinfo.value.code == vendor_module.VENDOR_USAGE


def test_a_placeholder_commit_is_refused_by_the_pin_rules(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, commit="0" * 40)
    assert excinfo.value.code == "SERVICE_PIN_INVALID"


# -- tag -> commit over https (kernel.git.remote is the only git contact) ------------------------------


HTTPS_REPO = "https://github.com/spec-kitty/spec-kitty-events"


def test_an_https_tag_resolves_through_the_git_remote_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    asked: list[tuple[str, str]] = []

    def fake(cwd: Path, remote: str, tag: str) -> str:
        asked.append((remote, tag))
        return FIXTURE_COMMIT

    monkeypatch.setattr(vendor_module, "remote_tag_commit", fake)
    assert vendor_module.resolve_commit(HTTPS_REPO, TAG, None, scratch=tmp_path) == FIXTURE_COMMIT
    assert asked == [(f"{HTTPS_REPO}.git", TAG)]


def test_an_https_tag_that_does_not_exist_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(vendor_module, "remote_tag_commit", lambda cwd, remote, tag: None)
    with pytest.raises(VendorError) as excinfo:
        vendor_module.resolve_commit(HTTPS_REPO, TAG, None, scratch=tmp_path)
    assert excinfo.value.code == vendor_module.VENDOR_TAG_UNRESOLVED


def test_an_unreachable_remote_refuses(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def unreachable(cwd: Path, remote: str, tag: str) -> str:
        raise RemoteUnreachable(remote, GitCommandError(argv=("git",), cwd=cwd, returncode=128, stderr="fatal: unable to access", timed_out=False))

    monkeypatch.setattr(vendor_module, "remote_tag_commit", unreachable)
    with pytest.raises(VendorError) as excinfo:
        vendor_module.resolve_commit(HTTPS_REPO, TAG, None, scratch=tmp_path)
    assert excinfo.value.code == vendor_module.VENDOR_TAG_UNRESOLVED


def test_an_explicit_commit_must_match_the_https_tag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(vendor_module, "remote_tag_commit", lambda cwd, remote, tag: FIXTURE_COMMIT)
    assert vendor_module.resolve_commit(HTTPS_REPO, TAG, FIXTURE_COMMIT, scratch=tmp_path) == FIXTURE_COMMIT
    with pytest.raises(VendorError) as excinfo:
        vendor_module.resolve_commit(HTTPS_REPO, TAG, OTHER_COMMIT, scratch=tmp_path)
    assert excinfo.value.code == vendor_module.VENDOR_TAG_UNRESOLVED


# -- check_pin -----------------------------------------------------------------------------------


def test_check_pin_passes_a_vendored_pin_offline_and_online(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _vendor(repo, pin)
    assert check_pin(pins_dir=repo / "pins", service="write-service", online=False) == []
    assert check_pin(pins_dir=repo / "pins", service="write-service", online=True) == []


def test_check_pin_offline_flags_a_tampered_digest(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _vendor(repo, pin)
    path = pin_path(repo, "write-service")
    digest = pin.assets[ServiceTarget.LINUX_X64].sha256
    path.write_text(path.read_text(encoding="utf-8").replace(digest, digest[:-4] + "XXXX"), encoding="utf-8")

    problems = check_pin(pins_dir=repo / "pins", service="write-service", online=False)

    assert problems and "sha256" in problems[0]
    assert digest not in "".join(problems)


def test_check_pin_offline_flags_an_invalid_requires_core(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    _seed_lockfile(repo, pin, requires_core="whatever")
    assert any("requires_core" in problem for problem in check_pin(pins_dir=repo / "pins", service="write-service", online=False))


def test_check_pin_online_flags_a_digest_that_disagrees_with_sha256sums(repo: Path, tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "releases", tag=TAG, corrupt={"linux-x64"})
    path = pin_path(repo, "write-service")
    path.parent.mkdir()
    write_service_pin(pin, path)

    assert check_pin(pins_dir=repo / "pins", service="write-service", online=False) == []
    problems = check_pin(pins_dir=repo / "pins", service="write-service", online=True)

    assert len(problems) == 1
    assert pin.assets[ServiceTarget.LINUX_X64].name in problems[0]
    assert pin.assets[ServiceTarget.LINUX_X64].sha256 not in problems[0]


def test_check_pin_online_flags_an_asset_missing_from_sha256sums(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    _vendor(repo, pin)
    jar = pin.assets[ServiceTarget.JVM].name
    sums = release_dir / SUMS_FILE
    sums.write_text("".join(line for line in sums.read_text(encoding="utf-8").splitlines(keepends=True) if jar not in line), encoding="utf-8")

    problems = check_pin(pins_dir=repo / "pins", service="write-service", online=True)

    assert any(jar in problem for problem in problems)


def test_check_pin_online_reports_an_unreachable_release(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, release_dir = release
    _vendor(repo, pin)
    (release_dir / SUMS_FILE).unlink()
    problems = check_pin(pins_dir=repo / "pins", service="write-service", online=True)
    assert problems and vendor_module.VENDOR_RELEASE_UNAVAILABLE in problems[0]


def test_check_pin_online_compares_the_https_tag_commit(repo: Path, release: tuple[ServicePin, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    pin, _ = release
    path = pin_path(repo, "write-service")
    path.parent.mkdir()
    write_service_pin(dataclasses.replace(pin, repository=HTTPS_REPO), path)
    monkeypatch.setattr(vendor_module, "remote_tag_commit", lambda cwd, remote, tag: OTHER_COMMIT)
    monkeypatch.setattr(vendor_module, "asset_url", lambda repository, tag, name: f"{pin.repository}/{tag}/{name}")

    problems = check_pin(pins_dir=repo / "pins", service="write-service", online=True)

    assert any("commit" in problem for problem in problems)


def test_check_pin_reports_a_missing_lockfile(repo: Path) -> None:
    problems = check_pin(pins_dir=repo / "pins", service="write-service", online=False)
    assert problems and "not pinned" in problems[0]


def test_vendor_uses_the_kernel_tag_and_repository_rules() -> None:
    """One authority: vendor keeps no tag pattern or repository check of its own (F6)."""
    from kernel import service_pin

    assert vendor_module.DEFAULT_ASSET_PREFIXES is service_pin.DEFAULT_ASSET_PREFIXES
    assert not hasattr(vendor_module, "_TAG_VERSION_RE")
    assert not hasattr(vendor_module, "_NATIVE_SUFFIXES")


def test_asset_prefixes_policies_and_known_services_name_the_same_services() -> None:
    from kernel.service_pin import KNOWN_SERVICES
    from specify_cli.services import policies

    assert set(vendor_module.DEFAULT_ASSET_PREFIXES) == set(policies._POLICIES) == set(KNOWN_SERVICES)


def test_a_credentialed_repository_is_a_usage_error_without_echoing_it(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    with pytest.raises(VendorError) as excinfo:
        _vendor(repo, pin, repository="https://x-access-token:ghs_SECRET0123@github.com/spec-kitty/spec-kitty-events")
    assert excinfo.value.code == "SERVICE_VENDOR_USAGE"
    assert "SECRET" not in str(excinfo.value)


def test_vendor_reports_the_native_targets_the_release_lacks(repo: Path, release: tuple[ServicePin, Path]) -> None:
    pin, _ = release
    result = _vendor(repo, pin)
    assert result.absent_targets == (ServiceTarget.LINUX_ARM64, ServiceTarget.MACOS_ARM64, ServiceTarget.WINDOWS_X64)
