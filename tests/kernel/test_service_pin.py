"""``kernel.service_pin``: the service pin lockfile model (FR-001, C-001, C-003).

A pin (``pins/<service>.source.yaml``) records which released build of a
service core runs: the ``service-v*`` tag, its commit, the protocol versions,
the core range it needs and, per target, the asset name and digest. The schema
is ``kitty-specs/pinned-service-binaries-01M64N66/contracts/service-pin.schema.md``.

Non-vacuous by construction: the valid fixture loads in this file, and every
rule of the contract has a malformed or placeholder variant of that same
fixture that refuses with ``SERVICE_PIN_INVALID``. Written red first.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from ruamel.yaml import YAML

from tests.kernel.service_release_fixture import pin_path
from kernel.service_pin import (
    DEFAULT_ASSET_PREFIXES,
    KNOWN_SERVICES,
    PINS_DIR,
    ServiceAsset,
    ServicePin,
    ServicePinError,
    ServiceTarget,
    check_repository,
    load_service_pin,
    pin_file,
    tag_version,
    write_service_pin,
)

pytestmark = pytest.mark.fast

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64
_DIGEST_C = "c" * 64
_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _valid_document() -> dict[str, Any]:
    return {
        "service": "write-service",
        "repository": "https://github.com/spec-kitty/spec-kitty-events",
        "tag": "service-v0.1.0",
        "commit": _COMMIT,
        "protocol_versions": [1],
        "requires_core": ">=4.0.0rc8,<5",
        "assets": {
            "linux-x64": {"name": "command-cli-0.1.0-linux-x64", "sha256": _DIGEST_A},
            "jvm": {"name": "command-cli-0.1.0.jar", "sha256": _DIGEST_B},
        },
        "extras": {
            "contracts": {"name": "contract-bundles-0.1.0.tar.gz", "sha256": _DIGEST_C},
        },
    }


def _write_document(directory: Path, document: Any, *, name: str = "write-service.source.yaml") -> Path:
    path = directory / name
    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(document, handle)
    return path


# --------------------------------------------------------------------------- #
# Valid pin
# --------------------------------------------------------------------------- #


def test_valid_pin_loads_into_frozen_value_objects(tmp_path: Path) -> None:
    pin = load_service_pin(_write_document(tmp_path, _valid_document()))

    assert pin.service == "write-service"
    assert pin.repository == "https://github.com/spec-kitty/spec-kitty-events"
    assert pin.tag == "service-v0.1.0"
    assert pin.commit == _COMMIT
    assert pin.protocol_versions == (1,)
    assert pin.requires_core == ">=4.0.0rc8,<5"
    assert set(pin.assets) == {ServiceTarget.LINUX_X64, ServiceTarget.JVM}
    assert pin.extras["contracts"] == ServiceAsset(name="contract-bundles-0.1.0.tar.gz", sha256=_DIGEST_C)
    with pytest.raises(dataclasses.FrozenInstanceError):
        pin.__setattr__("tag", "service-v9.9.9")
    with pytest.raises(TypeError):
        cast("dict[ServiceTarget, ServiceAsset]", pin.assets)[ServiceTarget.MACOS_ARM64] = ServiceAsset(name="x", sha256=_DIGEST_A)


def test_asset_for_hit_and_miss(tmp_path: Path) -> None:
    pin = load_service_pin(_write_document(tmp_path, _valid_document()))

    assert pin.asset_for(ServiceTarget.JVM) == ServiceAsset(name="command-cli-0.1.0.jar", sha256=_DIGEST_B)
    assert pin.asset_for(ServiceTarget.WINDOWS_X64) is None


def test_extras_are_optional(tmp_path: Path) -> None:
    document = _valid_document()
    del document["extras"]

    assert dict(load_service_pin(_write_document(tmp_path, document)).extras) == {}


def test_pre_release_tag_and_file_repository_are_accepted(tmp_path: Path) -> None:
    document = _valid_document()
    document["tag"] = "service-v0.1.0-rc.1"
    document["repository"] = (tmp_path / "fixture-release").as_uri()

    pin = load_service_pin(_write_document(tmp_path, document))

    assert pin.tag == "service-v0.1.0-rc.1"


def test_target_enum_values_match_the_contract() -> None:
    assert [target.value for target in ServiceTarget] == ["linux-x64", "linux-arm64", "macos-arm64", "windows-x64", "jvm"]
    assert {"write-service", "read-service", "charter-service"} == set(KNOWN_SERVICES)


def test_pin_file_names_the_lockfile() -> None:
    assert pin_file(Path("/repo") / PINS_DIR, "read-service") == Path("/repo") / PINS_DIR / "read-service.source.yaml"
    assert PINS_DIR == "pins"


# --------------------------------------------------------------------------- #
# Invalid pins: one case per rule of the schema contract
# --------------------------------------------------------------------------- #


def _set(key: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        document[key] = value

    return mutate


def _drop(key: str) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        del document[key]

    return mutate


def _asset(target: str, field: str, value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        document["assets"][target][field] = value

    return mutate


def _duplicate_name(document: dict[str, Any]) -> None:
    document["extras"]["contracts"]["name"] = document["assets"]["jvm"]["name"]


def _unknown_target(document: dict[str, Any]) -> None:
    document["assets"]["macos-x64"] = {"name": "service-macos-x64", "sha256": _DIGEST_A}


def _unknown_extras_key(document: dict[str, Any]) -> None:
    document["extras"]["docs"] = {"name": "docs.tar.gz", "sha256": _DIGEST_A}


def _unknown_asset_field(document: dict[str, Any]) -> None:
    document["assets"]["jvm"]["url"] = "https://example.invalid/a.jar"


_INVALID_CASES: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
    ("bad-tag", _set("tag", "v0.1.0"), "tag"),
    ("placeholder-tag", _set("tag", "service-v0.0.0"), "tag"),
    ("build-metadata-tag", _set("tag", "service-v0.1.0+build.5"), "tag"),
    ("dot-suffix-tag", _set("tag", "service-v0.1.0.1"), "tag"),
    ("hyphen-in-pre-release-tag", _set("tag", "service-v0.1.0-rc-1"), "tag"),
    ("trailing-newline-tag", _set("tag", "service-v0.1.0\n"), "tag"),
    ("short-commit", _set("commit", "0123abc"), "commit"),
    ("uppercase-commit", _set("commit", _COMMIT.upper()), "commit"),
    ("zero-commit", _set("commit", "0" * 40), "commit"),
    ("empty-protocol-list", _set("protocol_versions", []), "protocol_versions"),
    ("non-positive-protocol", _set("protocol_versions", [0]), "protocol_versions"),
    ("bool-protocol", _set("protocol_versions", [True]), "protocol_versions"),
    ("scalar-protocol", _set("protocol_versions", 1), "protocol_versions"),
    ("bad-digest", _asset("jvm", "sha256", "A" * 64), "sha256"),
    ("short-digest", _asset("jvm", "sha256", "a" * 63), "sha256"),
    ("path-like-asset-name", _asset("jvm", "name", "../escape.jar"), "name"),
    ("slash-asset-name", _asset("jvm", "name", "bin/service"), "name"),
    ("backslash-asset-name", _asset("jvm", "name", "bin\\service"), "name"),
    ("dot-asset-name", _asset("jvm", "name", "."), "name"),
    ("empty-asset-name", _asset("jvm", "name", ""), "name"),
    ("nul-asset-name", _asset("jvm", "name", "a\x00b"), "name"),
    ("unknown-asset-field", _unknown_asset_field, "url"),
    ("duplicate-asset-names", _duplicate_name, "duplicate"),
    ("unknown-key", _set("download_url", "https://example.invalid"), "download_url"),
    ("unknown-extras-key", _unknown_extras_key, "docs"),
    ("unknown-target", _unknown_target, "macos-x64"),
    ("no-assets", _set("assets", {}), "assets"),
    ("assets-not-mapping", _set("assets", ["jvm"]), "assets"),
    ("extras-not-mapping", _set("extras", "contracts"), "extras"),
    ("non-https-repository", _set("repository", "http://github.com/spec-kitty/spec-kitty-events"), "repository"),
    ("unknown-service", _set("service", "telemetry-service"), "service"),
    ("missing-requires-core", _drop("requires_core"), "requires_core"),
    ("empty-requires-core", _set("requires_core", ""), "requires_core"),
    ("blank-requires-core", _set("requires_core", "   "), "requires_core"),
    ("missing-commit", _drop("commit"), "commit"),
    ("missing-assets", _drop("assets"), "assets"),
    ("non-string-tag", _set("tag", 1), "tag"),
]


@pytest.mark.parametrize(("mutate", "field"), [(case[1], case[2]) for case in _INVALID_CASES], ids=[case[0] for case in _INVALID_CASES])
def test_invalid_pin_refuses_naming_the_field(tmp_path: Path, mutate: Callable[[dict[str, Any]], None], field: str) -> None:
    document = _valid_document()
    mutate(document)

    with pytest.raises(ServicePinError) as excinfo:
        load_service_pin(_write_document(tmp_path, document))

    assert excinfo.value.error_code == "SERVICE_PIN_INVALID"
    assert field in str(excinfo.value)


def test_stem_mismatch_refuses(tmp_path: Path) -> None:
    path = _write_document(tmp_path, _valid_document(), name="read-service.source.yaml")

    with pytest.raises(ServicePinError, match="does not match the file name"):
        load_service_pin(path)


def test_non_mapping_document_refuses(tmp_path: Path) -> None:
    with pytest.raises(ServicePinError, match="mapping"):
        load_service_pin(_write_document(tmp_path, ["service", "write-service"]))


def test_malformed_yaml_refuses(tmp_path: Path) -> None:
    path = tmp_path / "write-service.source.yaml"
    path.write_text("service: [unclosed\n", encoding="utf-8")

    with pytest.raises(ServicePinError) as excinfo:
        load_service_pin(path)

    assert excinfo.value.error_code == "SERVICE_PIN_INVALID"


def test_missing_file_says_the_service_is_not_pinned(tmp_path: Path) -> None:
    with pytest.raises(ServicePinError, match="not pinned in this core version") as excinfo:
        load_service_pin(pin_path(tmp_path, "charter-service"))

    assert "charter-service" in str(excinfo.value)
    assert excinfo.value.error_code == "SERVICE_PIN_INVALID"


def test_messages_never_echo_a_full_digest(tmp_path: Path) -> None:
    secret_like = "f" * 63 + "Z"
    document = _valid_document()
    document["assets"]["jvm"]["sha256"] = secret_like

    with pytest.raises(ServicePinError) as excinfo:
        load_service_pin(_write_document(tmp_path, document))

    assert secret_like not in str(excinfo.value)


@pytest.mark.parametrize(
    "repository",
    [
        "http://user:ghp_SECRETtoken0123456789@github.com/spec-kitty/spec-kitty-events",
        "ssh://ghp_SECRETtoken0123456789@github.com/spec-kitty/spec-kitty-events",
        "http://ghp_SECRETtoken0123456789:x-oauth-basic@github.com/spec-kitty/spec-kitty-events",
    ],
)
def test_repository_refusal_never_shows_credentials(tmp_path: Path, repository: str) -> None:
    document = _valid_document()
    document["repository"] = repository

    with pytest.raises(ServicePinError) as excinfo:
        load_service_pin(_write_document(tmp_path, document))

    message = str(excinfo.value)
    assert "repository" in message
    assert "SECRET" not in message
    assert "ghp_" not in message
    assert "***@" in message


def test_long_values_are_truncated_in_messages(tmp_path: Path) -> None:
    long_tag = "x" * 200
    document = _valid_document()
    document["tag"] = long_tag

    with pytest.raises(ServicePinError) as excinfo:
        load_service_pin(_write_document(tmp_path, document))

    assert long_tag not in str(excinfo.value)
    assert len(str(excinfo.value)) < 200


def test_direct_construction_validates_too() -> None:
    asset = ServiceAsset(name="service.jar", sha256=_DIGEST_A)
    with pytest.raises(ServicePinError, match="commit"):
        ServicePin(
            service="write-service",
            repository="https://github.com/spec-kitty/spec-kitty-events",
            tag="service-v0.1.0",
            commit="0" * 40,
            protocol_versions=(1,),
            requires_core=">=4",
            assets={ServiceTarget.JVM: asset},
        )


def test_direct_construction_coerces_protocol_versions_to_a_tuple() -> None:
    pin = ServicePin(
        service="write-service",
        repository="https://github.com/spec-kitty/spec-kitty-events",
        tag="service-v0.1.0",
        commit=_COMMIT,
        protocol_versions=cast("tuple[int, ...]", [1, 2]),  # a list on purpose: proves the coercion
        requires_core=">=4",
        assets={ServiceTarget.JVM: ServiceAsset(name="service.jar", sha256=_DIGEST_A)},
    )

    assert pin.protocol_versions == (1, 2)
    assert isinstance(pin.protocol_versions, tuple)


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #


def test_write_then_load_round_trips_byte_stably(tmp_path: Path) -> None:
    pin = load_service_pin(_write_document(tmp_path / "", _valid_document()))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    target = out_dir / "write-service.source.yaml"

    write_service_pin(pin, target)
    first = target.read_bytes()
    reloaded = load_service_pin(target)
    write_service_pin(reloaded, target)

    assert reloaded == pin
    assert target.read_bytes() == first
    text = first.decode("utf-8")
    assert text.startswith("# Pin lockfile: which released build of this service core runs.\n")
    assert "spec-kitty service vendor" in text
    # Keys in schema order, assets sorted by target value.
    order = [text.index(f"\n{key}:") for key in ("service", "repository", "tag", "commit", "protocol_versions", "requires_core", "assets", "extras")]
    assert order == sorted(order)
    assert text.index("jvm:") < text.index("linux-x64:")


def test_write_omits_empty_extras_and_round_trips(tmp_path: Path) -> None:
    document = _valid_document()
    del document["extras"]
    pin = load_service_pin(_write_document(tmp_path, document))
    target = tmp_path / "out" / "write-service.source.yaml"
    target.parent.mkdir()

    write_service_pin(pin, target)

    assert "extras" not in target.read_text(encoding="utf-8")
    assert load_service_pin(target) == pin


# --------------------------------------------------------------------------- #
# The one tag rule, the one repository rule, the asset naming (F6)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tag", "version"),
    [
        ("service-v0.1.0", "0.1.0"),
        ("service-v0.1.0-rc.1", "0.1.0-rc.1"),
        ("service-v12.3.45", "12.3.45"),
        ("service-v0.1", None),
        ("v0.1.0", None),
        ("service-v0.1.0+build.7", None),
        ("service-v0.1.0\n", None),
    ],
)
def test_tag_version_is_the_one_tag_rule(tag: str, version: str | None) -> None:
    assert tag_version(tag) == version


@pytest.mark.parametrize(
    "repository",
    [
        "https://user:ghp_SECRETtoken0123456789@github.com/spec-kitty/spec-kitty-events",
        "https://ghp_SECRETtoken0123456789@github.com/spec-kitty/spec-kitty-events",
        "file://ghp_SECRETtoken0123456789@host/srv/releases",
    ],
)
def test_check_repository_refuses_credentials_without_echoing_them(repository: str) -> None:
    with pytest.raises(ServicePinError) as excinfo:
        check_repository(repository)
    message = str(excinfo.value)
    assert "credentials" in message
    assert "SECRET" not in message
    assert "ghp_" not in message


@pytest.mark.parametrize("repository", ["https://github.com/spec-kitty/spec-kitty-events", "file:///srv/releases"])
def test_check_repository_accepts_https_and_file(repository: str) -> None:
    check_repository(repository)


@pytest.mark.parametrize(
    "repository", ["http://github.com/o/r", "ssh://github.com/o/r", "git@github.com:o/r", "ext::sh -c x", "", "HTTPS://github.com/o/r", "File:///srv/releases"]
)
def test_check_repository_refuses_other_schemes(repository: str) -> None:
    with pytest.raises(ServicePinError, match="repository"):
        check_repository(repository)


def test_a_pin_with_a_credentialed_https_repository_refuses(tmp_path: Path) -> None:
    document = _valid_document()
    document["repository"] = "https://x-access-token:ghs_SECRET0123456789@github.com/spec-kitty/spec-kitty-events"
    with pytest.raises(ServicePinError) as excinfo:
        load_service_pin(_write_document(tmp_path, document))
    assert "credentials" in str(excinfo.value)
    assert "SECRET" not in str(excinfo.value)


def test_asset_suffix_is_derived_from_the_target() -> None:
    assert {target: target.asset_suffix for target in ServiceTarget} == {
        ServiceTarget.LINUX_X64: "-linux-x64",
        ServiceTarget.LINUX_ARM64: "-linux-arm64",
        ServiceTarget.MACOS_ARM64: "-macos-arm64",
        ServiceTarget.WINDOWS_X64: "-windows-x64.exe",
        ServiceTarget.JVM: ".jar",
    }


def test_every_known_service_has_an_asset_prefix() -> None:
    assert set(DEFAULT_ASSET_PREFIXES) == set(KNOWN_SERVICES)


def test_pin_file_names_the_lockfile_in_a_pin_directory(tmp_path: Path) -> None:
    assert pin_file(tmp_path, "write-service") == tmp_path / "write-service.source.yaml"
