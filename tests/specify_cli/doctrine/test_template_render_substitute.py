"""Tests for token substitution (WP02 T008/T009)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.template_render.substitute import (
    RULE_LEFTOVER_TOKENS,
    RULE_PATH_TOKEN,
    substitute_tokens,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_substitute_replaces_both_tokens(tmp_path: Path) -> None:
    root = tmp_path / "out"
    root.mkdir()
    target = root / "pack" / "org-charter.yaml"
    target.parent.mkdir()
    target.write_text(
        'org_name: "{{ORG_NAME}}"\nsource: "{{LOCAL_PATH}}"\n',
        encoding="utf-8",
    )
    (root / "bin.dat").write_bytes(b"\xff\xfe\x00{{ORG_NAME}}")

    err = substitute_tokens(root, "acme-corp", "pack")
    assert err is None
    text = target.read_text(encoding="utf-8")
    assert "{{ORG_NAME}}" not in text
    assert "{{LOCAL_PATH}}" not in text
    assert "acme-corp" in text
    assert "pack" in text
    # binary left unchanged
    assert b"{{ORG_NAME}}" in (root / "bin.dat").read_bytes()


def test_substitute_fails_on_leftover_tokens(tmp_path: Path) -> None:
    """Single-pass leftover: replacement values that reintroduce placeholders."""
    root = tmp_path / "out"
    root.mkdir()
    path = root / "note.md"
    path.write_text("keep {{ORG_NAME}} forever\n", encoding="utf-8")
    err = substitute_tokens(root, "{{ORG_NAME}}", "pack")
    assert err is not None
    assert err.rule_id == RULE_LEFTOVER_TOKENS


def test_substitute_rejects_path_token_in_filename(tmp_path: Path) -> None:
    root = tmp_path / "out"
    root.mkdir()
    bad = root / "{{ORG_NAME}}.yaml"
    bad.write_text("ok\n", encoding="utf-8")
    err = substitute_tokens(root, "acme-corp", "pack")
    assert err is not None
    assert err.rule_id == RULE_PATH_TOKEN
    assert "{{ORG_NAME}}.yaml" in err.message


def test_substitute_rejects_path_token_in_dirname(tmp_path: Path) -> None:
    root = tmp_path / "out"
    nested = root / "dir-{{LOCAL_PATH}}"
    nested.mkdir(parents=True)
    (nested / "file.yaml").write_text("x\n", encoding="utf-8")
    err = substitute_tokens(root, "acme-corp", "pack")
    assert err is not None
    assert err.rule_id == RULE_PATH_TOKEN
