"""Parity: the charter-layer readers and ``load_org_charter_policies`` share one merge rule.

``required_<kind>`` is a first-seen-order union and ``skill_namespace`` is
last-non-empty-wins; ``charter.activation.org_pack_discovery`` owns both rules
and ``specify_cli.doctrine.org_charter`` delegates to them. This pins that the
two views agree on a multi-pack fixture (incl. a blank namespace, duplicate ids and a
non-list ``required_skills`` that both skip), declared through the canonical
``charter_packs.org.packs`` key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.org_pack_discovery import (
    read_org_required_ids,
    read_org_skill_namespace,
)
from charter.offering.artifact_kinds import ArtifactKind
from specify_cli.doctrine.org_charter import load_org_charter_policies

pytestmark = [pytest.mark.unit, pytest.mark.fast]

PACK_A = """\
schema_version: "1"
org_name: "A"
skill_namespace: "alpha"
required_skills: [shared, only-a]
required_directives: [DIRECTIVE_001]
"""
PACK_B = """\
schema_version: "1"
org_name: "B"
skill_namespace: "   "
required_skills: [only-b, shared]
required_directives: [DIRECTIVE_002, DIRECTIVE_001]
"""
PACK_C = """\
schema_version: "1"
skill_namespace: " gamma "
required_skills: [only-c]
"""
PACK_D = """\
schema_version: "1"
required_skills: not-a-list
"""


def _project(tmp_path: Path) -> Path:
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, body in (("a", PACK_A), ("b", PACK_B), ("c", PACK_C), ("d", PACK_D)):
        pack = tmp_path / f"pack-{name}"
        pack.mkdir()
        (pack / "org-charter.yaml").write_text(body, encoding="utf-8")
        lines += [f"      - name: {name}", f"        local_path: {pack}"]
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_both_views_agree_on_a_multi_pack_fixture(tmp_path: Path) -> None:
    root = _project(tmp_path)
    policy = load_org_charter_policies(root)

    assert read_org_required_ids(root, ArtifactKind.SKILL) == policy.required_skills == ["shared", "only-a", "only-b", "only-c"]
    assert read_org_required_ids(root, ArtifactKind.DIRECTIVE) == policy.required_directives == ["DIRECTIVE_001", "DIRECTIVE_002"]
    assert read_org_skill_namespace(root) == policy.skill_namespace == "gamma"


def test_blank_namespace_never_clears_an_earlier_one(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (tmp_path / "pack-c" / "org-charter.yaml").write_text(PACK_C.replace('" gamma "', '""'), encoding="utf-8")
    assert read_org_skill_namespace(root) == load_org_charter_policies(root).skill_namespace == "alpha"
