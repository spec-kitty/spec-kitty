"""Unit guard for ``charter.activation.scope._load_charter_scope_config`` (#4600, #5620).

The reader is a pure file reader, so these tests use real files under ``tmp_path``
instead of mocking it. A non-UTF-8 or malformed ``.kittify/config.yaml`` must fail
loud with ``CharterPackConfigError`` naming the file, never degrade silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.pack_context import CharterPackConfigError
from charter.activation.scope import CharterScopeConfig, _load_charter_scope_config

pytestmark = [pytest.mark.fast, pytest.mark.unit]


def _write_config(repo_root: Path, payload: bytes) -> Path:
    config_path = repo_root / ".kittify" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(payload)
    return config_path


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(b"\xff\xfe not utf-8", id="non-utf8"),
        pytest.param(b"scopes: [unclosed", id="malformed-yaml"),
    ],
)
def test_unreadable_config_raises_error_naming_the_file(tmp_path: Path, payload: bytes) -> None:
    config_path = _write_config(tmp_path, payload)

    with pytest.raises(CharterPackConfigError) as excinfo:
        _load_charter_scope_config(tmp_path)

    assert str(config_path) in excinfo.value.body


def test_absent_config_returns_none(tmp_path: Path) -> None:
    assert _load_charter_scope_config(tmp_path) is None


def test_non_mapping_yaml_returns_default_config(tmp_path: Path) -> None:
    _write_config(tmp_path, b"- a\n- b\n")

    assert _load_charter_scope_config(tmp_path) == CharterScopeConfig()


def test_valid_mapping_is_validated_into_config(tmp_path: Path) -> None:
    _write_config(tmp_path, b"charter_scopes:\n  - root: packages/auth\n    name: auth\n")

    config = _load_charter_scope_config(tmp_path)

    assert config is not None
    assert config.charter_scopes[0].root == "packages/auth"
