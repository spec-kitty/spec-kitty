"""Tests for token substitution (WP02 T008/T009)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.template_render.substitute import (
    RULE_LEFTOVER_TOKENS,
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
    root = tmp_path / "out"
    root.mkdir()
    # Intentionally leave a different casing / second file with token after
    # "failed" replace scenario: write a file that still has token because
    # we call assert path by writing ORG token in a file that uses a typo
    # that substitute won't remove — simulate by substituting then appending.
    path = root / "note.md"
    path.write_text("keep {{ORG_NAME}} forever\n", encoding="utf-8")
    # Substitute with empty-like won't remove if we pass values but token remains
    # if we use a weird approach: write AFTER substitute in test by calling
    # leftover check via incomplete replace — actually substitute replaces all.
    # Force leftover by writing a token form that is still present: use
    # substitute then manually reintroduce.
    err = substitute_tokens(root, "acme", "pack")
    assert err is None
    path.write_text("oops {{ORG_NAME}}\n", encoding="utf-8")
    err2 = substitute_tokens(root, "acme", "pack")
    # second call should clear it again
    assert err2 is None

    # True leftover: token that isn't the exact literal we replace — we only
    # detect exact {{ORG_NAME}}. Create leftover by failing to replace because
    # file is written with token after we monkey with only leftover assert:
    from specify_cli.doctrine.template_render import substitute as sub_mod

    path.write_text("still {{ORG_NAME}}\n", encoding="utf-8")
    leftover = sub_mod._assert_no_leftovers(root)
    assert leftover is not None
    assert leftover.rule_id == RULE_LEFTOVER_TOKENS
