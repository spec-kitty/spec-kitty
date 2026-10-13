"""Unit coverage for the shared charter-pack gitignore helper + migration edges (#6076).

The behavioural ATDD anchor lives in ``test_track_charter_pack_yaml.py``; this
module pins the helper's branch coverage directly (CLAUDE.md: "every new
branch/helper needs tests in the same PR") — line-ending preservation, the
end-of-file-without-newline anchor, allow-rule grouping and last-blanket
anchoring — plus the migration's unsafe-``.gitignore`` and missing-file edges.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.upgrade.migrations._charter_pack_gitignore import (
    CHARTER_PACK_YAML_ALLOW_RULE,
    ensure_pack_yaml_allow_rule,
    needs_pack_yaml_allow_rule,
)
from specify_cli.upgrade.migrations.m_4_0_0rc7_track_charter_pack_yaml import (
    TrackCharterPackYamlMigration,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_BLANKET = ".kittify/charter-packs/**"
_GRAPH_ALLOW = "!.kittify/charter-packs/graph.yaml"
_PACK_ALLOW = "!.kittify/charter-packs/pack.yaml"
_ANCHORED_BLANKET = "/.kittify/charter-packs/**"
_ANCHORED_PACK_ALLOW = "!/.kittify/charter-packs/pack.yaml"


# ---------------------------------------------------------------------------
# needs_pack_yaml_allow_rule — the "where the blanket rule is present" predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"{_BLANKET}\n{_GRAPH_ALLOW}\n", True),  # post-cutover bug state
        (f"{_BLANKET}\n{_GRAPH_ALLOW}\n{_PACK_ALLOW}\n", False),  # already allowed
        (f"{_ANCHORED_BLANKET}\n", True),  # rc6 cutover keeps a legacy anchored rule anchored (#6076)
        (f"{_ANCHORED_BLANKET}\n{_ANCHORED_PACK_ALLOW}\n", False),  # anchored allow-rule present
        (".kittify/charter-packs/\n", False),  # directory form: a negation could not re-include
        ("build/\n.venv/\n", False),  # no blanket rule → not our concern
        ("", False),
    ],
)
def test_needs_predicate(text: str, expected: bool) -> None:
    assert needs_pack_yaml_allow_rule(text) is expected


# ---------------------------------------------------------------------------
# ensure_pack_yaml_allow_rule — placement, line endings, idempotency
# ---------------------------------------------------------------------------


def test_inserts_after_the_graph_allow_rule_grouped() -> None:
    lines = [f"{_BLANKET}\n", f"{_GRAPH_ALLOW}\n", "build/\n"]
    out, changed = ensure_pack_yaml_allow_rule(lines)
    assert changed is True
    # Grouped with its sibling allow-rule, before the unrelated entry.
    assert [line.rstrip("\n") for line in out] == [_BLANKET, _GRAPH_ALLOW, _PACK_ALLOW, "build/"]


def test_anchored_blanket_gets_the_anchored_allow_rule() -> None:
    out, changed = ensure_pack_yaml_allow_rule([f"{_ANCHORED_BLANKET}\n", "!/.kittify/charter-packs/graph.yaml\n", "build/\n"])
    assert changed is True
    assert [line.rstrip("\n") for line in out] == [_ANCHORED_BLANKET, "!/.kittify/charter-packs/graph.yaml", _ANCHORED_PACK_ALLOW, "build/"]


def test_inserts_directly_after_a_standalone_blanket_rule() -> None:
    out, changed = ensure_pack_yaml_allow_rule([f"{_BLANKET}\n"])
    assert changed is True
    assert [line.rstrip("\n") for line in out] == [_BLANKET, _PACK_ALLOW]


def test_anchors_on_the_last_blanket_rule() -> None:
    lines = [f"{_BLANKET}\n", "mid\n", f"{_BLANKET}\n", f"{_GRAPH_ALLOW}\n"]
    out, _ = ensure_pack_yaml_allow_rule(lines)
    # The allow-rule must follow the LAST blanket rule so the negation wins.
    assert out.index(f"{_PACK_ALLOW}\n") == 4


def test_preserves_crlf_line_endings() -> None:
    lines = [f"{_BLANKET}\r\n", f"{_GRAPH_ALLOW}\r\n"]
    out, changed = ensure_pack_yaml_allow_rule(lines)
    assert changed is True
    assert f"{_PACK_ALLOW}\r\n" in out
    assert all(line.endswith("\r\n") for line in out)


def test_adds_newline_to_anchor_without_trailing_newline() -> None:
    # Blanket rule is the final line and lacks a trailing newline (EOF).
    lines = [f"{_GRAPH_ALLOW}\n", _BLANKET]
    out, changed = ensure_pack_yaml_allow_rule(lines)
    assert changed is True
    # The anchor gained a newline so the inserted rule lands on its own line.
    assert out == [f"{_GRAPH_ALLOW}\n", f"{_BLANKET}\n", f"{_PACK_ALLOW}\n"]


def test_noop_when_blanket_absent() -> None:
    lines = ["build/\n", ".venv/\n"]
    out, changed = ensure_pack_yaml_allow_rule(lines)
    assert changed is False
    assert out is lines


def test_noop_when_already_allowed() -> None:
    lines = [f"{_BLANKET}\n", f"{_PACK_ALLOW}\n"]
    out, changed = ensure_pack_yaml_allow_rule(lines)
    assert changed is False
    assert out is lines


# ---------------------------------------------------------------------------
# Migration edges — unsafe/missing .gitignore
# ---------------------------------------------------------------------------


def test_missing_gitignore_is_a_clean_noop(tmp_path: Path) -> None:
    migration = TrackCharterPackYamlMigration()
    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)
    assert result.success is True
    assert not result.changes_made


def test_symlinked_gitignore_detect_fails_closed(tmp_path: Path) -> None:
    """A symlinked .gitignore raises (fail-closed select), never followed silently."""
    target = tmp_path / "real_rules"
    target.write_text(f"{_BLANKET}\n{_GRAPH_ALLOW}\n", encoding="utf-8")
    os.symlink(target, tmp_path / ".gitignore")

    with pytest.raises(GitignorePathError):
        TrackCharterPackYamlMigration().detect(tmp_path)


def test_symlinked_gitignore_apply_is_nonfatal_and_untouched(tmp_path: Path) -> None:
    """apply() warns and leaves the symlink untouched rather than failing the upgrade."""
    target = tmp_path / "real_rules"
    target.write_text(f"{_BLANKET}\n{_GRAPH_ALLOW}\n", encoding="utf-8")
    link = tmp_path / ".gitignore"
    os.symlink(target, link)

    result = TrackCharterPackYamlMigration().apply(tmp_path)

    assert result.success is True
    assert not result.changes_made
    assert result.warnings and CHARTER_PACK_YAML_ALLOW_RULE in result.warnings[0]
    assert link.is_symlink()  # never followed / rewritten
