"""#4253: activating one artifact must not deactivate the rest.

While a kind's activation key is ABSENT, the activation-aware resolver treats
the kind as unrestricted — every available artifact is effective. The first
``charter activate`` for that kind materialized a shipped default list instead,
which is a strict subset of the available corpus, so one unrelated activation
silently deactivated everything outside it. Five projects lost 15 directives
and 11 procedures this way (``adversarial-squad-deployment`` and
``red-main-release-discipline`` among them), and the new-policy tests of the
day passed throughout, because they only asserted that the *newly* activated
artifact resolved.

These tests assert the dimension those missed: what was effective before is
still effective after (effective before ⊆ effective after), measured through
the consumer surfaces (``PackContext.from_config`` and the activation-aware
doctrine service), not by reading the YAML back.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service
from charter.activation.invocation_context import ProjectContext
from charter.activation.layer_roots import resolve_layer_roots
from charter.activation.pack_context import PackContext
from charter.activation.pack_manager import ActiveCharterManager
from specify_cli.cli.commands.charter import charter_app

pytestmark = [pytest.mark.integration]

runner = CliRunner()


@pytest.fixture
def project_without_activation_keys(tmp_path: Path) -> Path:
    """A project in the unrestricted state: no ``activated_*`` key at all."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    return tmp_path


def _activate(project_root: Path, kind: str, artifact_id: str):
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), kind, artifact_id],
        catch_exceptions=False,
    )


def _available(project_root: Path, kind: str) -> set[str]:
    """What the resolver exposes while the kind is unrestricted — i.e. exactly
    what was effective before the first activation, which is the oracle these
    tests measure preservation against."""
    return set(ActiveCharterManager().list_available(ProjectContext.from_repo(project_root), kind))


def _effective_directives(repo: Path) -> set[str]:
    """The directive ids the activation-aware service has in force."""
    from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

    return set(build_activation_aware_doctrine_service(repo).directives)


def test_first_activation_keeps_every_previously_effective_directive(
    project_without_activation_keys: Path,
) -> None:
    project_root = project_without_activation_keys
    before = PackContext.from_config(project_root)
    assert before.activated_directives is None, "fixture invalid: the kind must start unrestricted, or there is no narrowing to observe"
    effective_before = _effective_directives(project_root)
    assert len(effective_before) > 1, "fixture invalid: only one directive is effective, so this test could not observe a narrowing"

    result = _activate(project_root, "directive", "001-architectural-integrity-standard")
    assert result.exit_code == 0, result.output

    after = PackContext.from_config(project_root)
    assert after.activated_directives is not None, "control: the activation wrote the directive key"
    assert set(after.activated_directives) >= _available(project_root, "directive")

    lost = effective_before - _effective_directives(project_root)
    assert not lost, f"#4253: activating one directive deactivated {len(lost)} previously effective directive(s): {sorted(lost)}"


def test_activating_a_directive_leaves_procedures_untouched(
    project_without_activation_keys: Path,
) -> None:
    """The reported loss crossed kinds: procedures disappeared too.

    Activating a directive must not write — or narrow — another kind's set.
    """
    project_root = project_without_activation_keys

    result = _activate(project_root, "directive", "001-architectural-integrity-standard")
    assert result.exit_code == 0, result.output

    after = PackContext.from_config(project_root)
    assert after.activated_procedures is None, (
        "#4253: activating a directive restricted the procedure set; adversarial-squad-deployment and red-main-release-discipline were lost this way"
    )


def test_first_activation_of_a_procedure_keeps_the_rest_effective(
    project_without_activation_keys: Path,
) -> None:
    project_root = project_without_activation_keys

    result = _activate(project_root, "procedure", "adversarial-squad-deployment")
    assert result.exit_code == 0, result.output

    after = PackContext.from_config(project_root)
    assert after.activated_procedures is not None
    effective = set(after.activated_procedures)

    assert "adversarial-squad-deployment" in effective
    previously_effective = _available(project_root, "procedure")
    lost = previously_effective - effective
    assert not lost, (
        f"#4253: activating one procedure deactivated {len(lost)} previously effective "
        f"procedure(s): {sorted(lost)} — red-main-release-discipline was lost exactly this way"
    )


def test_an_explicitly_restricted_set_is_still_respected(tmp_path: Path) -> None:
    """Explicit restriction is a decision, not an accident — activation appends
    to it and never re-widens it to the whole corpus."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "activated_directives:\n  - 001-architectural-integrity-standard\nmission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )

    result = _activate(tmp_path, "directive", "003-decision-documentation-requirement")
    assert result.exit_code == 0, result.output

    effective = set(PackContext.from_config(tmp_path).activated_directives or [])
    assert len(effective) == 2, f"an explicit set must stay explicit, got {sorted(effective)}"


def test_an_explicitly_empty_set_is_still_respected(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("activated_directives: []\nmission_type_activations:\n  - software-dev\n", encoding="utf-8")

    result = _activate(tmp_path, "directive", "001-architectural-integrity-standard")
    assert result.exit_code == 0, result.output

    effective = set(PackContext.from_config(tmp_path).activated_directives or [])
    assert len(effective) == 1, f"explicit-empty must stay explicit, got {sorted(effective)}"


def test_an_unknown_id_fails_without_mutating_the_config(
    project_without_activation_keys: Path,
) -> None:
    project_root = project_without_activation_keys
    config = project_root / ".kittify" / "config.yaml"
    before = config.read_bytes()

    result = runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), "directive", "999-not-a-real-directive"],
    )

    assert result.exit_code != 0
    assert config.read_bytes() == before, "a failed activation must not write"
    assert PackContext.from_config(project_root).activated_directives is None


# ---------------------------------------------------------------------------
# #4399 squad round: the two configurations the issue's acceptance names but
# the first pass did not cover — a declared org CHAIN, and an artifact whose
# `id:` diverges from its filename stem.
# ---------------------------------------------------------------------------


def _write_org_procedure(pack_root: Path, *, stem: str, declared_id: str) -> None:
    """One org-pack procedure whose declared id may differ from its file stem."""
    procedures = pack_root / "procedures"
    procedures.mkdir(parents=True, exist_ok=True)
    # Same shape as a built-in procedure (packs/built-in/procedures/*.yaml):
    # the loader rejects unknown keys, so the fixture has to be a real one.
    (procedures / f"{stem}.procedure.yaml").write_text(
        'schema_version: "1.0"\n'
        f"id: {declared_id}\n"
        f"name: {declared_id} fixture procedure\n"
        "purpose: >\n"
        "  Prove that org-layer artifacts survive an unrelated activation.\n"
        "entry_condition: >\n"
        "  An activation runs while this kind has no explicit activation set.\n"
        "exit_condition: >\n"
        "  The artifact is still effective afterwards.\n"
        "steps:\n"
        "  - title: Observe\n"
        "    description: >\n"
        "      Read the effective set before and after the activation.\n"
        "    actor: agent\n",
        encoding="utf-8",
    )


def _declare_org_packs(repo: Path, *pack_roots: Path) -> None:
    lines = ["mission_type_activations:", "  - software-dev", "doctrine:", "  org:", "    packs:"]
    for index, root in enumerate(pack_roots):
        lines.append(f"      - name: preservation-fixture-{index}")
        lines.append(f"        local_path: {root}")
    (repo / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _effective_procedures(repo: Path) -> set[str]:
    from charter.activation.doctrine_service_builder import build_activation_aware_doctrine_service

    return set(build_activation_aware_doctrine_service(repo).procedures)


def test_artifacts_in_the_second_org_pack_survive_activation(tmp_path: Path) -> None:
    """#4399 MAJOR 1: the declared org chain is preserved, not just pack #1.

    The CLI's ``layer_roots`` map truncates to the first org pack by a
    documented back-compat contract, so sourcing the preserved set from it
    left every artifact in packs 2+ to be silently deactivated.
    """
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    pack_one = tmp_path / "org-one"
    pack_two = tmp_path / "org-two"
    _write_org_procedure(pack_one, stem="org1-proc", declared_id="org1-proc")
    _write_org_procedure(pack_two, stem="org2-proc", declared_id="org2-proc")
    _declare_org_packs(repo, pack_one, pack_two)

    before = _effective_procedures(repo)
    assert {"org1-proc", "org2-proc"} <= before, f"fixture invalid: both packs must be effective first, got {sorted(before)}"

    result = _activate(repo, "procedure", "spike-timebox-policy")
    assert result.exit_code == 0, result.output

    after = _effective_procedures(repo)
    assert "org2-proc" in after, "#4399 MAJOR 1: activating an unrelated procedure deactivated the second org pack's artifact"
    assert "org1-proc" in after


def test_an_id_that_diverges_from_its_stem_survives_activation(tmp_path: Path) -> None:
    """#4399 MAJOR 2: the preserved set is written in the keyspace the filter uses.

    The resolver matches Pattern-B/C kinds on the declared ``id:`` by plain
    membership, so a set written as filename stems is filtered straight back
    out whenever the two diverge.
    """
    repo = tmp_path / "repo"
    (repo / ".kittify").mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    pack = tmp_path / "org-divergent"
    _write_org_procedure(pack, stem="acme-release", declared_id="acme-release-proc")
    _declare_org_packs(repo, pack)

    assert "acme-release-proc" in _effective_procedures(repo), "fixture invalid: the divergent-id procedure must be effective first"

    result = _activate(repo, "procedure", "spike-timebox-policy")
    assert result.exit_code == 0, result.output

    assert "acme-release-proc" in _effective_procedures(repo), "#4399 MAJOR 2: the divergent-id org procedure was written by stem and filtered back out"


# ---------------------------------------------------------------------------
# #4400 (WP06 review cycle 1): the tolerant fallback never narrows below the
# readable chain. When the effective set of an absent key cannot be resolved,
# ``activate`` seeds the key from the seam's ``EffectiveSet.fallback_ids``: the
# union over the built-in layer, EVERY readable declared org root and the
# project layer. The CLI's ``layer_roots`` map holds org pack #1 only, so
# seeding from it deactivated org packs 2+.
# ---------------------------------------------------------------------------

ALREADY_EFFECTIVE = "already effective"


def _fb_tactic(directory: Path, tactic_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{tactic_id}.tactic.yaml").write_text(
        f'schema_version: "1.0"\nid: {tactic_id}\nname: {tactic_id}\npurpose: Fixture tactic.\nsteps:\n  - title: Act\n    description: Do the thing.\n',
        encoding="utf-8",
    )


def _fb_project(tmp_path: Path, packs: list[str]) -> Path:
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    with (root / ".kittify" / "config.yaml").open("w", encoding="utf-8") as fh:
        YAML().dump({"charter_packs": {"org": {"packs": [{"name": name, "local_path": f"org-packs/{name}"} for name in packs]}}}, fh)
    return root


def _fb_config(root: Path) -> dict[str, object]:
    data = YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _fb_effective_tactics(root: Path) -> set[str]:
    return {str(key) for key in build_activation_aware_doctrine_service(root).tactics}


def _fb_activate(root: Path, kind: str, artifact_id: str) -> list[str]:
    return ActiveCharterManager().activate(ProjectContext(repo_root=root), kind, artifact_id, layer_roots=resolve_layer_roots(root)).warnings


def test_missing_middle_org_root_keeps_pack_three_effective(tmp_path: Path) -> None:
    root = _fb_project(tmp_path, ["a", "b", "c"])
    _fb_tactic(root / "org-packs" / "a" / "tactics", "org-a-tactic")
    _fb_tactic(root / "org-packs" / "c" / "tactics", "org-c-tactic")
    assert "org-c-tactic" in _fb_effective_tactics(root), "control: pack c is effective while the key is absent"

    warnings = _fb_activate(root, "tactic", "org-a-tactic")

    written = _fb_config(root)["activated_tactics"]
    assert isinstance(written, list) and {"org-a-tactic", "org-c-tactic"} <= set(written)
    assert "org-c-tactic" in _fb_effective_tactics(root)
    assert any("could not be resolved because" in w and "org-packs/b" in w and "across all readable layers" in w for w in warnings), warnings
    assert not any(ALREADY_EFFECTIVE in w for w in warnings), "the engine must not claim nothing in force was deactivated"


def test_service_build_failure_keeps_both_readable_org_packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import charter.activation.doctrine_service_builder as builder

    root = _fb_project(tmp_path, ["a", "c"])
    _fb_tactic(root / "org-packs" / "a" / "tactics", "org-a-tactic")
    _fb_tactic(root / "org-packs" / "c" / "tactics", "org-c-tactic")
    assert "org-c-tactic" in _fb_effective_tactics(root), "control"

    def broken(repo_root: Path) -> None:
        raise RuntimeError(f"cannot build for {repo_root.name}")

    with monkeypatch.context() as patch:
        patch.setattr(builder, "build_activation_aware_doctrine_service", broken)
        warnings = _fb_activate(root, "tactic", "org-a-tactic")

    written = _fb_config(root)["activated_tactics"]
    assert isinstance(written, list) and {"org-a-tactic", "org-c-tactic"} <= set(written)
    assert "org-c-tactic" in _fb_effective_tactics(root)
    assert any("doctrine service cannot be built" in w for w in warnings), warnings
    assert not any(ALREADY_EFFECTIVE in w for w in warnings)


def test_resolved_set_still_reports_nothing_deactivated(tmp_path: Path) -> None:
    root = _fb_project(tmp_path, ["a", "c"])
    _fb_tactic(root / "org-packs" / "a" / "tactics", "org-a-tactic")
    _fb_tactic(root / "org-packs" / "c" / "tactics", "org-c-tactic")

    warnings = _fb_activate(root, "tactic", "org-a-tactic")

    assert any(ALREADY_EFFECTIVE in w for w in warnings), warnings
    assert not any("could not be resolved" in w for w in warnings)


def _fb_mission_type(directory: Path, mission_type_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{mission_type_id}.yaml").write_text(f"schema_version: 1\nid: {mission_type_id}\ndisplay_name: {mission_type_id}\n", encoding="utf-8")


def test_mission_type_seeding_spans_both_org_packs(tmp_path: Path) -> None:
    """An absent ``mission_type_activations`` puts nothing in force; seeding is symmetric across org packs."""
    root = _fb_project(tmp_path, ["one", "two"])
    _fb_mission_type(root / "org-packs" / "one" / "mission_types", "mt-one")
    _fb_mission_type(root / "org-packs" / "two" / "mission_types", "mt-two")

    warnings = _fb_activate(root, "mission-type", "mt-one")

    written = _fb_config(root)["mission_type_activations"]
    assert isinstance(written, list)
    assert {"software-dev", "mt-one", "mt-two"} <= set(written), written
    assert any("no mission type was in force" in w and "mission types available across all readable layers" in w for w in warnings), warnings
    assert not any(ALREADY_EFFECTIVE in w for w in warnings)
