"""Direct-written doctrine registration through the charter domain seam."""

from pathlib import Path
from textwrap import dedent

import pytest

from charter.activation.synthesizer.manifest import load_yaml, verify
from charter.offering.artifact_kinds import ArtifactKind, PROJECT_KIND_DIRS
from specify_cli.cli.commands.doctrine import _STUB_TEMPLATES

pytestmark = pytest.mark.unit


def author_guidance(root: Path) -> dict[str, Path]:
    paths = {}
    for token, identifier in {
        "procedure": "incident-runbook",
        "agent_profile": "ops-responder",
        "directive": "CHANGE_FREEZE",
        "tactic": "verify-rollback",
        "styleguide": "incident-notes",
    }.items():
        kind = ArtifactKind(token)
        directory = root / ".kittify/doctrine" / PROJECT_KIND_DIRS[kind]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / kind.glob_pattern.replace("*", identifier)
        content = _STUB_TEMPLATES[kind].format(artifact_id=identifier).replace("TODO", "Operational")
        if token == "agent_profile":
            content += (
                "collaboration:\n  operating-procedures: [incident-runbook]\n"
                "directive-references:\n  - code: CHANGE_FREEZE\n    name: Freeze\n    rationale: Safety\n"
                "tactic-references:\n  - id: verify-rollback\n    rationale: Safety\n"
                "styleguide-references:\n  - id: incident-notes\n    rationale: Clarity\n"
            )
        path.write_text(content)
        paths[token] = path
    return paths


def test_direct_written_guidance_registers_five_artifacts_without_synthesis(tmp_path):
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    before = {key: path.read_bytes() for key, path in paths.items()}
    plan = plan_project_registration(tmp_path)
    assert not (tmp_path / ".kittify/doctrine/graph.yaml").exists()
    assert sorted((a.node.kind.value, a.path) for a in plan.artifacts) == sorted(paths.items())
    assert {e.target for e in plan.graph.edges if e.source == "agent_profile:ops-responder"} == {
        "procedure:incident-runbook",
        "directive:CHANGE_FREEZE",
        "tactic:verify-rollback",
        "styleguide:incident-notes",
    }
    commit_project_registration(plan)
    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    assert sorted((a.kind, tmp_path / a.path) for a in manifest.artifacts) == sorted(paths.items())
    assert {key: path.read_bytes() for key, path in paths.items()} == before
    snapshot = {p: p.read_bytes() for p in (tmp_path / ".kittify").rglob("*.yaml")}
    commit_project_registration(plan_project_registration(tmp_path))
    assert {p: p.read_bytes() for p in snapshot} == snapshot


def test_unresolved_profile_reference_is_reported_without_phantom_node(tmp_path):
    from charter.activation.project_registration import plan_project_registration

    paths = author_guidance(tmp_path)
    paths["procedure"].unlink()
    plan = plan_project_registration(tmp_path)
    assert any("procedure:incident-runbook" in warning for warning in plan.warnings)
    assert plan.graph.get_node("procedure:incident-runbook") is None
    assert all(e.target != "procedure:incident-runbook" for e in plan.graph.edges)


def test_invalid_artifact_preflight_does_not_write_registration(tmp_path):
    from charter.activation.project_registration import plan_project_registration

    paths = author_guidance(tmp_path)
    paths["procedure"].write_text("id: incident-runbook\n")
    with pytest.raises(ValueError, match="incident-runbook"):
        plan_project_registration(tmp_path)
    assert not (tmp_path / ".kittify/charter/synthesis-manifest.yaml").exists()


def test_synthesis_reemits_all_registered_nodes_and_profile_edges(tmp_path):
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.project_drg import emit_project_layer
    from charter.offering.drg.loader import load_built_in_graph
    from charter.activation.synthesizer.reconcile import merge_project_overlay

    author_guidance(tmp_path)
    plan = plan_project_registration(tmp_path)
    commit_project_registration(plan)
    overlay = emit_project_layer([], "test", load_built_in_graph(), project_root=tmp_path)
    assert {node.urn for node in overlay.nodes} == {artifact.node.urn for artifact in plan.artifacts}
    assert sorted((e.target, e.relation.value) for e in overlay.edges) == [
        ("directive:CHANGE_FREEZE", "requires"),
        ("procedure:incident-runbook", "requires"),
        ("styleguide:incident-notes", "suggests"),
        ("tactic:verify-rollback", "requires"),
    ]
    merged = merge_project_overlay(existing_overlay=overlay, updated_overlay=overlay)
    assert merged.edges == overlay.edges


def test_editing_references_removes_previous_projected_edges(tmp_path):
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    profile = paths["agent_profile"]
    profile.write_text(profile.read_text().replace("operating-procedures: [incident-runbook]", "operating-procedures: []"))
    plan = plan_project_registration(tmp_path)
    assert all(e.target != "procedure:incident-runbook" for e in plan.graph.edges if e.source == "agent_profile:ops-responder")
    commit_project_registration(plan)
    verify(load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml"), tmp_path)


def test_duplicate_identity_fails_before_bookkeeping_mutation(tmp_path):
    from charter.activation.project_registration import plan_project_registration

    paths = author_guidance(tmp_path)
    duplicate = paths["procedure"].with_name("other.procedure.yaml")
    duplicate.write_bytes(paths["procedure"].read_bytes())
    with pytest.raises(ValueError, match="Duplicate project artifact procedure:incident-runbook"):
        plan_project_registration(tmp_path)
    assert not (tmp_path / ".kittify/charter").exists()


def test_existing_manifest_slug_is_reconciled_against_slug_for(tmp_path):
    """A hand-edited, non-canonical manifest ``slug`` is reconciled, not kept (T012/#4834).

    Identity is still tracked by URN (via the provenance sidecar, unaffected by
    this manual manifest edit), so the entry is correctly matched to its
    artifact across the replan -- but the *slug* the manifest records for that
    identity must always be ``slug_for(kind, id)``, never a legacy or
    hand-edited value perpetuated verbatim (the pre-fix behavior this test
    used to pin). The provenance sidecar path is unaffected here because the
    reconciled slug equals the artifact's original (already-canonical) slug.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.manifest import dump_yaml, finalize_manifest
    from charter.activation.synthesizer.path_guard import PathGuard

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    manifest_path = tmp_path / ".kittify/charter/synthesis-manifest.yaml"
    manifest = load_yaml(manifest_path)
    original = manifest.artifacts[0]
    renamed = original.model_copy(update={"slug": "original-synthesis-slug"})
    manifest = finalize_manifest(manifest.model_copy(update={"artifacts": [renamed, *manifest.artifacts[1:]]}))
    dump_yaml(manifest, manifest_path, PathGuard(tmp_path))
    sidecar = tmp_path / original.provenance_path

    commit_project_registration(plan_project_registration(tmp_path))
    after = load_yaml(manifest_path)
    assert sorted((a.kind, tmp_path / a.path) for a in after.artifacts) == sorted(paths.items())
    reconciled = next(entry for entry in after.artifacts if entry.kind == original.kind)
    assert reconciled.slug == original.slug
    assert not any(entry.slug == "original-synthesis-slug" for entry in after.artifacts)
    assert reconciled.provenance_path == original.provenance_path
    assert sidecar.is_file()
    verify(after, tmp_path)


def test_namespaced_profile_identity_cannot_escape_provenance_directory(tmp_path):
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    profile = paths["agent_profile"]
    profile.write_text(profile.read_text().replace("profile-id: ops-responder", "profile-id: team/ops-responder"))
    plan = plan_project_registration(tmp_path)
    commit_project_registration(plan)
    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    entry = next(entry for entry in manifest.artifacts if entry.kind == "agent_profile")
    assert Path(entry.provenance_path).parent == Path(".kittify/charter/provenance")
    assert "team%2Fops-responder" in entry.provenance_path
    verify(manifest, tmp_path)


# ---------------------------------------------------------------------------
# Source deletion prunes the registration (#4121, squad MAJOR 1)
# ---------------------------------------------------------------------------


def test_deleted_source_prunes_node_edge_manifest_entry_and_sidecar(tmp_path):
    """Deleting an authored artifact after registering it must not leave a phantom.

    Pre-fix (live-reproduced by the squad on this very fixture): the node and
    the ``agent_profile -> procedure`` edge persisted in ``graph.yaml``, the
    manifest kept naming a nonexistent ``path`` (so ``verify()`` raised on
    every subsequent read with no in-tool recovery), and the phantom node
    still satisfied the profile reference, silencing the missing-reference
    warning #4100 promises exactly in the delete-after-register case.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.offering.drg.loader import load_graph_or_dir

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].unlink()

    plan = plan_project_registration(tmp_path)
    assert any("Pruned project registration for procedure:incident-runbook" in warning for warning in plan.warnings)
    # the missing-reference warning fires again: the phantom no longer satisfies it
    assert any("references unresolved procedure:incident-runbook" in warning for warning in plan.warnings)
    assert plan.graph.get_node("procedure:incident-runbook") is None
    assert all(e.target != "procedure:incident-runbook" for e in plan.graph.edges)
    assert any(str(path).endswith("procedure-incident-runbook.yaml") for path in plan.deletes)
    commit_project_registration(plan)

    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    assert all(entry.kind != "procedure" for entry in manifest.artifacts)
    assert not (tmp_path / ".kittify/charter/provenance/procedure-incident-runbook.yaml").exists()
    committed = load_graph_or_dir(tmp_path / ".kittify/doctrine")
    assert committed.get_node("procedure:incident-runbook") is None
    assert all(e.target != "procedure:incident-runbook" for e in committed.edges)


def test_deleting_every_source_prunes_the_whole_registration(tmp_path):
    """The all-artifacts-deleted case must also plan (and commit) the prune.

    Pre-fix, ``not artifacts`` short-circuited the plan before any bookkeeping
    was considered, so deleting the last authored artifact left the manifest
    permanently invalid with no write that could heal it.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    for path in paths.values():
        path.unlink()

    plan = plan_project_registration(tmp_path)
    assert plan.artifacts == ()
    assert len(plan.warnings) == 5
    assert plan.deletes
    commit_project_registration(plan)

    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    assert manifest.artifacts == []
    assert list((tmp_path / ".kittify/charter/provenance").glob("*.yaml")) == []


def test_pruned_registration_is_not_resurrected_by_replan(tmp_path):
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].unlink()
    commit_project_registration(plan_project_registration(tmp_path))

    again = plan_project_registration(tmp_path)
    assert not any("Pruned project registration" in warning for warning in again.warnings)
    assert again.deletes == ()
    assert again.writes == ()
    commit_project_registration(again)
    verify(load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml"), tmp_path)


def test_recreated_artifact_with_same_identity_keeps_its_sidecar(tmp_path):
    """A rename must re-register under the existing identity, not delete the
    fresh sidecar the same plan writes (the deletes/writes same-path guard)."""
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    renamed = paths["procedure"].with_name("moved.procedure.yaml")
    renamed.write_text(paths["procedure"].read_text().replace("Operational", "Relocated"))
    paths["procedure"].unlink()

    plan = plan_project_registration(tmp_path)
    commit_project_registration(plan)

    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    entry = next(entry for entry in manifest.artifacts if entry.kind == "procedure")
    assert entry.path.endswith("moved.procedure.yaml")
    sidecar = tmp_path / ".kittify/charter/provenance/procedure-incident-runbook.yaml"
    assert sidecar.is_file()


# ---------------------------------------------------------------------------
# In-place identity edit prunes the predecessor (#4121, squad pass-2 MAJOR)
# ---------------------------------------------------------------------------


def test_in_place_identity_edit_prunes_the_predecessor_registration(tmp_path):
    """An in-place ``id:`` edit must prune the predecessor, not re-point it.

    Pre-fix (live-probed by the squad on this head): staleness was keyed on the
    manifest entry's path, so a same-file identity edit left the old
    ``procedure:incident-runbook`` node in ``graph.yaml`` still satisfying the
    profile's reference — ``WARNINGS: ()``, exactly the silence #4100 exists
    to remove — while the predecessor's manifest entry was silently re-pointed
    at the new identity.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.offering.drg.loader import load_graph_or_dir

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].write_text(paths["procedure"].read_text().replace("incident-runbook", "incident-runbook-v2"))

    plan = plan_project_registration(tmp_path)
    assert any("Pruned project registration for procedure:incident-runbook" in warning for warning in plan.warnings)
    # the profile still references the old identity: the #4100 warning fires
    assert any("references unresolved procedure:incident-runbook" in warning for warning in plan.warnings)
    assert plan.graph.get_node("procedure:incident-runbook") is None
    assert plan.graph.get_node("procedure:incident-runbook-v2") is not None
    assert any(str(path).endswith("procedure-incident-runbook.yaml") for path in plan.deletes)
    commit_project_registration(plan)

    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    entry = next(entry for entry in manifest.artifacts if entry.kind == "procedure")
    assert entry.slug == "incident-runbook-v2"
    assert tmp_path / entry.path == paths["procedure"]
    assert not (tmp_path / ".kittify/charter/provenance/procedure-incident-runbook.yaml").exists()
    assert (tmp_path / ".kittify/charter/provenance/procedure-incident-runbook-v2.yaml").is_file()
    committed = load_graph_or_dir(tmp_path / ".kittify/doctrine")
    assert committed.get_node("procedure:incident-runbook") is None
    assert committed.get_node("procedure:incident-runbook-v2") is not None


def test_deleting_the_renamed_source_leaves_no_permanent_phantom(tmp_path):
    """The follow-up delete the finding probed: nothing may stay invisible.

    Pre-fix, after the in-place edit the phantom ``incident-runbook`` node had
    no manifest entry at all, so the entry-iterating prune could never see it:
    deleting the renamed source pruned only ``incident-runbook-v2`` and the
    phantom node and its edge persisted permanently in the committed graph
    with ``WARNINGS: ()``.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.offering.drg.loader import load_graph_or_dir

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].write_text(paths["procedure"].read_text().replace("incident-runbook", "incident-runbook-v2"))
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].unlink()

    plan = plan_project_registration(tmp_path)
    assert any("Pruned project registration for procedure:incident-runbook-v2" in warning for warning in plan.warnings)
    assert any("references unresolved procedure:incident-runbook" in warning for warning in plan.warnings)
    commit_project_registration(plan)

    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    verify(manifest, tmp_path)
    assert all(entry.kind != "procedure" for entry in manifest.artifacts)
    committed = load_graph_or_dir(tmp_path / ".kittify/doctrine")
    assert committed.get_node("procedure:incident-runbook") is None
    assert committed.get_node("procedure:incident-runbook-v2") is None
    assert list((tmp_path / ".kittify/charter/provenance").glob("procedure-*.yaml")) == []


def test_synthesis_owned_entry_with_missing_source_is_not_pruned(tmp_path):
    """Registration prunes only its own direct-write entries.

    A synthesized artifact's dead manifest entry is the synthesis lane's
    orphan (FR-014 refusal + ``charter synthesize --prune``), not this lane's.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].unlink()
    sidecar = tmp_path / ".kittify/charter/provenance/procedure-incident-runbook.yaml"
    sidecar.write_text(sidecar.read_text().replace("project-direct-write", "generated-adapter"))

    plan = plan_project_registration(tmp_path)
    assert not any("Pruned project registration" in warning for warning in plan.warnings)
    commit_project_registration(plan)
    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    assert any(entry.kind == "procedure" for entry in manifest.artifacts)


# ---------------------------------------------------------------------------
# Org-aware re-emission (#4121, squad MAJOR 2)
# ---------------------------------------------------------------------------


def _configure_org_pack(root: Path, *, node_id: str, kind: str = "procedures") -> None:
    """Write a one-node org pack (fragment shape) and register it in config."""
    pack = root / "org-pack"
    (pack / "drg").mkdir(parents=True)
    (pack / "drg" / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: org-pack
            source_kind: local_path
            source_ref: {pack}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: {node_id}
                kind: {kind}
                title: "Org fixture {node_id}"
            edges: []
            """
        )
    )
    (root / ".kittify").mkdir(exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(
        dedent(
            f"""\
            charter_packs:
              org:
                packs:
                  - name: org-pack
                    local_path: {pack}
            """
        )
    )


def test_resynthesis_reemits_org_referencing_profile_edges(tmp_path):
    """A project profile referencing an org-pack artifact must survive re-emission.

    Pre-fix: activation-time projection resolved against the org chain and
    committed the edge, but ``emit_project_layer`` projected against a
    built-in-only universe, so the next synthesis/resynthesis replaced the
    source's edges with the org-blind set and the project->org edge vanished
    from ``graph.yaml`` with only a ``logging.warning`` to show for it.
    """
    from charter.activation._drg_helpers import org_chain_graph
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.project_drg import emit_project_layer
    from charter.activation.synthesizer.reconcile import merge_project_overlay
    from charter.offering.drg.loader import load_built_in_graph

    _configure_org_pack(tmp_path, node_id="org-only-runbook")
    paths = author_guidance(tmp_path)
    profile = paths["agent_profile"]
    profile.write_text(
        profile.read_text().replace(
            "operating-procedures: [incident-runbook]",
            "operating-procedures: [incident-runbook, org-only-runbook]",
        )
    )

    # activation-time projection: the org chain resolves the reference
    plan = plan_project_registration(tmp_path)
    assert plan.warnings == ()
    assert any(e.target == "procedure:org-only-runbook" for e in plan.graph.edges)
    commit_project_registration(plan)

    org_drg = org_chain_graph(tmp_path)
    assert org_drg is not None and org_drg.get_node("procedure:org-only-runbook") is not None

    built_in = load_built_in_graph()
    warnings: list[str] = []
    overlay = emit_project_layer([], "test", built_in, project_root=tmp_path, org_drg=org_drg, warnings_out=warnings)
    assert warnings == []
    assert any(e.target == "procedure:org-only-runbook" for e in overlay.edges)

    # merge_project_overlay replaces the source's edges with the fresh set —
    # with the org-aware emit that set still carries the project->org edge
    merged = merge_project_overlay(existing_overlay=overlay, updated_overlay=overlay)
    assert any(e.target == "procedure:org-only-runbook" for e in merged.edges)

    # regression contrast: the org-blind emit this fix replaces
    blind_warnings: list[str] = []
    blind = emit_project_layer([], "test", built_in, project_root=tmp_path, warnings_out=blind_warnings)
    assert not any(e.target == "procedure:org-only-runbook" for e in blind.edges)
    assert any("procedure:org-only-runbook" in warning for warning in blind_warnings)


def test_artifactless_repo_plans_nothing_and_missing_sidecar_is_left_untouched(tmp_path):
    """Two scope boundaries of the prune (#4121).

    An artifact-less, manifest-less repo plans nothing (the pre-existing
    no-op early return, now also gated on there being nothing to prune); and
    a dead direct-write entry whose provenance sidecar has ALSO vanished
    cannot be identified, so it is deliberately left untouched rather than
    pruned on a guess.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    plan = plan_project_registration(tmp_path)
    assert plan.artifacts == ()
    assert plan.warnings == ()
    assert plan.writes == ()
    assert plan.deletes == ()

    paths = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    paths["procedure"].unlink()
    (tmp_path / ".kittify/charter/provenance/procedure-incident-runbook.yaml").unlink()

    plan = plan_project_registration(tmp_path)
    assert not any("Pruned project registration" in warning for warning in plan.warnings)
    assert plan.deletes == ()


# ---------------------------------------------------------------------------
# WP03: slug_for reconciliation + #4834 path-update (T012, T016)
# ---------------------------------------------------------------------------


def test_legacy_non_canonical_directive_slug_reconciles_and_moves_sidecar(tmp_path):
    """T012 falsifying test: unlike the generic hand-edit test above, a
    directive's canonical slug genuinely differs from a legacy SCREAMING
    slug, so reconciliation must move (not merely relabel) the provenance
    sidecar -- the legacy path is deleted, the canonical path is (re)written,
    and the manifest never carries a duplicate entry for the same identity.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.manifest import dump_yaml, finalize_manifest
    from charter.activation.synthesizer.path_guard import PathGuard

    author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    manifest_path = tmp_path / ".kittify/charter/synthesis-manifest.yaml"
    manifest = load_yaml(manifest_path)
    directive_entry = next(e for e in manifest.artifacts if e.kind == "directive")
    assert directive_entry.slug == "change-freeze"

    legacy_provenance_path = ".kittify/charter/provenance/directive-CHANGE_FREEZE.yaml"
    (tmp_path / directive_entry.provenance_path).rename(tmp_path / legacy_provenance_path)
    legacy_entry = directive_entry.model_copy(update={"slug": "CHANGE_FREEZE", "provenance_path": legacy_provenance_path})
    others = [e for e in manifest.artifacts if e.kind != "directive"]
    manifest = finalize_manifest(manifest.model_copy(update={"artifacts": [legacy_entry, *others]}))
    dump_yaml(manifest, manifest_path, PathGuard(tmp_path))

    plan = plan_project_registration(tmp_path)
    assert any(path == tmp_path / legacy_provenance_path for path in plan.deletes)
    commit_project_registration(plan)

    after = load_yaml(manifest_path)
    assert [e for e in after.artifacts if e.kind == "directive"] == [directive_entry]
    assert not (tmp_path / legacy_provenance_path).exists()
    assert (tmp_path / directive_entry.provenance_path).is_file()
    verify(after, tmp_path)


def test_path_and_provenance_drift_rewrites_manifest_entry_without_deleting_sidecar(tmp_path):
    """#4834 path-update (T016): a manifest entry whose recorded ``path`` has
    drifted from the freshly-resolved value -- on otherwise UNCHANGED content
    -- is corrected in a single registration pass rather than silently
    skipped by the pre-fix early ``continue``. No sidecar is deleted.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.manifest import dump_yaml, finalize_manifest
    from charter.activation.synthesizer.path_guard import PathGuard

    author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    manifest_path = tmp_path / ".kittify/charter/synthesis-manifest.yaml"
    manifest = load_yaml(manifest_path)
    original = next(e for e in manifest.artifacts if e.kind == "procedure")
    drifted = original.model_copy(update={"path": ".kittify/doctrine/procedures/stale-recorded-path.procedure.yaml"})
    others = [e for e in manifest.artifacts if e.kind != "procedure"]
    manifest = finalize_manifest(manifest.model_copy(update={"artifacts": [drifted, *others]}))
    dump_yaml(manifest, manifest_path, PathGuard(tmp_path))
    sidecar = tmp_path / original.provenance_path

    plan = plan_project_registration(tmp_path)
    assert plan.writes  # not silently skipped by the pre-fix early continue
    assert plan.deletes == ()
    commit_project_registration(plan)

    after = load_yaml(manifest_path)
    reconciled = next(e for e in after.artifacts if e.kind == "procedure")
    assert reconciled.path == original.path
    assert reconciled.path != drifted.path
    assert reconciled.provenance_path == original.provenance_path
    assert sidecar.is_file()
    verify(after, tmp_path)


def test_corrupt_sidecar_degrades_to_untouched_not_crash(tmp_path):
    """An unreadable sidecar must not take planning down with it (#4121 pass 2).

    The URN probe is best-effort, mirroring ``reconcile._provenance_urn``:
    a sidecar that fails to load degrades to "not this lane's to touch", so
    planning completes and the entry is left for its owning lane rather than
    crashing every subsequent activation.
    """
    from charter.activation.project_registration import plan_project_registration, commit_project_registration

    author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    sidecar = tmp_path / ".kittify/charter/provenance/procedure-incident-runbook.yaml"
    sidecar.write_text("artifact_urn: [unclosed")

    plan = plan_project_registration(tmp_path)  # must not raise
    assert not any("Pruned project registration" in warning for warning in plan.warnings)
    assert plan.deletes == ()
    commit_project_registration(plan)
