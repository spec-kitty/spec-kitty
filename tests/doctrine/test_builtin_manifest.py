"""Built-in pack-manifest generator tests (WP01 / T004, T005).

Synthetic-fixture only (tmp_path) — the tests build a miniature pack tree, so
nothing here reads the shipped ``packs/built-in`` corpus. Covers:

* T004(a) SC-002 — every artifact-kind DRG node is enumerated as a constituent;
* T004(b) — the build/upgrade wiring (``regenerate-graph``) actually *fires* the
  generator (renata M1: enumeration alone does not prove invocation);
* T005(a) NFR-003 — twice-generating an unchanged pack is byte-identical and the
  ``manifest_hash`` is stable, independent of the ``generated_*`` provenance;
* T005(b) FR-009 — mutating one constituent's bytes changes its ``content_hash``
  *and* the ``manifest_hash`` (tamper is detected, not merely stable);
* the writer boundary — only ``pack-manifest.yaml`` is emitted, never
  ``pack.yaml`` and never a ``pack_version`` field.
"""

from __future__ import annotations

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.packs.builtin_manifest import (
    MANIFEST_FILENAME,
    build_builtin_manifest,
    builtin_manifest_is_fresh,
    enumerate_constituents,
    generate_builtin_manifest,
)
from charter.offering.packs.pack_manifest import load_pack_manifest

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture()
def pack_root(tmp_path):
    """A miniature built-in pack: directive + tactic (nested) + agent_profile."""
    root = tmp_path / "built-in"
    _write(root / "directives" / "001-alpha.directive.yaml", "id: DIRECTIVE_001\nlabel: Alpha\n")
    _write(root / "tactics" / "analysis" / "beta.tactic.yaml", "id: beta\nlabel: Beta\n")
    _write(root / "agent_profiles" / "pedro.agent.yaml", "profile-id: python-pedro\nname: Pedro\n")
    return root


class TestEnumeration:
    def test_enumerates_every_artifact_kind_node(self, pack_root) -> None:
        cs = enumerate_constituents(pack_root)
        got = {(c.kind, c.id) for c in cs}
        assert got == {
            (ArtifactKind.DIRECTIVE, "DIRECTIVE_001"),
            (ArtifactKind.TACTIC, "beta"),
            (ArtifactKind.AGENT_PROFILE, "python-pedro"),
        }

    def test_covers_100_percent_of_artifact_nodes(self, pack_root) -> None:
        # Model the DRG node set (including a mission_type + action node that
        # have no artifact file): every *artifact-kind* node must be enumerated,
        # and the non-artifact kinds must NOT appear (documented exclusion, not
        # a silent drop).
        graph_nodes = {
            ("directive", "DIRECTIVE_001"),
            ("tactic", "beta"),
            ("agent_profile", "python-pedro"),
            ("mission_type", "software-dev"),
            ("action", "software-dev/implement"),
        }
        artifact_kind_values = {k.value for k in ArtifactKind}
        artifact_nodes = {(k, i) for (k, i) in graph_nodes if k in artifact_kind_values}
        enumerated = {(c.kind.value, c.id) for c in enumerate_constituents(pack_root)}
        assert enumerated == artifact_nodes
        # mission_type / action are intentionally absent.
        assert not any(k in {"mission_type", "action"} for (k, _) in enumerated)

    def test_missing_id_field_fails_closed(self, pack_root) -> None:
        _write(pack_root / "directives" / "002-noid.directive.yaml", "label: no id here\n")
        with pytest.raises(ValueError, match="missing its 'id'"):
            enumerate_constituents(pack_root)

    def test_lf_normalized_content_hash_is_crlf_stable(self, tmp_path) -> None:
        lf = tmp_path / "lf"
        crlf = tmp_path / "crlf"
        _write(lf / "directives" / "001-a.directive.yaml", "id: DIRECTIVE_001\nlabel: A\n")
        (crlf / "directives").mkdir(parents=True)
        (crlf / "directives" / "001-a.directive.yaml").write_bytes(b"id: DIRECTIVE_001\r\nlabel: A\r\n")
        assert (
            enumerate_constituents(lf)[0].content_hash
            == enumerate_constituents(crlf)[0].content_hash
        )


class TestDeterminism:
    def test_twice_generate_byte_identical(self, pack_root) -> None:
        generate_builtin_manifest(pack_root)
        first = (pack_root / MANIFEST_FILENAME).read_bytes()
        generate_builtin_manifest(pack_root)
        second = (pack_root / MANIFEST_FILENAME).read_bytes()
        assert first == second

    def test_manifest_hash_excludes_generated_provenance(self, pack_root) -> None:
        # generated_at/by are excluded from BOTH the manifest_hash and the
        # (constituents) byte set — a re-run is byte-identical regardless.
        a = build_builtin_manifest(pack_root).model_copy(update={"generated_at": "t1", "generated_by": "x"})
        b = build_builtin_manifest(pack_root).model_copy(update={"generated_at": "t2", "generated_by": "y"})
        from charter.offering.packs.pack_manifest import compute_pack_manifest_hash

        assert compute_pack_manifest_hash(a) == compute_pack_manifest_hash(b)


class TestTamperEvidence:
    def test_mutating_a_constituent_changes_both_hashes(self, pack_root) -> None:
        before = build_builtin_manifest(pack_root)
        before_by_id = {c.id: c for c in before.constituents}
        # Mutate the directive's bytes.
        target = pack_root / "directives" / "001-alpha.directive.yaml"
        target.write_text("id: DIRECTIVE_001\nlabel: TAMPERED\n", encoding="utf-8")
        after = build_builtin_manifest(pack_root)
        after_by_id = {c.id: c for c in after.constituents}
        assert after_by_id["DIRECTIVE_001"].content_hash != before_by_id["DIRECTIVE_001"].content_hash
        assert after.manifest_hash != before.manifest_hash


class TestWriterBoundary:
    def test_emits_only_pack_manifest_never_pack_yaml_or_pack_version(self, pack_root) -> None:
        generate_builtin_manifest(pack_root)
        assert (pack_root / MANIFEST_FILENAME).is_file()
        assert not (pack_root / "pack.yaml").exists()
        text = (pack_root / MANIFEST_FILENAME).read_text(encoding="utf-8")
        assert "pack_version" not in text
        # And the model has no such field.
        loaded = load_pack_manifest(pack_root / MANIFEST_FILENAME)
        assert "pack_version" not in loaded.model_dump()

    def test_freshness_gate_detects_drift(self, pack_root) -> None:
        generate_builtin_manifest(pack_root)
        assert builtin_manifest_is_fresh(pack_root) is True
        (pack_root / "tactics" / "analysis" / "gamma.tactic.yaml").write_text(
            "id: gamma\n", encoding="utf-8"
        )
        assert builtin_manifest_is_fresh(pack_root) is False


class TestWiringFires:
    """T004(b): the regenerate-graph command actually invokes the generator."""

    def test_regenerate_graph_materializes_the_manifest(self, pack_root, monkeypatch) -> None:
        import typer

        from charter.offering.drg.migration import hand_authored_overlay
        from specify_cli.cli.commands import doctrine as doctrine_cmd

        # Stub the unrelated DRG graph write; keep the real manifest generator.
        monkeypatch.setattr(
            hand_authored_overlay,
            "write_reference_graph_with_overlay",
            lambda root, out: out.write_text("nodes: []\n", encoding="utf-8"),
        )
        monkeypatch.setattr(doctrine_cmd, "_doctrine_root", lambda: pack_root)

        assert not (pack_root / MANIFEST_FILENAME).exists()
        with pytest.raises(typer.Exit) as exc:
            doctrine_cmd.regenerate_graph(check=False, json_output=True)
        assert exc.value.exit_code == 0
        # The wiring fired: the generator ran as part of the command.
        assert (pack_root / MANIFEST_FILENAME).is_file()
        assert build_builtin_manifest(pack_root).constituents
