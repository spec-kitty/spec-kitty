"""Tests for ``specify_cli.doctrine.pack_validator``.

These tests build minimal, schema-valid artifact fixtures in ``tmp_path`` and
exercise :func:`validate_pack` against each of the documented error categories.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from specify_cli.doctrine.pack_validator import (
    ValidationResult,
    _check_profile_skipped_diagnostics,
    render_validation_result,
    validate_pack,
)

_yaml = YAML(typ="safe")
_yaml.default_flow_style = False


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]

def _write_directive(
    pack_dir: Path,
    *,
    artifact_id: str,
    filename: str | None = None,
    title: str = "Example",
    drop_title: bool = False,
) -> Path:
    """Write a minimal, schema-valid directive YAML file."""
    directives = pack_dir / "directives"
    directives.mkdir(parents=True, exist_ok=True)
    body_lines = [
        'schema_version: "1.0"',
        f"id: {artifact_id}",
    ]
    if not drop_title:
        body_lines.append(f"title: {title}")
    body_lines.extend(
        [
            "intent: A short description.",
            "enforcement: advisory",
        ]
    )
    name = filename or f"{artifact_id.lower()}.directive.yaml"
    path = directives / name
    path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    return path


def _write_asset_manifest(
    pack_dir: Path,
    *,
    artifact_id: str | None,
    mime: str | None = "image/png",
    path_value: str | None = "branding/acme-logo.png",
    title: str | None = "Acme brand logo (PNG)",
    filename: str | None = None,
    drop_id: bool = False,
    subdir: str | None = None,
) -> Path:
    """Write a ``*.asset.yaml`` sidecar manifest under ``pack_dir/assets/``.

    Realistic, production-shaped defaults (a real PNG-shaped manifest) —
    callers override individual fields to exercise a single failure mode.

    ``subdir``, when given, nests the manifest one directory below
    ``assets/`` (e.g. ``assets/<subdir>/x.asset.yaml``) — the ADR-mandated
    org-pack manifest layout (FR-003) that ``AssetRepository`` already
    recurses into.
    """
    assets = pack_dir / "assets" / subdir if subdir else pack_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {}
    if not drop_id and artifact_id is not None:
        payload["id"] = artifact_id
    if mime is not None:
        payload["mime"] = mime
    if path_value is not None:
        payload["path"] = path_value
    if title is not None:
        payload["title"] = title
    name = filename or f"{(artifact_id or 'manifest').lower()}.asset.yaml"
    manifest_path = assets / name
    _yaml.dump(payload, manifest_path)
    return manifest_path


def _write_agent_profile_yaml(
    pack_dir: Path,
    *,
    filename: str,
    content: str,
) -> Path:
    """Write a raw ``*.agent.yaml`` file under ``pack_dir/agent_profiles/``.

    Takes a pre-formatted YAML string (rather than a dict payload, unlike the
    other ``_write_*`` helpers here) so callers can author fixtures whose
    exact on-disk shape matters (e.g. the deprecated scalar ``role:`` field,
    which a dict-based writer using ``roles:`` could not represent).
    """
    agent_profiles = pack_dir / "agent_profiles"
    agent_profiles.mkdir(parents=True, exist_ok=True)
    path = agent_profiles / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestValidatePack:
    def test_nonexistent_pack_dir(self, tmp_path: Path) -> None:
        result = validate_pack(tmp_path / "does-not-exist")
        assert result.ok is False
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].message

    def test_empty_pack(self, tmp_path: Path) -> None:
        # A pack with no artifact files at all is valid.
        result = validate_pack(tmp_path)
        assert result.ok is True
        assert result.errors == []

    def test_valid_pack_single_type(self, tmp_path: Path) -> None:
        _write_directive(tmp_path, artifact_id="ACME-001")
        _write_directive(tmp_path, artifact_id="ACME-002")

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        assert result.errors == []

    def test_schema_violation(self, tmp_path: Path) -> None:
        _write_directive(
            tmp_path,
            artifact_id="ACME-003",
            drop_title=True,
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        assert any(
            issue.artifact_type == "directives" for issue in result.errors
        )

    def test_duplicate_id(self, tmp_path: Path) -> None:
        _write_directive(
            tmp_path,
            artifact_id="ACME-004",
            filename="first.directive.yaml",
        )
        _write_directive(
            tmp_path,
            artifact_id="ACME-004",
            filename="second.directive.yaml",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        duplicate_errors = [
            e for e in result.errors if "duplicate id" in e.message
        ]
        assert len(duplicate_errors) == 1
        assert duplicate_errors[0].artifact_id == "ACME-004"

    def test_dangling_drg_edge(self, tmp_path: Path) -> None:
        # A pack with a DRG fragment that points at a URN nobody knows about.
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-broken.graph.yaml").write_text(
            textwrap.dedent(
                """\
                schema_version: "1.0"
                generated_at: STATIC
                generated_by: test
                nodes: []
                edges:
                  - source: directive:does-not-exist
                    target: directive:also-missing
                    relation: requires
                """
            ),
            encoding="utf-8",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        dangling = [
            e
            for e in result.errors
            if e.artifact_type == "drg" and "dangling" in e.message.lower()
        ]
        assert dangling, result.errors

    def test_drg_fragment_stray_top_level_key_reports_structured_issue(
        self, tmp_path: Path
    ) -> None:
        # A DRG fragment declaring a top-level key ``DRGGraph`` does not define
        # raises ``DRGGraphSchemaError`` at the load boundary (T009, NFR-006).
        # ``validate_pack`` must surface this as a structured ``ValidationIssue``
        # (category ``schema_invalid``) rather than let the exception escape as
        # an uncaught traceback (#3062).
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-stray-key.graph.yaml").write_text(
            textwrap.dedent(
                """\
                schema_version: "1.0"
                generated_at: STATIC
                generated_by: test
                nodes: []
                edges: []
                not_a_real_field: surprise
                """
            ),
            encoding="utf-8",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        schema_errors = [
            e
            for e in result.errors
            if e.artifact_type == "drg" and e.category == "schema_invalid"
        ]
        assert schema_errors, result.errors
        assert "not_a_real_field" in schema_errors[0].message
        assert schema_errors[0].file == str(drg / "010-stray-key.graph.yaml")

    def test_drg_edge_resolves_against_pack_artifacts(
        self, tmp_path: Path
    ) -> None:
        # Edge URNs that resolve to the pack's own directives must NOT error.
        _write_directive(tmp_path, artifact_id="ACME-100")
        _write_directive(tmp_path, artifact_id="ACME-101")
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-edges.graph.yaml").write_text(
            textwrap.dedent(
                """\
                schema_version: "1.0"
                generated_at: STATIC
                generated_by: test
                nodes: []
                edges:
                  - source: directive:ACME-100
                    target: directive:ACME-101
                    relation: requires
                """
            ),
            encoding="utf-8",
        )

        # check_drg_root=False: this test is about edge-URN resolution
        # against pack artifacts, orthogonal to FR-004's pack-root-graph
        # check — the fixture is deliberately drg/-fragments-only.
        result = validate_pack(tmp_path, check_drg_root=False)

        assert result.ok is True, result.errors

    def test_duplicate_drg_edge_advisory(self, tmp_path: Path) -> None:
        _write_directive(tmp_path, artifact_id="ACME-200")
        _write_directive(tmp_path, artifact_id="ACME-201")
        drg = tmp_path / "drg"
        drg.mkdir()
        edge_yaml = textwrap.dedent(
            """\
            schema_version: "1.0"
            generated_at: STATIC
            generated_by: test
            nodes: []
            edges:
              - source: directive:ACME-200
                target: directive:ACME-201
                relation: requires
            """
        )
        (drg / "010-a.graph.yaml").write_text(edge_yaml, encoding="utf-8")
        (drg / "020-b.graph.yaml").write_text(edge_yaml, encoding="utf-8")

        # check_drg_root=False: this test is about the duplicate-edge
        # advisory, orthogonal to FR-004's pack-root-graph check — the
        # fixture is deliberately drg/-fragments-only.
        result = validate_pack(tmp_path, check_drg_root=False)

        # The duplicate is advisory, not fatal.
        assert result.ok is True, result.errors
        advisories = [
            a for a in result.advisories if "duplicate edge" in a.message
        ]
        assert advisories

    def test_built_in_id_collision_advisory(self, tmp_path: Path) -> None:
        # Use a known shipped directive id so the advisory fires.  If shipped
        # doctrine is absent in this environment, the test simply has no
        # advisory to assert (validation should still pass) — keep the test
        # tolerant of stripped envs.
        _write_directive(tmp_path, artifact_id="DIRECTIVE_001")

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        # Advisory presence depends on whether shipped doctrine is on disk.
        # FR-013 (WP06): reworded message uses "field-merge" wording and
        # surfaces both ``enhances`` and ``overrides`` recommendations.
        for advisory in result.advisories:
            if advisory.artifact_id == "DIRECTIVE_001":
                assert advisory.category == "same_id_collision"
                assert "field-merge" in advisory.message
                assert "enhances: DIRECTIVE_001" in advisory.message
                assert "overrides: DIRECTIVE_001" in advisory.message
                break

    def test_returns_validation_result_type(self, tmp_path: Path) -> None:
        result = validate_pack(tmp_path)
        assert isinstance(result, ValidationResult)
        # ``to_dict`` is part of the public surface used by the CLI.
        payload = result.to_dict()
        assert set(payload.keys()) == {"ok", "errors", "advisories"}


# ---------------------------------------------------------------------------
# WP06: intent-aware collision message tests (FR-011, FR-012, FR-013)
# ---------------------------------------------------------------------------


# A canonical shipped tactic id used by the WP06 test matrix. The auto-emit
# and intent-aware passes resolve against the live shipped doctrine on disk,
# so the id must point at an actual built-in tactic.
_BUILT_IN_TACTIC_ID = "adversarial-qa-handoff"


def _assert_built_in_fixture_tactic_present() -> None:
    """Fail loudly if the fixture built-in tactic ever disappears.

    Packs always ship (``charter.offering.pack_paths.built_in_dir`` fails
    closed with ``PackRootNotFound`` when the built-in tree is absent), so a
    "skip if absent" probe around this fixture was always either dead or
    masking a real bug (#5346/#5353). This precondition assert replaces that
    probe: it never skips, it fails the test with a clear message naming the
    missing fixture path.
    """
    path = built_in_dir(ArtifactKind.TACTIC) / f"{_BUILT_IN_TACTIC_ID}.tactic.yaml"
    assert path.is_file(), (
        f"fixture tactic {_BUILT_IN_TACTIC_ID!r} missing from shipped "
        f"built-ins at {path}"
    )


def _write_tactic(
    pack_dir: Path,
    *,
    artifact_id: str,
    overrides: str | None = None,
    enhances: str | None = None,
) -> Path:
    """Write a minimal, schema-valid tactic YAML file with optional augmentation fields."""
    tactics = pack_dir / "tactics"
    tactics.mkdir(parents=True, exist_ok=True)
    body_lines = [
        'schema_version: "1.0"',
        f"id: {artifact_id}",
        f"name: {artifact_id.title().replace('-', ' ')}",
    ]
    if overrides is not None:
        body_lines.append(f"overrides: {overrides}")
    if enhances is not None:
        body_lines.append(f"enhances: {enhances}")
    body_lines.extend(
        [
            "steps:",
            "  - title: Single test step",
        ]
    )
    path = tactics / f"{artifact_id}.tactic.yaml"
    path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")
    return path


def _write_drg_intent(pack_dir: Path, *, artifact_id: str, relation: str) -> Path:
    """Write a ``drg/*.graph.yaml``-shaped intent edge.

    Retained only for :func:`test_drg_only_fragment_no_pack_root_graph_fires_error`-adjacent
    coverage: one case still needs a ``*.graph.yaml`` fixture (paired with
    ``validate_pack(pack_dir, check_drg_root=False)``) so the
    ``_DRG_GRAPH_GLOB`` path of ``_collect_fragment_edge_intent`` stays
    covered (#5346/#5353 T003). The runtime authoring shape is
    ``drg/fragment.yaml`` — see :func:`_write_fragment_intent`.
    """
    drg = pack_dir / "drg"
    drg.mkdir(parents=True, exist_ok=True)
    path = drg / "intent.graph.yaml"
    path.write_text(
        textwrap.dedent(
            f"""\
            schema_version: '1.0'
            generated_at: STATIC
            generated_by: test
            nodes: []
            edges:
              - source: tactic:{artifact_id}
                target: tactic:{artifact_id}
                relation: {relation}
            """
        ),
        encoding="utf-8",
    )
    return path


def _write_fragment_intent(
    pack_dir: Path,
    *,
    artifact_id: str,
    relation: str,
    source: str | None = None,
    target: str | None = None,
    declare_node: bool = False,
) -> Path:
    """Write a ``drg/fragment.yaml`` augmentation edge.

    This is the org-fragment shape the runtime actually reads (via
    ``charter.offering.drg.org_pack_loader.load_org_pack``), unlike
    ``drg/*.graph.yaml`` (:func:`_write_drg_intent`), which is a hard error
    since #3387 (``drg_root_graph_missing``). Pins #5494 (#5346/#5353 T003).

    ``source`` / ``target`` default to the fully-qualified ``tactic:<id>``
    spelling; pass a bare id to exercise the bare-endpoint forms the runtime
    resolver (``charter.offering.drg.merge._resolve_edge_endpoint``) accepts.
    ``declare_node`` emits a ``nodes:`` entry for *artifact_id* (kind
    ``tactics``) so a bare endpoint binds fragment-locally (rule 1).
    """
    drg = pack_dir / "drg"
    drg.mkdir(parents=True, exist_ok=True)
    path = drg / "fragment.yaml"
    edge_source = source if source is not None else f"tactic:{artifact_id}"
    edge_target = target if target is not None else f"tactic:{artifact_id}"
    nodes_block = (
        f"nodes:\n  - id: {artifact_id}\n    kind: tactics\n    title: Org variant\n"
        if declare_node
        else "nodes: []\n"
    )
    path.write_text(
        nodes_block
        + textwrap.dedent(
            f"""\
            edges:
              - source: {edge_source}
                target: {edge_target}
                relation: {relation}
            """
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
class TestIntentAwareCollision:
    """WP06 precedence table — `enhances` / `overrides` advisory + error logic.

    Tests exercise against the live shipped doctrine on disk (the worktree's
    ``packs/built-in/tactics`` tree). The shared fixture
    :data:`_BUILT_IN_TACTIC_ID` points at a known built-in. Packs always
    ship, so the ``_built_in_fixture_tactic_present`` autouse fixture asserts
    the precondition loudly instead of skipping when it cannot be met.
    """

    @pytest.fixture(autouse=True)
    def _built_in_fixture_tactic_present(self) -> None:
        _assert_built_in_fixture_tactic_present()

    def test_enhances_suppresses_collision_advisory(self, tmp_path: Path) -> None:
        """Case 4: declared `enhances` against a valid built-in -> no advisory.

        Regression coverage for #5494: the declaration lives in
        ``drg/fragment.yaml``, the shape the runtime reads.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        _write_fragment_intent(
            tmp_path,
            artifact_id=_BUILT_IN_TACTIC_ID,
            relation="enhances",
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        collision_advisories = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        assert collision_advisories == [], (
            "Declared `enhances` must suppress same_id_collision advisory."
        )

    def test_overrides_suppresses_collision_advisory(self, tmp_path: Path) -> None:
        """Case 4: declared `overrides` against a valid built-in -> no advisory.

        Regression coverage for #5494: the declaration lives in
        ``drg/fragment.yaml``, the shape the runtime reads.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        _write_fragment_intent(
            tmp_path,
            artifact_id=_BUILT_IN_TACTIC_ID,
            relation="overrides",
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        collision_advisories = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        assert collision_advisories == [], (
            "Declared `overrides` must suppress same_id_collision advisory."
        )

    def test_same_id_collision_uses_reworded_wording(self, tmp_path: Path) -> None:
        """Case 5: same-ID collision, no declaration -> reworded advisory.

        Message MUST mention `field-merge` and recommend BOTH
        `enhances: <id>` and `overrides: <id>`.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)

        result = validate_pack(tmp_path)

        matched = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        assert matched, (
            "Same-ID collision without declared intent MUST produce an "
            f"advisory. Saw advisories: {result.advisories}"
        )
        msg = matched[0].message
        assert "field-merge" in msg, msg
        assert f"enhances: {_BUILT_IN_TACTIC_ID}" in msg, msg
        assert f"overrides: {_BUILT_IN_TACTIC_ID}" in msg, msg

    def test_intent_conflict_when_both_fields_set(self, tmp_path: Path) -> None:
        """Case 1: both `overrides` and `enhances` declared -> `intent_conflict` ERROR."""
        _write_tactic(
            tmp_path,
            artifact_id="rogue-tactic",
            overrides="foo",
            enhances="bar",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        conflict_errors = [
            e for e in result.errors if e.category == "intent_conflict"
        ]
        assert conflict_errors, (
            f"Both-fields-set MUST emit `intent_conflict`. Errors: {result.errors}"
        )
        assert conflict_errors[0].artifact_id == "rogue-tactic"
        assert "mutually exclusive" in conflict_errors[0].message

    def test_enhances_unknown_target_errors(self, tmp_path: Path) -> None:
        """Case 3: `enhances` references unknown built-in -> `unknown_target` ERROR."""
        _write_tactic(
            tmp_path,
            artifact_id="org-only-tactic",
            enhances="totally-bogus-id",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        unknown_errors = [
            e for e in result.errors if e.category == "unknown_target"
        ]
        assert unknown_errors, (
            f"Unknown `enhances` target MUST emit `unknown_target`. "
            f"Errors: {result.errors}"
        )
        assert "totally-bogus-id" in unknown_errors[0].message
        assert "enhances" in unknown_errors[0].message

    def test_overrides_unknown_target_errors(self, tmp_path: Path) -> None:
        """Case 2: `overrides` references unknown built-in -> `unknown_target` ERROR."""
        _write_tactic(
            tmp_path,
            artifact_id="org-only-tactic",
            overrides="totally-bogus-id",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        unknown_errors = [
            e for e in result.errors if e.category == "unknown_target"
        ]
        assert unknown_errors, (
            f"Unknown `overrides` target MUST emit `unknown_target`. "
            f"Errors: {result.errors}"
        )
        assert "totally-bogus-id" in unknown_errors[0].message
        assert "overrides" in unknown_errors[0].message

    def test_json_output_includes_new_categories(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """T038: `category` field surfaces in JSON output for the new error kinds."""
        _write_tactic(
            tmp_path,
            artifact_id="rogue-tactic",
            overrides="a",
            enhances="b",
        )

        result = validate_pack(tmp_path)
        render_validation_result(result, json_output=True)
        captured = capsys.readouterr().out
        import json as _json

        payload = _json.loads(captured.strip())
        assert payload["ok"] is False
        categories = {e.get("category") for e in payload["errors"]}
        assert "intent_conflict" in categories, payload

    @pytest.mark.parametrize(
        ("relation", "expect_collision_absent"),
        [
            ("enhances", True),
            ("overrides", True),
            (None, False),
        ],
    )
    def test_fragment_yaml_augmentation_intent_suppresses_same_id_collision(
        self,
        tmp_path: Path,
        relation: str | None,
        expect_collision_absent: bool,
    ) -> None:
        """Regression test for #5494 (FR-005).

        `drg/fragment.yaml` augmentation intent — the org-fragment shape the
        runtime actually reads via ``load_org_pack`` — must suppress the
        `same_id_collision` advisory exactly like `drg/*.graph.yaml` intent
        does. Before the fix, `_collect_fragment_edge_intent` only read
        `drg/*.graph.yaml` (a shape that is a hard `drg_root_graph_missing`
        error since #3387), so no DRG shape validated clean with declared
        intent.

        The `relation=None` arm (no `drg/fragment.yaml` at all) is a
        positive control: it asserts the advisory IS present, proving the
        absence assertion in the other two arms is not vacuous.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        if relation is not None:
            _write_fragment_intent(
                tmp_path, artifact_id=_BUILT_IN_TACTIC_ID, relation=relation
            )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        drg_root_missing = [
            e for e in result.errors if e.category == "drg_root_graph_missing"
        ]
        assert drg_root_missing == [], drg_root_missing
        collision_advisories = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        if expect_collision_absent:
            assert collision_advisories == [], (
                f"drg/fragment.yaml {relation!r} intent must suppress "
                f"same_id_collision. Saw: {collision_advisories}"
            )
        else:
            assert collision_advisories, (
                "With no drg/fragment.yaml declared, same_id_collision MUST "
                "still fire (positive control, proves the absence assertion "
                "above is not vacuous)."
            )

    def test_graph_yaml_augmentation_intent_still_covered(
        self, tmp_path: Path
    ) -> None:
        """One `drg/*.graph.yaml`-shaped case stays covered (T003 step 5).

        ``_collect_fragment_edge_intent``'s original ``_DRG_GRAPH_GLOB`` path
        must keep working alongside the new ``drg/fragment.yaml`` path added
        for #5494. Uses ``check_drg_root=False`` because a bare
        ``drg/*.graph.yaml`` pack (no pack-root graph) is otherwise a hard
        ``drg_root_graph_missing`` error since #3387 — orthogonal to this
        assertion.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        _write_drg_intent(
            tmp_path, artifact_id=_BUILT_IN_TACTIC_ID, relation="enhances"
        )

        result = validate_pack(tmp_path, check_drg_root=False)

        assert result.ok is True, result.errors
        collision_advisories = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        assert collision_advisories == [], collision_advisories

    @pytest.mark.parametrize("relation", ["enhances", "overrides"])
    @pytest.mark.parametrize(
        ("source", "target", "declare_node"),
        [
            pytest.param(
                _BUILT_IN_TACTIC_ID, _BUILT_IN_TACTIC_ID, True, id="bare-both-declared"
            ),
            pytest.param(
                _BUILT_IN_TACTIC_ID,
                f"tactic:{_BUILT_IN_TACTIC_ID}",
                True,
                id="bare-source-declared",
            ),
            pytest.param(
                f"tactic:{_BUILT_IN_TACTIC_ID}",
                _BUILT_IN_TACTIC_ID,
                False,
                id="bare-target-builtin",
            ),
        ],
    )
    def test_fragment_yaml_bare_id_endpoints_suppress_same_id_collision(
        self,
        tmp_path: Path,
        relation: str,
        source: str,
        target: str,
        declare_node: bool,
    ) -> None:
        """Bare-id ``drg/fragment.yaml`` endpoints carry intent too (#5494 residual).

        The runtime resolver (``charter.offering.drg.merge._resolve_edge_endpoint``)
        binds a bare endpoint to a fragment-local node (rule 1) or to a
        unique built-in (rule 3), so these spellings are valid declared
        intent and must suppress ``same_id_collision`` exactly like the
        fully-qualified form pinned by
        :meth:`test_fragment_yaml_augmentation_intent_suppresses_same_id_collision`.
        The positive control there (no fragment -> advisory fires) keeps the
        absence assertion here non-vacuous.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        _write_fragment_intent(
            tmp_path,
            artifact_id=_BUILT_IN_TACTIC_ID,
            relation=relation,
            source=source,
            target=target,
            declare_node=declare_node,
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        collision_advisories = [
            a
            for a in result.advisories
            if a.artifact_id == _BUILT_IN_TACTIC_ID
            and a.category == "same_id_collision"
        ]
        assert collision_advisories == [], (
            f"bare-id drg/fragment.yaml {relation!r} intent "
            f"({source!r} -> {target!r}) must suppress same_id_collision. "
            f"Saw: {collision_advisories}"
        )

    @pytest.mark.parametrize("relation", ["enhances", "overrides"])
    def test_fragment_yaml_bare_unknown_target_is_unknown_target(
        self, tmp_path: Path, relation: str
    ) -> None:
        """Negative control: a bare typo'd target is resolved, not dropped.

        A bare target takes the source's kind, so ``bogus-id`` reaches the
        existing ``unknown_target`` error — the validator analogue of the
        runtime's ``unresolved_edge_endpoint``. Before the fix the edge was
        silently dropped and the pack validated ``ok=True``.
        """
        _write_tactic(tmp_path, artifact_id=_BUILT_IN_TACTIC_ID)
        _write_fragment_intent(
            tmp_path,
            artifact_id=_BUILT_IN_TACTIC_ID,
            relation=relation,
            target="bogus-id",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False, result.advisories
        unknown_errors = [e for e in result.errors if e.category == "unknown_target"]
        assert unknown_errors, (
            f"bare typo'd {relation!r} target MUST emit unknown_target. "
            f"Errors: {result.errors}"
        )
        assert "bogus-id" in unknown_errors[0].message


class TestRenderValidationResult:
    def test_json_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_directive(tmp_path, artifact_id="ACME-300")
        result = validate_pack(tmp_path)
        render_validation_result(result, json_output=True)
        captured = capsys.readouterr().out
        # The first non-empty line must be JSON.
        import json as _json

        payload = _json.loads(captured.strip())
        assert payload["ok"] is True

    def test_human_output_lists_errors_and_summary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_directive(
            tmp_path, artifact_id="ACME-400", drop_title=True
        )
        result = validate_pack(tmp_path)
        render_validation_result(result, json_output=False)
        captured = capsys.readouterr().out
        assert "Error" in captured
        assert "Pack validation:" in captured


# ---------------------------------------------------------------------------
# WP04: ASSET sidecar manifest validation (T014-T018)
# ---------------------------------------------------------------------------


class TestAssetManifestValidation:
    """ASSET (``*.asset.yaml``) sidecar manifest + safety contract.

    The referenced blob is never scanned; only the sidecar manifest is
    schema-validated (T014), plus a separate containment (T016) and mime
    (T017) safety pass. Global id-uniqueness across packs is explicitly
    OUT of scope here (WP03's merge scan).
    """

    def test_valid_manifest_passes(self, tmp_path: Path) -> None:
        """A well-formed, contained, mime-consistent manifest is clean."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-brand-logo-png",
            mime="image/png",
            path_value="branding/acme-logo.png",
            title="Acme brand logo (PNG)",
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        assert result.errors == []

    def test_missing_id_fails_schema(self, tmp_path: Path) -> None:
        _write_asset_manifest(
            tmp_path,
            artifact_id=None,
            drop_id=True,
            filename="acme-logo-no-id.asset.yaml",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        assert any(
            issue.artifact_type == "assets" and issue.category == "schema_invalid"
            for issue in result.errors
        ), result.errors

    def test_blank_id_fails_schema(self, tmp_path: Path) -> None:
        _write_asset_manifest(
            tmp_path,
            artifact_id="",
            filename="acme-logo-blank-id.asset.yaml",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        assert any(
            issue.artifact_type == "assets" and issue.category == "schema_invalid"
            for issue in result.errors
        ), result.errors

    def test_path_escape_via_dotdot_rejected(self, tmp_path: Path) -> None:
        """T016: an escaping ``path`` is rejected as ``asset_path_escape``."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-logo-escape",
            mime="image/png",
            path_value="../../../etc/passwd",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        escape_errors = [
            e for e in result.errors if e.category == "asset_path_escape"
        ]
        assert escape_errors, result.errors
        assert escape_errors[0].artifact_id == "acme-logo-escape"

    def test_absolute_path_rejected(self, tmp_path: Path) -> None:
        """T016: an absolute ``path`` is also rejected as ``asset_path_escape``."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-logo-absolute",
            mime="image/png",
            path_value="/etc/passwd",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        escape_errors = [
            e for e in result.errors if e.category == "asset_path_escape"
        ]
        assert escape_errors, result.errors
        assert escape_errors[0].artifact_id == "acme-logo-absolute"

    def test_malformed_mime_rejected(self, tmp_path: Path) -> None:
        """T017: ``mime`` without a ``type/subtype`` shape is rejected."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-logo-badmime",
            mime="notamimetype",
            path_value="branding/acme-logo.png",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        mime_errors = [e for e in result.errors if e.category == "asset_mime_invalid"]
        assert mime_errors, result.errors
        assert mime_errors[0].artifact_id == "acme-logo-badmime"

    def test_mime_extension_mismatch_rejected(self, tmp_path: Path) -> None:
        """T017: declared ``mime`` disagreeing with the path extension is rejected."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-logo-mismatch",
            mime="image/png",
            path_value="branding/acme-logo.txt",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        mime_errors = [e for e in result.errors if e.category == "asset_mime_invalid"]
        assert mime_errors, result.errors
        assert mime_errors[0].artifact_id == "acme-logo-mismatch"

    def test_nested_asset_manifest_violation_is_caught(self, tmp_path: Path) -> None:
        """FR-003 AC-1: a schema-violating manifest nested one level below
        ``assets/`` (``assets/<pack>/x.asset.yaml`` — the ADR-mandated org-pack
        layout ``AssetRepository`` already recurses into) is caught by
        ``pack validate``, not silently skipped. Before FR-003, ``_scan_files``
        only recurses for ``styleguides``, so this manifest was never scanned
        and this assertion failed.
        """
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-logo-nested-badmime",
            mime="notamimetype",
            path_value="branding/acme-logo.png",
            subdir="acme-pack",
        )

        result = validate_pack(tmp_path)

        assert result.ok is False
        mime_errors = [e for e in result.errors if e.category == "asset_mime_invalid"]
        assert mime_errors, result.errors
        assert mime_errors[0].artifact_id == "acme-logo-nested-badmime"
        assert "acme-pack" in mime_errors[0].file

    def test_nested_asset_manifest_valid_passes(self, tmp_path: Path) -> None:
        """FR-003 AC-2: a valid nested manifest passes with no false positive —
        it participates in the existing containment/mime checks exactly like a
        top-level asset would."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-brand-logo-nested-png",
            mime="image/png",
            path_value="branding/acme-logo.png",
            subdir="acme-pack",
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        assert result.errors == []

    def test_no_assets_directory_is_a_noop(self, tmp_path: Path) -> None:
        """FR-003 AC-4: an absent ``assets/`` directory produces no error and no
        behavior change. ``validate_pack``'s registry loop guard
        (``if not type_dir.is_dir(): continue``) predates FR-003 and is left
        untouched by it — this proves the guard path actually executes for the
        absent-directory case (not merely that nothing crashes) by asserting no
        ``assets``-typed issue is ever produced when ``assets/`` never existed.
        """
        _write_directive(tmp_path, artifact_id="ACME-001")
        assert not (tmp_path / "assets").exists()

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        assert not any(
            issue.artifact_type == "assets"
            for issue in (*result.errors, *result.advisories)
        ), (result.errors, result.advisories)

    def test_multiple_assets_independent(self, tmp_path: Path) -> None:
        """Multiple manifests in one pack are each validated independently."""
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-brand-logo-png",
            mime="image/png",
            path_value="branding/acme-logo.png",
        )
        _write_asset_manifest(
            tmp_path,
            artifact_id="acme-brand-font-woff2",
            mime="font/woff2",
            path_value="branding/acme-brand.woff2",
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors


class TestProfileSkippedDiagnostics:
    """FR-002: ``pack validate`` surfaces ``AgentProfileRepository``'s
    post-merge profile-skip diagnostics inline (``skipped_profiles()``),
    not only via the separate, undocumented ``spec-kitty doctor doctrine
    --json`` command.

    This is additive wiring (AC-4), not a new validation engine: the checks
    here exercise the REAL, shipped built-in ``analyst-annie`` profile
    (``packs/built-in/agent_profiles/analyst-annie.agent.yaml``) as the
    merge target, per this WP's Reviewer Guidance — no fake built-in
    directory is fabricated.
    """

    _ANALYST_ANNIE_ROLE_CONFLICT_YAML = textwrap.dedent(
        """\
        profile-id: analyst-annie
        role: implementer
        name: Override
        purpose: test purpose
        specialization:
          primary-focus: test focus
        """
    )

    def test_post_merge_skip_surfaces_as_profile_skipped_issue(
        self, tmp_path: Path
    ) -> None:
        """AC-1: a profile that passes ``AgentProfile.model_validate`` in
        isolation (proven standalone-valid by
        ``tests/doctrine/test_agent_profile_model_field.py``'s
        ``TestDeprecatedScalarRoleStandaloneValid``, T008) but is recorded
        via ``AgentProfileRepository``'s ``_record_skip`` during merge-time
        load (the deprecated scalar ``role:`` colliding with the real
        built-in ``analyst-annie``'s already-resolved ``roles:``) causes
        ``pack validate`` to include a ``profile_skipped`` ``ValidationIssue``
        in ``result.errors``.

        Before this WP, ``pack_validator.py`` never calls
        ``AgentProfileRepository``/``skipped_profiles()`` at all, so this
        assertion fails — the only surface for this diagnostic today is the
        separate ``spec-kitty doctor doctrine --json`` command.
        """
        profile_path = _write_agent_profile_yaml(
            tmp_path,
            filename="analyst-annie.agent.yaml",
            content=self._ANALYST_ANNIE_ROLE_CONFLICT_YAML,
        )

        result = validate_pack(tmp_path)

        skipped_issues = [
            issue for issue in result.errors if issue.category == "profile_skipped"
        ]
        assert skipped_issues, result.errors
        issue = skipped_issues[0]
        assert issue.severity == "error"
        assert issue.artifact_type == "agent_profiles"
        assert issue.artifact_id == "analyst-annie"
        assert issue.file == str(profile_path)
        assert "role" in issue.message and "roles" in issue.message

    def test_helper_calls_repository_skipped_profiles_directly(
        self, tmp_path: Path
    ) -> None:
        """AC-4: the helper reuses ``AgentProfileRepository.skipped_profiles()``
        directly rather than hand-rolling a second skip-detection heuristic.

        Patches the source location the helper's lazy, function-local import
        binds to (``charter.offering.agent_profiles.repository.AgentProfileRepository``
        — matching this file's existing precedent of lazy in-function
        imports, and what ``scripts/check_patch_targets.py`` expects). This
        assertion is non-vacuous: it fails if the call is removed or replaced
        with an inline reimplementation, since only an actual invocation of
        the mocked method satisfies ``assert_called_once``.
        """
        agent_profiles_dir = tmp_path / "agent_profiles"
        agent_profiles_dir.mkdir()

        with patch(
            "charter.offering.agent_profiles.repository.AgentProfileRepository.skipped_profiles"
        ) as mock_skipped_profiles:
            mock_skipped_profiles.return_value = []
            issues = _check_profile_skipped_diagnostics(tmp_path, set())

        mock_skipped_profiles.assert_called_once_with()
        assert issues == []

    def test_schema_invalid_profile_is_not_double_reported(
        self, tmp_path: Path
    ) -> None:
        """AC-2: a profile file with an undeclared key (the already-fixed
        acute case — ``AgentProfile.model_config`` has ``extra="forbid"``)
        is caught by the existing generic per-file schema scan as
        ``schema_invalid``. ``AgentProfileRepository``'s own load of this
        same file would *also* fail schema validation (identical model,
        identical ``extra="forbid"`` constraint) and therefore also appear
        in ``skipped_profiles()`` — proving the ``already_flagged_files``
        dedup actually filters the redundant report rather than merely
        happening not to fire.
        """
        profile_path = _write_agent_profile_yaml(
            tmp_path,
            filename="some-profile.agent.yaml",
            content=textwrap.dedent(
                """\
                profile-id: some-profile
                name: Some Profile
                purpose: test purpose
                specialization:
                  primary-focus: test focus
                roles: [implementer]
                totally-unknown-field: true
                """
            ),
        )

        result = validate_pack(tmp_path)

        file_issues = [
            issue for issue in result.errors if issue.file == str(profile_path)
        ]
        assert len(file_issues) == 1, file_issues
        assert file_issues[0].category == "schema_invalid"
        assert not any(
            issue.category == "profile_skipped" for issue in file_issues
        )

    def test_clean_pack_has_no_profile_skipped_issue(self, tmp_path: Path) -> None:
        """AC-3: a pack with no profile problems produces no ``profile_skipped``
        issue and an unaffected ``ok`` result — no false positive on a
        currently-passing pack. Uses a fresh ``profile-id`` that does not
        collide with any built-in profile, so no merge is even attempted.
        """
        _write_agent_profile_yaml(
            tmp_path,
            filename="acme-custom-implementer.agent.yaml",
            content=textwrap.dedent(
                """\
                profile-id: acme-custom-implementer
                name: Acme Custom Implementer
                purpose: test purpose
                specialization:
                  primary-focus: test focus
                roles: [implementer]
                """
            ),
        )

        result = validate_pack(tmp_path)

        assert result.ok is True, result.errors
        assert not any(
            issue.category == "profile_skipped"
            for issue in (*result.errors, *result.advisories)
        )

    def test_absent_agent_profiles_directory_is_safe_and_exercised(
        self, tmp_path: Path
    ) -> None:
        """AC-5: a pack whose ``agent_profiles/`` directory is entirely
        absent does not raise, produces no ``profile_skipped`` issue, and —
        per the spec's Edge Cases bullet 2 — this is proven by actually
        exercising the check path (a direct call to the helper returning an
        empty list), not merely by the absence of a crash from
        ``validate_pack``.
        """
        (tmp_path / "directives").mkdir()
        assert not (tmp_path / "agent_profiles").exists()

        result = validate_pack(tmp_path)

        assert not any(
            issue.category == "profile_skipped"
            for issue in (*result.errors, *result.advisories)
        )

        # Direct-call assertion: prove the check path actually executed
        # against the absent-directory case, not swallowed by a broad
        # try/except that would make the assertion above vacuous.
        assert _check_profile_skipped_diagnostics(tmp_path, set()) == []

    def test_repository_construction_failure_is_guarded(
        self, tmp_path: Path
    ) -> None:
        """PR-M-001: a raise while resolving ``AgentProfileRepository``'s
        built-in content directory must not propagate as an uncaught
        traceback. The raise path is real (not hypothetical): ``__init__``
        resolves ``built_in_dir()`` through the fail-closed seam pinned by
        ``tests/doctrine/test_pack_root_resolver.py`` — a stripped
        environment raises ``PackRootNotFound`` there, exactly as the
        sibling ``_load_built_in_ids_per_kind`` guard anticipates for the
        same seam.

        Patches ``built_in_dir`` at the binding the repository's own
        constructor calls (``charter.offering.agent_profiles.repository.built_in_dir``
        — the module ``AgentProfileRepository._default_built_in_dir``
        actually imported it into), so this fires regardless of which
        construction path calls into the repository (PR-M-002 routes that
        construction through ``DoctrineService``, which does not change
        this seam).
        """
        from charter.offering.pack_paths import PackRootNotFound

        with patch(
            "charter.offering.agent_profiles.repository.built_in_dir",
            side_effect=PackRootNotFound("built-in"),
        ):
            issues = _check_profile_skipped_diagnostics(tmp_path, set())

        assert issues, "a resolution failure must surface as an issue, not vanish"
        assert issues[0].severity == "error"
        assert issues[0].category == "profile_skipped"
        assert issues[0].artifact_type == "agent_profiles"

    def test_validate_pack_survives_repository_construction_failure(
        self, tmp_path: Path
    ) -> None:
        """PR-M-001: the same raise must not crash ``validate_pack`` (and by
        extension the ``pack_validate`` / ``org_validate`` CLI entry
        points), which is the concrete failure the finding describes — a
        raw traceback instead of the promised ``{"ok": ...}`` JSON.
        """
        from charter.offering.pack_paths import PackRootNotFound

        with patch(
            "charter.offering.agent_profiles.repository.built_in_dir",
            side_effect=PackRootNotFound("built-in"),
        ):
            result = validate_pack(tmp_path)

        assert isinstance(result, ValidationResult)
        assert result.ok is False
        assert any(issue.category == "profile_skipped" for issue in result.errors)


class TestDrgRootGraphMissing:
    """FR-004: ``pack validate`` gains an additive check that fires when a
    pack's DRG content lives only under ``drg/*.graph.yaml`` fragments with
    no pack-root ``*.graph.yaml`` — the shape the runtime
    (``src/charter/activation/_drg_helpers.py:load_validated_graph``) never reads
    (see sibling mission #3384). Keyed off pack *content*, via the same
    exact ``*.graph.yaml`` glob ``_validate_drg`` already uses, so it is
    consistent by construction (AC-5).
    """

    _MINIMAL_FRAGMENT_YAML = textwrap.dedent(
        """\
        schema_version: "1.0"
        generated_at: STATIC
        generated_by: test
        nodes: []
        edges: []
        """
    )

    def test_drg_only_fragment_no_pack_root_graph_fires_error(
        self, tmp_path: Path
    ) -> None:
        """AC-1 + AC-4: a pack with ``drg/010-security.graph.yaml`` and no
        pack-root ``*.graph.yaml`` produces a ``drg_root_graph_missing``
        error (default ``check_drg_root=True``), and ``pack validate``'s
        CLI maps that to exit code 1.

        Before this WP, ``validate_pack`` has no ``check_drg_root``
        parameter and no ``drg_root_graph_missing`` category exists, so
        both assertions below fail.
        """
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-security.graph.yaml").write_text(
            self._MINIMAL_FRAGMENT_YAML, encoding="utf-8"
        )
        assert not sorted(tmp_path.glob("*.graph.yaml"))

        result = validate_pack(tmp_path)

        assert result.ok is False
        root_missing = [
            issue
            for issue in result.errors
            if issue.category == "drg_root_graph_missing"
        ]
        assert root_missing, result.errors
        issue = root_missing[0]
        assert issue.severity == "error"
        assert "_drg_helpers.py" in issue.message or "load_validated_graph" in issue.message

        # AC-4's exit-code half: exercise the same fixture through the CLI.
        from typer.testing import CliRunner

        from specify_cli.cli.commands.doctrine import app as doctrine_app

        cli_result = CliRunner().invoke(
            doctrine_app, ["pack", "validate", str(tmp_path)]
        )
        assert cli_result.exit_code == 1, cli_result.output

    def test_pack_root_graph_present_suppresses_diagnostic(
        self, tmp_path: Path
    ) -> None:
        """AC-2: a pack-root ``*.graph.yaml`` present (alongside ``drg/``
        fragments) produces no ``drg_root_graph_missing`` diagnostic.
        """
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-security.graph.yaml").write_text(
            self._MINIMAL_FRAGMENT_YAML, encoding="utf-8"
        )
        (tmp_path / "pack.graph.yaml").write_text(
            self._MINIMAL_FRAGMENT_YAML, encoding="utf-8"
        )

        result = validate_pack(tmp_path)

        assert not any(
            issue.category == "drg_root_graph_missing"
            for issue in (*result.errors, *result.advisories)
        )

    def test_neither_root_graph_nor_drg_dir_no_diagnostic(
        self, tmp_path: Path
    ) -> None:
        """AC-3: a pack with neither a pack-root graph nor a ``drg/``
        directory at all produces no diagnostic — this check is about a
        *mismatch*, not about requiring DRG content to exist.
        """
        assert not (tmp_path / "drg").exists()
        assert not sorted(tmp_path.glob("*.graph.yaml"))

        result = validate_pack(tmp_path)

        assert not any(
            issue.category == "drg_root_graph_missing"
            for issue in (*result.errors, *result.advisories)
        )

    def test_near_miss_pack_root_filename_does_not_satisfy_check(
        self, tmp_path: Path
    ) -> None:
        """AC-5: a pack-root file named e.g. ``notes.graph.yaml.bak`` (a
        near-miss that does not match ``*.graph.yaml``) does not satisfy
        the pack-root requirement — the AC-1 diagnostic still fires. This
        is correct by construction (``Path.glob("*.graph.yaml")`` does not
        match a ``.bak``-suffixed name); this test is a regression guard
        against a future, accidental widening of the glob.
        """
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-security.graph.yaml").write_text(
            self._MINIMAL_FRAGMENT_YAML, encoding="utf-8"
        )
        (tmp_path / "notes.graph.yaml.bak").write_text(
            "not a real graph", encoding="utf-8"
        )

        result = validate_pack(tmp_path)

        root_missing = [
            issue
            for issue in result.errors
            if issue.category == "drg_root_graph_missing"
        ]
        assert root_missing, result.errors


# ---------------------------------------------------------------------------
# Pack-root sanction file (FR-014, #5767)
# ---------------------------------------------------------------------------

_SANCTION_FILE = "replaceable-builtins.yaml"
_BUILT_IN_TACTIC = "acceptance-test-first"
_BUILT_IN_DIRECTIVE = "DIRECTIVE_003"


def _write_override_fragment(pack_dir: Path, *nodes: tuple[str, str]) -> None:
    """Write a ``drg/fragment.yaml`` declaring ``(kind_plural, id)`` nodes."""
    drg = pack_dir / "drg"
    drg.mkdir(parents=True, exist_ok=True)
    body = "".join(
        f"  - id: {node_id}\n    kind: {kind}\n    title: Org variant\n"
        for kind, node_id in nodes
    )
    (drg / "fragment.yaml").write_text(f"nodes:\n{body}edges: []\n", encoding="utf-8")


def _write_sanction(pack_dir: Path, text: str) -> None:
    (pack_dir / _SANCTION_FILE).write_text(textwrap.dedent(text), encoding="utf-8")


def _sanction_issues(result: ValidationResult) -> tuple[list, list]:
    errors = [i for i in result.errors if i.category == "pack_sanction"]
    advisories = [i for i in result.advisories if i.category == "pack_sanction"]
    return errors, advisories


@pytest.mark.unit
class TestPackSanctionValidation:
    def test_valid_sanction_for_overridden_builtin_is_clean(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path, ("tactics", _BUILT_IN_TACTIC))
        _write_sanction(
            tmp_path,
            f"""\
            replaceable_builtins:
              - urn: tactic:{_BUILT_IN_TACTIC}
                reason: Ours is stricter.
            """,
        )

        result = validate_pack(tmp_path)

        assert result.ok, [i.message for i in result.errors]
        assert _sanction_issues(result) == ([], [])

    def test_valid_sanction_is_not_inert_when_the_built_in_graph_is_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A degraded env (built-in graph unloadable) must not flood every entry
        with the inert advisory: without the real built-in set we cannot tell an
        entry is inert, so the advisory is withheld rather than wrongly emitted."""
        from charter.offering.drg import loader

        def failing() -> object:
            raise loader.DRGLoadError("broken built-in graph")

        monkeypatch.setattr(loader, "load_built_in_graph", failing)
        _write_override_fragment(tmp_path, ("tactics", _BUILT_IN_TACTIC))
        _write_sanction(
            tmp_path,
            f"""\
            replaceable_builtins:
              - urn: tactic:{_BUILT_IN_TACTIC}
                reason: Ours is stricter.
            """,
        )

        errors, advisories = _sanction_issues(validate_pack(tmp_path))

        assert errors == []
        assert advisories == []

    def test_malformed_sanction_is_an_error_naming_the_file(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path, ("tactics", _BUILT_IN_TACTIC))
        _write_sanction(tmp_path, "replaceable_builtins: [unterminated\n")

        result = validate_pack(tmp_path)

        errors, _ = _sanction_issues(result)
        assert not result.ok
        assert len(errors) == 1
        assert _SANCTION_FILE in errors[0].message

    def test_consumer_only_revocation_key_is_an_error(self, tmp_path: Path) -> None:
        _write_sanction(
            tmp_path,
            """\
            revoked_pack_sanctions:
              - urn: tactic:x
            """,
        )

        errors, _ = _sanction_issues(validate_pack(tmp_path))

        assert len(errors) == 1

    def test_directive_without_reason_is_an_error(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path, ("directives", _BUILT_IN_DIRECTIVE))
        _write_sanction(
            tmp_path,
            f"""\
            replaceable_builtins:
              - urn: directive:{_BUILT_IN_DIRECTIVE}
                reason: ""
            """,
        )

        errors, advisories = _sanction_issues(validate_pack(tmp_path))

        assert len(errors) == 1
        assert f"directive:{_BUILT_IN_DIRECTIVE}" in errors[0].message
        assert advisories == []

    def test_non_directive_without_reason_is_accepted(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path, ("tactics", _BUILT_IN_TACTIC))
        _write_sanction(
            tmp_path,
            f"""\
            replaceable_builtins:
              - urn: tactic:{_BUILT_IN_TACTIC}
            """,
        )

        assert _sanction_issues(validate_pack(tmp_path)) == ([], [])

    def test_entry_the_pack_does_not_override_is_an_advisory_only(
        self, tmp_path: Path
    ) -> None:
        _write_override_fragment(tmp_path, ("tactics", _BUILT_IN_TACTIC))
        _write_sanction(
            tmp_path,
            """\
            replaceable_builtins:
              - urn: tactic:not-in-this-pack
                reason: Inert.
              - urn: tactic:acceptance-criteria-non-vacuity
                reason: Built-in, but this pack declares no node for it.
            """,
        )

        result = validate_pack(tmp_path)

        errors, advisories = _sanction_issues(result)
        assert result.ok
        assert errors == []
        assert len(advisories) == 2
        assert all(a.severity == "advisory" for a in advisories)

    def test_pack_own_non_builtin_node_entry_is_an_advisory(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path, ("tactics", "org-only-tactic"))
        _write_sanction(
            tmp_path,
            """\
            replaceable_builtins:
              - urn: tactic:org-only-tactic
                reason: Not a built-in.
            """,
        )

        errors, advisories = _sanction_issues(validate_pack(tmp_path))

        assert errors == []
        assert len(advisories) == 1

    def test_artifact_file_node_counts_as_pack_node(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path)
        _write_directive(tmp_path, artifact_id=_BUILT_IN_DIRECTIVE)
        _write_sanction(
            tmp_path,
            f"""\
            replaceable_builtins:
              - urn: directive:{_BUILT_IN_DIRECTIVE}
                reason: Replaced by file-backed artifact.
            """,
        )

        assert _sanction_issues(validate_pack(tmp_path)) == ([], [])

    def test_pack_without_sanction_file_is_unchanged(self, tmp_path: Path) -> None:
        _write_override_fragment(tmp_path, ("tactics", _BUILT_IN_TACTIC))

        result = validate_pack(tmp_path)

        assert _sanction_issues(result) == ([], [])


@pytest.mark.unit
class TestPackSanctionSymlinkPresence:
    """A symlinked sanction file counts as present, as the runtime parser sees it."""

    @pytest.fixture(autouse=True)
    def _require_symlinks(self, tmp_path: Path) -> None:
        probe = tmp_path / "probe-link"
        try:
            probe.symlink_to(tmp_path / "probe-target")
        except (OSError, NotImplementedError, AttributeError):
            pytest.skip("symlinks unsupported on this platform")
        probe.unlink()

    def test_dangling_symlink_is_a_pack_sanction_error(self, tmp_path: Path) -> None:
        pack = tmp_path / "mypack"
        pack.mkdir()
        (pack / _SANCTION_FILE).symlink_to(tmp_path / "nonexistent.yaml")

        errors, _ = _sanction_issues(validate_pack(pack))

        assert len(errors) == 1
        assert _SANCTION_FILE in errors[0].message

    def test_symlink_escaping_pack_root_is_a_pack_sanction_error(
        self, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside.yaml"
        outside.write_text("replaceable_builtins: []\n", encoding="utf-8")
        pack = tmp_path / "mypack"
        pack.mkdir()
        (pack / _SANCTION_FILE).symlink_to(outside)

        errors, _ = _sanction_issues(validate_pack(pack))

        assert len(errors) == 1
        assert _SANCTION_FILE in errors[0].message


def test_built_in_node_urns_is_empty_when_the_built_in_graph_cannot_load(monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.offering.drg import loader
    from specify_cli.doctrine.pack_validator import _built_in_node_urns

    def failing() -> object:
        raise loader.DRGLoadError("broken built-in graph")

    monkeypatch.setattr(loader, "load_built_in_graph", failing)
    assert _built_in_node_urns() == frozenset()
