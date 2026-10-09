"""WP08 (#2082): ``doctor doctrine`` flags unsanctioned built-in DRG overrides.

C-005 red-first through the **public** ``doctor doctrine --json`` surface (NOT
the promoted predicate API — that is WP07's surface). C-007 realistic org-pack
fixtures: a real on-disk ``drg/fragment.yaml`` pack layout (read by
``load_org_drg``) overriding a real shipped built-in URN. NFR-001 no-org-packs
regression (the finding path stays unreachable without org packs).

The governance boundary under test (FR-010 / FR-012):

* an ``org:``-provenance override of a built-in DRG node that is NOT sanctioned
  by ``.kittify/doctrine/replaceable-builtins.yaml`` is flagged and flips the
  report unhealthy (RC=1);
* a sanctioning allowlist entry (with a reason, since the target is a built-in
  *directive*) clears the finding;
* a repo with no org packs is byte-identical to today (no ``unsanctioned_overrides``
  key emitted).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

pytestmark = pytest.mark.fast

runner = CliRunner()

# A real shipped built-in directive URN (src/charter/offering/graph.yaml). Using a real
# built-in URN (not a handcrafted placeholder) is what makes the merge record a
# same-kind ``org_override`` the gate can adjudicate (C-007).
_BUILT_IN_DIRECTIVE_URN = "directive:DIRECTIVE_001"


# ---------------------------------------------------------------------------
# Realistic on-disk org-pack fixtures (read by ``load_org_drg``).
# ---------------------------------------------------------------------------


def _write_org_override_pack(
    repo_root: Path,
    *,
    pack_dir: str = "org-pack",
    pack_name: str = "acme-org",
    node_id: str = "DIRECTIVE_001",
    sanction: str | None = None,
    legacy_template: str | None = None,
) -> Path:
    """Create a realistic org pack whose directive node id is *node_id*.

    Mirrors the on-disk org-pack layout (``drg/fragment.yaml`` + body file)
    that ``load_org_drg`` reads — distinct from a hand-built ``OrgDRGFragment``.
    With the default *node_id* the node overrides a real shipped built-in URN so
    ``merge_three_layers`` records a same-kind ``org_override`` (C-007); a fresh
    id yields a pack that overrides nothing. *sanction* is the verbatim text of
    the pack-root ``replaceable-builtins.yaml``; *legacy_template* the verbatim
    text of ``templates/setup/replaceable-builtins.yaml``.
    """
    pack_root = repo_root / pack_dir
    drg_dir = pack_root / "drg"
    directives_dir = pack_root / "directives"
    drg_dir.mkdir(parents=True)
    directives_dir.mkdir(parents=True)
    (drg_dir / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: {pack_name}
            source_kind: local_path
            source_ref: {pack_dir}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: {node_id}
                kind: directives
                title: "ACME-tightened first directive"
                body_path: directives/{node_id}.directive.yaml
            edges: []
            """
        )
    )
    (directives_dir / f"{node_id}.directive.yaml").write_text(
        dedent(
            f"""\
            id: {node_id}
            type: directive
            title: "ACME-tightened first directive"
            body: |
              Org-tier replacement for the built-in {node_id} (fixture).
            severity: binding
            status: active
            """
        )
    )
    if sanction is not None:
        (pack_root / "replaceable-builtins.yaml").write_text(sanction)
    if legacy_template is not None:
        template_dir = pack_root / "templates" / "setup"
        template_dir.mkdir(parents=True)
        (template_dir / "replaceable-builtins.yaml").write_text(legacy_template)
    return pack_root


def _write_config(repo_root: Path, pack_root: Path) -> None:
    """Write the canonical ``doctrine.org.packs`` config that ``load_org_drg`` reads."""
    _write_packs_config(repo_root, [("acme-org", pack_root)])


def _write_packs_config(
    repo_root: Path,
    packs: list[tuple[str, Path]],
    *,
    top_key: str = "doctrine",
) -> None:
    """Write several packs under ``doctrine.org.packs`` or ``charter_packs.org.packs``."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(exist_ok=True)
    entries = "".join(f'      - name: {name}\n        local_path: "{root}"\n' for name, root in packs)
    (kittify / "config.yaml").write_text(f"{top_key}:\n  org:\n    packs:\n{entries}")


def _sanction_text(*entries: tuple[str, str]) -> str:
    """Render a ``replaceable_builtins`` document from ``(urn, reason)`` pairs."""
    lines = ["replaceable_builtins:"]
    for urn, reason in entries:
        lines.append(f"  - urn: {urn}")
        lines.append(f"    reason: {json.dumps(reason)}")
    return "\n".join(lines) + "\n"


def _write_allowlist(repo_root: Path, *, reason: str) -> None:
    """Write a ``replaceable-builtins.yaml`` sanctioning the override URN."""
    _write_consumer_file(repo_root, _sanction_text((_BUILT_IN_DIRECTIVE_URN, reason)))


def _write_consumer_file(repo_root: Path, text: str) -> None:
    doctrine_dir = repo_root / ".kittify" / "doctrine"
    doctrine_dir.mkdir(parents=True, exist_ok=True)
    (doctrine_dir / "replaceable-builtins.yaml").write_text(text)


def _run_doctrine_json(repo_root: Path) -> tuple[int, dict[str, object]]:
    """Drive ``doctor doctrine --json`` and return ``(exit_code, payload)``."""
    from specify_cli.cli.commands.doctor import app as doctor_app

    with patch(
        "specify_cli.cli.commands.doctor.locate_project_root",
        return_value=repo_root,
    ):
        result = runner.invoke(doctor_app, ["doctrine", "--json"])
    try:
        payload = json.loads(result.output)
    except json.JSONDecodeError as exc:  # pragma: no cover - failure diagnostic
        pytest.fail(
            f"doctor doctrine --json did not produce valid JSON: {exc}\n"
            f"output: {result.output!r}"
        )
    return result.exit_code, payload


def _org_drg(payload: dict[str, object]) -> dict[str, object]:
    org_drg = payload.get("org_drg")
    assert isinstance(org_drg, dict), f"expected org_drg dict, got: {payload!r}"
    return org_drg


# ---------------------------------------------------------------------------
# Public-surface cases (C-005).
# ---------------------------------------------------------------------------


def test_unsanctioned_org_override_is_flagged(tmp_path: Path) -> None:
    """An unlisted org override of a built-in directive flips the report unhealthy.

    RED today: the override is invisible to the operator (no diagnostic emitted,
    RC=0). GREEN once WP08 wires the promoted predicates into the org-packs-present
    branch.
    """
    pack = _write_org_override_pack(tmp_path)
    _write_config(tmp_path, pack)

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    overrides = org_drg.get("unsanctioned_overrides", [])
    assert isinstance(overrides, list) and overrides, (
        "expected a non-empty unsanctioned_overrides finding for the unlisted "
        f"built-in override, got org_drg={org_drg!r}"
    )
    assert any(
        isinstance(o, dict) and o.get("urn") == _BUILT_IN_DIRECTIVE_URN
        for o in overrides
    ), f"expected {_BUILT_IN_DIRECTIVE_URN} in findings: {overrides!r}"

    profile_health = payload.get("profile_health")
    assert isinstance(profile_health, dict)
    assert profile_health.get("healthy") is False, (
        "an unsanctioned built-in override must flip healthy=false"
    )
    assert exit_code == 1, f"expected RC=1, got {exit_code}: {payload!r}"


def test_sanctioned_org_override_is_cleared(tmp_path: Path) -> None:
    """A sanctioning allowlist entry (with a reason) clears the finding (RC=0)."""
    pack = _write_org_override_pack(tmp_path)
    _write_config(tmp_path, pack)
    _write_allowlist(tmp_path, reason="ACME tightened the binding posture")

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert org_drg.get("unsanctioned_overrides", []) == [], (
        "a sanctioned override must NOT be flagged"
    )
    profile_health = payload.get("profile_health")
    assert isinstance(profile_health, dict)
    assert profile_health.get("healthy") is True, (
        "with the override sanctioned (and no other defects) the report is healthy"
    )
    assert exit_code == 0, f"expected RC=0, got {exit_code}: {payload!r}"


def test_no_org_packs_output_unchanged(tmp_path: Path) -> None:
    """No org packs → the finding path is unreachable; no key emitted (NFR-001)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        dedent(
            """\
            agents:
              available:
                - claude
            """
        )
    )

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert "unsanctioned_overrides" not in org_drg, (
        "the unsanctioned-override key must not appear without org packs (NFR-001)"
    )
    assert org_drg.get("configured_packs", []) == []
    assert exit_code == 0, f"expected RC=0 for a built-in-only repo, got {exit_code}"


# ---------------------------------------------------------------------------
# Pure helper coverage: ``_adjudicate_with_policy`` + ``_unsanctioned_findings``.
# ---------------------------------------------------------------------------


def _override_fragment(urn_kind: str) -> object:
    from charter.offering.drg.org_pack_loader import OrgDRGFragment

    item_id = "DIRECTIVE_001"
    return OrgDRGFragment.model_validate(
        {
            "pack_name": "acme-org",
            "source_kind": "local_path",
            "source_ref": "org-packs/acme-org",
            "layer_index": 1,
            "provenance_marker": "org",
            "nodes": [{"id": item_id, "kind": urn_kind, "title": "Override"}],
            "edges": [],
        }
    )


def test_unsanctioned_findings_flags_unlisted_directive(tmp_path: Path) -> None:
    """The extracted helper flags an unlisted built-in directive override."""
    from specify_cli.cli.commands._doctrine_collect import (
        _adjudicate_with_policy,
        _unsanctioned_findings,
    )
    from charter.offering.drg.merge import merge_three_layers
    from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind

    built_in = DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by="unit-test",
        nodes=[
            DRGNode(urn="directive:DIRECTIVE_001", kind=NodeKind.DIRECTIVE, label="Built-in")
        ],
        edges=[],
    )
    merged = merge_three_layers(
        built_in=built_in, org_fragments=[_override_fragment("directives")], project=None
    )
    built_in_urns = frozenset(n.urn for n in built_in.nodes)

    findings = _unsanctioned_findings(_adjudicate_with_policy(merged, built_in_urns, tmp_path, ()))
    assert [f["urn"] for f in findings] == ["directive:DIRECTIVE_001"]
    assert findings[0]["kind"] == "directive"
    assert "replaceable-builtins" in findings[0]["why"]


def test_unsanctioned_findings_clears_sanctioned_directive(tmp_path: Path) -> None:
    """A directive override with a non-empty reason clears via the helper."""
    from specify_cli.cli.commands._doctrine_collect import (
        _adjudicate_with_policy,
        _unsanctioned_findings,
    )
    from charter.offering.drg.merge import merge_three_layers
    from charter.offering.drg.models import DRGGraph, DRGNode, NodeKind

    built_in = DRGGraph(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by="unit-test",
        nodes=[
            DRGNode(urn="directive:DIRECTIVE_001", kind=NodeKind.DIRECTIVE, label="Built-in")
        ],
        edges=[],
    )
    merged = merge_three_layers(
        built_in=built_in, org_fragments=[_override_fragment("directives")], project=None
    )
    built_in_urns = frozenset(n.urn for n in built_in.nodes)
    _write_allowlist(tmp_path, reason="org tightened this directive")

    findings = _unsanctioned_findings(_adjudicate_with_policy(merged, built_in_urns, tmp_path, ()))
    assert findings == []


# ---------------------------------------------------------------------------
# #5767 — pack-shipped sanctions (red-first, through the real entry point).
# ---------------------------------------------------------------------------

_REASON = "ACME tightened the binding posture"
_ORG_DRG_KEYS = ("unsanctioned_overrides", "sanctioned_overrides", "pack_sanction_errors")
_UNHEALTHY_MESSAGE = "expected RC=1 / unhealthy"


def _run_doctrine_human(repo_root: Path) -> tuple[int, str]:
    """Drive the human ``doctor doctrine`` surface and return ``(exit_code, output)``."""
    from specify_cli.cli.commands.doctor import app as doctor_app

    with patch(
        "specify_cli.cli.commands.doctor.locate_project_root",
        return_value=repo_root,
    ):
        result = runner.invoke(doctor_app, ["doctrine"])
    return result.exit_code, result.output


def _tree_snapshot(root: Path) -> dict[str, bytes]:
    """Relative path -> content for every file under *root*."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _findings(org_drg: dict[str, object], key: str) -> list[dict[str, object]]:
    value = org_drg.get(key, [])
    assert isinstance(value, list)
    return [item for item in value if isinstance(item, dict)]


def _errors(org_drg: dict[str, object]) -> list[str]:
    value = org_drg.get("errors", [])
    assert isinstance(value, list)
    return [str(item) for item in value]


def _urns(org_drg: dict[str, object], key: str) -> set[object]:
    return {item.get("urn") for item in _findings(org_drg, key)}


def _single_pack_repo(
    tmp_path: Path,
    *,
    sanction: str | None = None,
    legacy_template: str | None = None,
    node_id: str = "DIRECTIVE_001",
) -> Path:
    pack = _write_org_override_pack(tmp_path, sanction=sanction, legacy_template=legacy_template, node_id=node_id)
    _write_config(tmp_path, pack)
    return pack


# -- US1 / SC-001 / FR-001 ---------------------------------------------------


def test_pack_root_sanction_clears_override_without_consumer_file(tmp_path: Path) -> None:
    """Issue #5767 reproduction: the pack's own sanction clears the override (RC=0)."""
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    before = _tree_snapshot(tmp_path / ".kittify")

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert "unsanctioned_overrides" not in org_drg
    assert _errors(org_drg) == []
    assert exit_code == 0, f"expected RC=0, got {exit_code}: {org_drg!r}"
    profile_health = payload["profile_health"]
    assert isinstance(profile_health, dict) and profile_health["healthy"] is True
    assert _tree_snapshot(tmp_path / ".kittify") == before, "consumer tree must stay byte-unchanged"


def test_pack_root_sanction_beats_stale_consumer_allowlist(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    _write_consumer_file(tmp_path, _sanction_text(("directive:SOME_OTHER_URN", "stale entry")))

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 0, _org_drg(payload)


def test_pack_root_sanction_via_charter_packs_key(tmp_path: Path) -> None:
    pack = _write_org_override_pack(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    _write_packs_config(tmp_path, [("acme-org", pack)], top_key="charter_packs")

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 0, _org_drg(payload)
    assert _urns(_org_drg(payload), "sanctioned_overrides") == {_BUILT_IN_DIRECTIVE_URN}


def test_positive_control_same_fixture_without_pack_file_is_red(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path)

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 1, _UNHEALTHY_MESSAGE
    assert _urns(_org_drg(payload), "unsanctioned_overrides") == {_BUILT_IN_DIRECTIVE_URN}


# -- FR-006 eager integrity --------------------------------------------------


def test_malformed_pack_file_is_reported_even_when_pack_overrides_nothing(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, node_id="BRAND_NEW_ORG_DIRECTIVE", sanction="replaceable_builtins: not-a-list\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    errors = _findings_as_strings(org_drg, "pack_sanction_errors")
    assert exit_code == 1
    assert len(errors) == 1 and "acme-org" in errors[0] and "replaceable-builtins.yaml" in errors[0]
    assert set(errors) <= set(_errors(org_drg)), "pack_sanction_errors must also drive errors"


def _findings_as_strings(org_drg: dict[str, object], key: str) -> list[str]:
    value = org_drg.get(key, [])
    assert isinstance(value, list)
    return [str(item) for item in value]


def test_malformed_pack_file_with_valid_consumer_sanction_lists_it_but_stays_red(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction="replaceable_builtins: not-a-list\n")
    _write_allowlist(tmp_path, reason=_REASON)

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert exit_code == 1
    assert [f["source"] for f in _findings(org_drg, "sanctioned_overrides")] == ["consumer"]
    assert "unsanctioned_overrides" not in org_drg
    assert _findings_as_strings(org_drg, "pack_sanction_errors")


def test_malformed_pack_file_keeps_other_findings(tmp_path: Path) -> None:
    pack_a = _write_org_override_pack(tmp_path, pack_dir="pack-a", pack_name="pack-a", sanction="replaceable_builtins: oops\n")
    pack_b = _write_org_override_pack(tmp_path, pack_dir="pack-b", pack_name="pack-b", node_id="DIRECTIVE_003")
    _write_packs_config(tmp_path, [("pack-a", pack_a), ("pack-b", pack_b)])

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert exit_code == 1
    assert any("pack-a" in e for e in _findings_as_strings(org_drg, "pack_sanction_errors"))
    assert _urns(org_drg, "unsanctioned_overrides") == {_BUILT_IN_DIRECTIVE_URN, "directive:DIRECTIVE_003"}


# -- malformed consumer allowlist (deliberate behaviour change) --------------


def test_malformed_consumer_allowlist_is_reported_when_no_override_exists(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, node_id="BRAND_NEW_ORG_DIRECTIVE")
    _write_consumer_file(tmp_path, "replaceable_builtins: not-a-list\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 1
    assert any("replaceable-builtins.yaml" in e for e in _errors(_org_drg(payload)))


def test_malformed_consumer_allowlist_keeps_pack_sanction_and_other_findings(tmp_path: Path) -> None:
    pack_a = _write_org_override_pack(
        tmp_path, pack_dir="pack-a", pack_name="pack-a", sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON))
    )
    pack_b = _write_org_override_pack(tmp_path, pack_dir="pack-b", pack_name="pack-b", node_id="DIRECTIVE_003")
    _write_packs_config(tmp_path, [("pack-a", pack_a), ("pack-b", pack_b)])
    _write_consumer_file(tmp_path, "replaceable_builtins: not-a-list\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert exit_code == 1
    assert [(f["urn"], f["source"]) for f in _findings(org_drg, "sanctioned_overrides")] == [(_BUILT_IN_DIRECTIVE_URN, "pack")]
    assert _urns(org_drg, "unsanctioned_overrides") == {"directive:DIRECTIVE_003"}
    assert any("replaceable-builtins.yaml" in e for e in _errors(org_drg))


def test_revocation_of_unknown_pack_is_an_error(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    _write_consumer_file(tmp_path, "revoked_pack_sanctions:\n  - pack: Acme\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert exit_code == 1
    assert any("Acme" in e for e in _errors(org_drg))
    assert _urns(org_drg, "sanctioned_overrides") == {_BUILT_IN_DIRECTIVE_URN}


def test_override_of_a_pack_with_a_broken_sanction_file_is_attributed_to_the_file(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction="replaceable_builtins: oops\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    (finding,) = _findings(org_drg, "unsanctioned_overrides")
    why = str(finding["why"])
    assert exit_code == 1
    assert "could not be read" in why and "replaceable-builtins" in why
    assert "not on" not in why


def test_override_of_a_pack_with_a_dangling_sanction_symlink_is_attributed_to_the_file(tmp_path: Path) -> None:
    pack = _single_pack_repo(tmp_path)
    try:
        (pack / "replaceable-builtins.yaml").symlink_to(tmp_path / "missing-target")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")

    exit_code, payload = _run_doctrine_json(tmp_path)

    (finding,) = _findings(_org_drg(payload), "unsanctioned_overrides")
    assert exit_code == 1
    assert "could not be read" in str(finding["why"])


# -- SC-004: the four reported URNs ------------------------------------------

_MINUTES_URNS = (
    "directive:ACTION_ITEM_ATTRIBUTION",
    "directive:MINUTES_STAND_ALONE",
    "agent_profile:minutes-mahad",
    "paradigm:extract-then-publish-separation",
)
_BUILT_IN_PACK = Path(__file__).resolve().parents[4] / "packs" / "built-in"


def _write_minutes_pack(repo_root: Path, *, with_sanction: bool) -> Path:
    """An org pack replacing the four built-in minutes artifacts with real node shapes."""
    pack_root = repo_root / "minutes-pack"
    (pack_root / "drg").mkdir(parents=True)
    bodies = {
        "ACTION_ITEM_ATTRIBUTION": ("directives", "directives/action-item-attribution.directive.yaml"),
        "MINUTES_STAND_ALONE": ("directives", "directives/minutes-stand-alone.directive.yaml"),
        "minutes-mahad": ("agent_profiles", "agent_profiles/minutes-mahad.agent.yaml"),
        "extract-then-publish-separation": ("paradigms", "paradigms/extract-then-publish-separation.paradigm.yaml"),
    }
    nodes = []
    for node_id, (kind, rel) in bodies.items():
        (pack_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_BUILT_IN_PACK / rel, pack_root / rel)
        nodes.append(f"  - id: {node_id}\n    kind: {kind}\n    title: {node_id}\n    body_path: {rel}\n")
    (pack_root / "drg" / "fragment.yaml").write_text(
        "pack_name: doctrine-org\nsource_kind: local_path\nsource_ref: minutes-pack\nlayer_index: 1\n"
        "provenance_marker: org\nnodes:\n" + "".join(nodes) + "edges: []\n"
    )
    if with_sanction:
        (pack_root / "replaceable-builtins.yaml").write_text(_sanction_text(*((urn, f"{urn} replaced by the org") for urn in _MINUTES_URNS)))
    return pack_root


def test_sc004_four_reported_urns_sanctioned_by_pack_root_file(tmp_path: Path) -> None:
    pack = _write_minutes_pack(tmp_path, with_sanction=True)
    _write_packs_config(tmp_path, [("doctrine-org", pack)])

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert exit_code == 0, org_drg
    assert _urns(org_drg, "sanctioned_overrides") == set(_MINUTES_URNS)
    assert {f["source"] for f in _findings(org_drg, "sanctioned_overrides")} == {"pack"}


def test_sc004_positive_control_without_pack_file_is_red(tmp_path: Path) -> None:
    pack = _write_minutes_pack(tmp_path, with_sanction=False)
    _write_packs_config(tmp_path, [("doctrine-org", pack)])

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 1
    assert _urns(_org_drg(payload), "unsanctioned_overrides") == set(_MINUTES_URNS)


# -- SC-002 negatives --------------------------------------------------------


def test_cross_pack_sanction_does_not_apply(tmp_path: Path) -> None:
    pack_a = _write_org_override_pack(tmp_path, pack_dir="pack-a", pack_name="pack-a")
    pack_b = _write_org_override_pack(
        tmp_path,
        pack_dir="pack-b",
        pack_name="pack-b",
        node_id="DIRECTIVE_003",
        sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON), ("directive:DIRECTIVE_003", _REASON)),
    )
    _write_packs_config(tmp_path, [("pack-a", pack_a), ("pack-b", pack_b)])

    exit_code, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    assert exit_code == 1
    assert _urns(org_drg, "unsanctioned_overrides") == {_BUILT_IN_DIRECTIVE_URN}
    assert _urns(org_drg, "sanctioned_overrides") == {"directive:DIRECTIVE_003"}


def test_directive_with_empty_pack_reason_is_unsanctioned(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, "")))

    exit_code, payload = _run_doctrine_json(tmp_path)

    findings = _findings(_org_drg(payload), "unsanctioned_overrides")
    assert exit_code == 1
    assert len(findings) == 1 and "reason" in str(findings[0]["why"])


# -- union / revocation ------------------------------------------------------


def test_consumer_and_pack_sanctions_are_unioned(tmp_path: Path) -> None:
    pack_a = _write_org_override_pack(tmp_path, pack_dir="pack-a", pack_name="pack-a")
    pack_b = _write_org_override_pack(
        tmp_path,
        pack_dir="pack-b",
        pack_name="pack-b",
        node_id="DIRECTIVE_003",
        sanction=_sanction_text(("directive:DIRECTIVE_003", _REASON)),
    )
    _write_packs_config(tmp_path, [("pack-a", pack_a), ("pack-b", pack_b)])
    _write_allowlist(tmp_path, reason=_REASON)

    exit_code, payload = _run_doctrine_json(tmp_path)

    sources = {f["urn"]: f["source"] for f in _findings(_org_drg(payload), "sanctioned_overrides")}
    assert exit_code == 0
    assert sources == {_BUILT_IN_DIRECTIVE_URN: "consumer", "directive:DIRECTIVE_003": "pack"}


def test_revoking_a_urn_withdraws_the_pack_sanction(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    _write_consumer_file(tmp_path, f"revoked_pack_sanctions:\n  - urn: {_BUILT_IN_DIRECTIVE_URN}\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    findings = _findings(_org_drg(payload), "unsanctioned_overrides")
    assert exit_code == 1
    assert len(findings) == 1 and "revoked_pack_sanctions" in str(findings[0]["why"])


def test_revoking_a_pack_withdraws_all_its_sanctions(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    _write_consumer_file(tmp_path, "revoked_pack_sanctions:\n  - pack: acme-org\n")

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 1
    assert _urns(_org_drg(payload), "unsanctioned_overrides") == {_BUILT_IN_DIRECTIVE_URN}


def test_consumer_listing_wins_over_its_own_revocation(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    _write_consumer_file(
        tmp_path,
        _sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)) + f"revoked_pack_sanctions:\n  - urn: {_BUILT_IN_DIRECTIVE_URN}\n",
    )

    exit_code, payload = _run_doctrine_json(tmp_path)

    assert exit_code == 0
    assert [f["source"] for f in _findings(_org_drg(payload), "sanctioned_overrides")] == ["consumer"]


# -- FR-008 visibility -------------------------------------------------------


def test_sanctioned_overrides_are_listed_in_json_and_human_output(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))

    _, payload = _run_doctrine_json(tmp_path)
    exit_code, output = _run_doctrine_human(tmp_path)

    assert _org_drg(payload)["sanctioned_overrides"] == [
        {"urn": _BUILT_IN_DIRECTIVE_URN, "kind": "directive", "pack": "acme-org", "source": "pack", "reason": _REASON}
    ]
    assert exit_code == 0
    assert "Sanctioned built-in override" in output
    assert "pack acme-org" in output and _BUILT_IN_DIRECTIVE_URN in output and _REASON in output


# -- FR-009 / FR-010 legacy template hint ------------------------------------

_LEGACY_REASON = "Legacy template reason"


def test_legacy_template_stays_red_and_prints_actionable_hint(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, legacy_template=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _LEGACY_REASON)))

    exit_code, payload = _run_doctrine_json(tmp_path)
    human_code, output = _run_doctrine_human(tmp_path)

    (finding,) = _findings(_org_drg(payload), "unsanctioned_overrides")
    legacy = finding["legacy_template"]
    assert isinstance(legacy, dict) and legacy["reason"] == _LEGACY_REASON
    assert str(legacy["path"]).endswith("templates/setup/replaceable-builtins.yaml")
    assert exit_code == human_code == 1
    assert "templates/setup/replaceable-builtins.yaml" in output
    assert "replaceable-builtins.yaml" in output and "move" in output
    assert f"- urn: {_BUILT_IN_DIRECTIVE_URN}" in output
    assert f"reason: {_LEGACY_REASON}" in output
    assert "cp " not in output
    assert "> .kittify/charter-packs/replaceable-builtins.yaml" not in output


def test_malformed_legacy_template_gives_no_hint_and_no_error(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, legacy_template="replaceable_builtins: [unclosed\n")

    _, payload = _run_doctrine_json(tmp_path)

    org_drg = _org_drg(payload)
    (finding,) = _findings(org_drg, "unsanctioned_overrides")
    assert "legacy_template" not in finding
    assert all("templates/setup" not in e for e in _errors(org_drg))


def test_legacy_template_directive_without_reason_says_reason_required(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, legacy_template=_sanction_text((_BUILT_IN_DIRECTIVE_URN, "")))

    _, output = _run_doctrine_human(tmp_path)

    assert "reason is required" in output
    assert f"- urn: {_BUILT_IN_DIRECTIVE_URN}" not in output


def test_generic_hint_names_both_remedies(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path)

    _, output = _run_doctrine_human(tmp_path)

    assert ".kittify/charter-packs/replaceable-builtins.yaml" in output
    assert "pack-root" in output or "pack root" in output


# -- NFR-005 safe output -----------------------------------------------------


def test_rich_markup_in_paths_and_reasons_is_printed_literally(tmp_path: Path) -> None:
    pack = _write_org_override_pack(
        tmp_path,
        pack_dir="org[bold]pack",
        legacy_template=_sanction_text((_BUILT_IN_DIRECTIVE_URN, "[red]x[/red]")),
    )
    _write_config(tmp_path, pack)
    _, unsanctioned_output = _run_doctrine_human(tmp_path)

    (pack / "replaceable-builtins.yaml").write_text(_sanction_text((_BUILT_IN_DIRECTIVE_URN, "[red]x[/red]")))
    _, sanctioned_output = _run_doctrine_human(tmp_path)

    assert "org[bold]pack" in unsanctioned_output and "[red]x[/red]" in unsanctioned_output
    assert "[red]x[/red]" in sanctioned_output


# -- FR-012 no-org-packs output unchanged -----------------------------------

_NO_PACKS_HUMAN = """\
No org doctrine configured.
Add a 'charter_packs.org' block to .kittify/config.yaml to register a pack.

Selections (active globally-selected artifacts):
  directives: (none)
  tactics: (none)
  paradigms: (none)
  styleguides: (none)
  toolguides: (none)
  procedures: (none)
  mission_step_contracts: (none)
  agent_profiles: (none)
Active charter (activated artifacts): spec-kitty charter list
"""
_NO_PACKS_ORG_DRG: dict[str, object] = {
    "configured_packs": [],
    "collision_warnings": [],
    "dangling_endpoints": [],
    "errors": [],
    "operating_procedures_unresolved": [],
}


def _write_no_pack_config(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n")


def test_no_org_packs_output_is_byte_identical_to_pre_change_snapshot(tmp_path: Path) -> None:
    _write_no_pack_config(tmp_path)

    json_code, payload = _run_doctrine_json(tmp_path)
    human_code, human = _run_doctrine_human(tmp_path)

    assert json_code == human_code == 0
    assert human == _NO_PACKS_HUMAN
    assert _org_drg(payload) == _NO_PACKS_ORG_DRG
    assert list(payload) == ["org_configured", "packs", "selections", "org_drg", "profile_health"]
    profile_health = payload["profile_health"]
    assert isinstance(profile_health, dict)
    assert list(profile_health) == ["healthy", "packs", "org_drg", "glossary_packs", "skills"]


# -- characterisation pin of today's unsanctioned block ----------------------


def test_unsanctioned_human_block_characterisation(tmp_path: Path) -> None:
    """Pins the header, generic hint and project-tier hint of the unsanctioned block."""
    _single_pack_repo(tmp_path)

    exit_code, output = _run_doctrine_human(tmp_path)

    assert exit_code == 1
    assert "Unsanctioned built-in override(s) — 1 not allowlisted" in output
    assert f"{_BUILT_IN_DIRECTIVE_URN} (directive)" in output
    assert (
        "Add the URN to .kittify/charter-packs/replaceable-builtins.yaml (with a reason for directives), have the overriding pack "
        "ship it in its pack-root replaceable-builtins.yaml, or remove the org override."
    ) in output
    assert "Only org-tier overrides are adjudicated; project-tier (.kittify/doctrine/) overrides are intentionally ungoverned (FR-012)." in output


# -- NFR-001 bounded I/O ------------------------------------------------------


def test_doctor_reads_each_pack_sanction_file_exactly_once(tmp_path: Path) -> None:
    """NFR-001: one sanction-file read per configured pack, counted not timed."""
    from charter.offering.drg import override_policy

    pack_a = _write_org_override_pack(tmp_path, pack_dir="pack-a", pack_name="pack-a", sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))
    pack_b = _write_org_override_pack(
        tmp_path, pack_dir="pack-b", pack_name="pack-b", node_id="DIRECTIVE_003", sanction=_sanction_text(("directive:DIRECTIVE_003", _REASON))
    )
    _write_packs_config(tmp_path, [("pack-a", pack_a), ("pack-b", pack_b)])
    real_read = override_policy._read_policy_file
    reads: list[str] = []

    def counting_read(path: Path, **kwargs: object) -> object:
        reads.append(str(path))
        return real_read(path, source_label=str(kwargs["source_label"]), allow_revocations=bool(kwargs["allow_revocations"]))

    with patch.object(override_policy, "_read_policy_file", counting_read):
        exit_code, _ = _run_doctrine_json(tmp_path)

    assert exit_code == 0
    assert sorted(reads) == sorted([str(pack_a / "replaceable-builtins.yaml"), str(pack_b / "replaceable-builtins.yaml")])


# -- human policy-error block (FR-006 / FR-007, NFR-005) ----------------------


def test_policy_error_block_lists_pack_and_revocation_errors_without_duplicates(tmp_path: Path) -> None:
    pack_a = _write_org_override_pack(tmp_path, pack_dir="pack[bold]a", pack_name="pack-a", sanction="replaceable_builtins: oops\n")
    pack_b = _write_org_override_pack(tmp_path, pack_dir="pack-b", pack_name="pack-b", node_id="DIRECTIVE_003")
    _write_packs_config(tmp_path, [("pack-a", pack_a), ("pack-b", pack_b)])
    _write_consumer_file(tmp_path, "revoked_pack_sanctions:\n  - pack: Nope\n")

    exit_code, output = _run_doctrine_human(tmp_path)

    block = output.split("Override sanction file error(s)", 1)[1].split("Unsanctioned built-in override(s)", 1)[0]
    assert exit_code == 1
    assert "Override sanction file error(s) — 2" in output
    assert "pack-a" in block and "pack[bold]a" in block, "pack path must be printed literally (escaped)"
    assert "revoked_pack_sanctions names pack 'Nope'" in block
    assert "unsanctioned built-in override:" not in block, "generic error lines must not be duplicated here"


def test_policy_error_block_is_absent_when_policy_files_are_well_formed(tmp_path: Path) -> None:
    _single_pack_repo(tmp_path, sanction=_sanction_text((_BUILT_IN_DIRECTIVE_URN, _REASON)))

    _, output = _run_doctrine_human(tmp_path)

    assert "Override sanction file error" not in output


def test_legacy_move_target_uses_path_semantics_for_windows_separators() -> None:
    from pathlib import PurePosixPath, PureWindowsPath

    from specify_cli.cli.commands.doctor import _legacy_move_target

    windows = PureWindowsPath("C:\\packs\\acme\\templates\\setup\\replaceable-builtins.yaml")
    assert _legacy_move_target(windows) == PureWindowsPath("C:\\packs\\acme\\replaceable-builtins.yaml")
    posix = PurePosixPath("/packs/acme/templates/setup/replaceable-builtins.yaml")
    assert _legacy_move_target(posix) == PurePosixPath("/packs/acme/replaceable-builtins.yaml")
    odd = PurePosixPath("/elsewhere/file.yaml")
    assert _legacy_move_target(odd) == PurePosixPath("/elsewhere/replaceable-builtins.yaml")


def test_legacy_entry_lines_use_shared_renderer_and_reason_rule() -> None:
    from specify_cli.cli.commands.doctor import _legacy_entry_lines

    directive = {"urn": "directive:DIRECTIVE_001", "kind": "directive"}
    assert _legacy_entry_lines(directive, {"reason": "  "}) is None
    assert _legacy_entry_lines(directive, {"reason": "because"}) == [
        "replaceable_builtins:",
        "- urn: directive:DIRECTIVE_001",
        "  reason: because",
    ]
    assert _legacy_entry_lines({"urn": "tactic:t", "kind": "tactic"}, {}) == ["replaceable_builtins:", "- urn: tactic:t"]


def test_legacy_organisation_packs_deprecation_warns_at_most_once(tmp_path: Path) -> None:
    import warnings

    from specify_cli.cli.commands._doctrine_collect import _collect_org_layer_data

    pack = _write_org_override_pack(tmp_path, sanction=None)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(f'organisation_packs:\n  - name: acme-org\n    path: "{pack}"\n')

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _collect_org_layer_data(tmp_path)

    legacy = [w for w in caught if issubclass(w.category, DeprecationWarning) and "organisation_packs" in str(w.message)]
    assert len(legacy) <= 1
