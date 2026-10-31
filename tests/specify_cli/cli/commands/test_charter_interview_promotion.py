"""End-to-end CLI test: `spec-kitty charter interview` promotes selections (WP07, T024, FR-007).

Proves the wiring between the `charter interview` command and
``charter.activation.activation_engine.promote_activations`` (via
``charter.activation.kind_vocabulary.resolve_selected_id_to_stem`` and the
effective-set seam ``charter.activation.effective_set``) — the captured
`selected_paradigms` / `selected_directives` must be append-promoted into
the ``activated_*`` keys of the activation authority (the activation ledger,
``.kittify/charter/activation.yaml``, for these fresh projects; FR-019) after
every interview run,
without dropping anything that was effective while the key was absent
(FR-015 / #4400, exercised here at the live CLI call site).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from charter.activation.effective_set import resolve_effective_sets
from charter.offering.artifact_kinds import ArtifactKind
from kernel.activation_ledger_store import activation_ledger_path
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

# Real built-in artifacts (this module never mocks resolve_offering_root()).
_DIRECTIVE_010_STEM = "010-specification-fidelity-requirement"
_DIRECTIVE_010_CANONICAL = "DIRECTIVE_010"
_PARADIGM_DDD = "domain-driven-design"


def _git_init(repo: Path) -> None:
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    for key, value in (
        ("user.email", "test@example.com"),
        ("user.name", "Test User"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(["git", "config", key, value], cwd=repo, check=True, capture_output=True)


def _read_config_yaml(repo_root: Path) -> dict[str, object]:
    """The legacy ``config.yaml`` of an unmigrated fixture (legacy keys, no ledger): its writes keep that target."""
    loaded = YAML(typ="safe").load((repo_root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _read_config(repo_root: Path) -> dict[str, object]:
    """The promoted activation state: a fresh project writes the activation ledger (FR-019)."""
    config_path = activation_ledger_path(repo_root)
    assert config_path.exists(), f"activation ledger not written at {config_path}"
    yaml = YAML(typ="safe")
    loaded = yaml.load(config_path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_interview_leaves_an_absent_key_absent_and_names_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No pre-existing config.yaml (absent-key state): the promotion writes nothing (#6685).

    An absent ``activated_<kind>`` key means every available artifact of the kind is in
    force, so the selection is already in force; writing the in-force set into the key
    turned "nothing chosen yet" into an operator's activation, which ``charter synthesize``
    answered by demanding a companion tactic per directive and skipping the fresh-project
    seed (#2577, #4785, #6629).
    """
    _git_init(tmp_path)
    # Hermetic against a stray ``.kittify`` marker anywhere above ``tmp_path``
    # (e.g. a developer's home-dir kittify root, or another test's litter
    # under the OS temp dir): with no config.yaml at ``tmp_path`` yet,
    # ``locate_project_root``'s walk-up would otherwise happily resolve to
    # that ambient ancestor instead of this fixture's repo, and the
    # promoted config.yaml would land there instead of under tmp_path.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    effective = resolve_effective_sets(tmp_path, ["activated_directives", "activated_paradigms"])
    effective_directives = effective["activated_directives"].ids
    effective_paradigms = effective["activated_paradigms"].ids
    assert len(effective_directives) > 1 and len(effective_paradigms) > 1, "control: a narrowing is observable"
    result = runner.invoke(
        charter_app,
        [
            "interview",
            "--defaults",
            "--profile", "minimal",
            "--selected-directives", _DIRECTIVE_010_STEM,
            "--selected-paradigms", _PARADIGM_DDD,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"interview failed: stdout={result.stdout!r}"

    # No allow list on any activation surface (a fresh project writes the activation ledger).
    for surface in (activation_ledger_path(tmp_path), tmp_path / ".kittify" / "config.yaml"):
        if surface.exists():
            data = YAML(typ="safe").load(surface.read_text(encoding="utf-8")) or {}
            assert "activated_directives" not in data, f"{surface.name} gained an activation key (#6685)"
            assert "activated_paradigms" not in data, f"{surface.name} gained an activation key (#6685)"
    # The run says what it left absent, and names the flag that writes an explicit list.
    assert "activated_directives" in result.stdout and "activated_paradigms" in result.stdout, result.stdout
    assert "--narrow-activation" in result.stdout, result.stdout
    # Nothing effective before stops applying (FR-015, at this call site).
    after = resolve_effective_sets(tmp_path, ["activated_directives", "activated_paradigms"])
    assert effective_directives <= after["activated_directives"].ids
    assert effective_paradigms <= after["activated_paradigms"].ids


def test_interview_normalizes_canonical_form_directive_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directive selected in canonical id form (DIRECTIVE_010) still promotes
    into config as its config-stem form (ID-form parity, WP01 resolver reuse).
    """
    _git_init(tmp_path)
    # See the hermeticity note in
    # test_interview_promotes_selections_preserving_builtins_on_absent_key.
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_directives=[_DIRECTIVE_001_STEM])
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        [
            "interview",
            "--defaults",
            "--profile", "minimal",
            "--selected-directives", _DIRECTIVE_010_CANONICAL,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout

    config = _read_config(tmp_path)
    assert _DIRECTIVE_010_STEM in config["activated_directives"]
    assert _DIRECTIVE_010_CANONICAL not in config["activated_directives"]


def test_interview_promotion_is_idempotent_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_path)
    # See the hermeticity note in
    # test_interview_promotes_selections_preserving_builtins_on_absent_key.
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_directives=[_DIRECTIVE_001_STEM])
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    args = [
        "interview",
        "--defaults",
        "--profile", "minimal",
        "--selected-directives", _DIRECTIVE_010_STEM,
    ]
    first = runner.invoke(charter_app, args, catch_exceptions=False)
    assert first.exit_code == 0
    after_first = activation_ledger_path(tmp_path).read_text(encoding="utf-8")
    second = runner.invoke(charter_app, args, catch_exceptions=False)
    assert second.exit_code == 0

    config = _read_config(tmp_path)
    assert config["activated_directives"].count(_DIRECTIVE_010_STEM) == 1
    assert activation_ledger_path(tmp_path).read_text(encoding="utf-8") == after_first, "a second run wrote bytes (#6685 NFR-002)"


def test_interview_with_no_selections_leaves_config_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-007 is append-only: an interview run with no directive/paradigm
    selections must not fabricate config.yaml activation keys.
    """
    _git_init(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        [
            "interview",
            "--defaults",
            "--profile", "minimal",
            "--selected-directives", "",
            "--selected-paradigms", "",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout

    for config_path in (tmp_path / ".kittify" / "config.yaml", activation_ledger_path(tmp_path)):
        if config_path.exists():
            data = YAML(typ="safe").load(config_path.read_text(encoding="utf-8")) or {}
            assert "activated_directives" not in data
            assert "activated_paradigms" not in data


# --- #6408: opt-in --narrow-activation -------------------------------------

_DIRECTIVE_001_STEM = "001-architectural-integrity-standard"


def _run_interview_json(repo: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> dict[str, object]:
    import json

    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo))
    monkeypatch.chdir(repo)
    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal", "--json", *extra],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_interview_narrow_activation_replaces_directive_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_path)
    effective = resolve_effective_sets(tmp_path, ["activated_directives"])["activated_directives"].ids
    assert len(effective) > 1, "control: narrowing is observable"

    payload = _run_interview_json(
        tmp_path, monkeypatch, "--selected-directives", "DIRECTIVE_001", "--narrow-activation"
    )

    assert _read_config(tmp_path)["activated_directives"] == [_DIRECTIVE_001_STEM]
    narrowed = payload["narrowed"]
    assert isinstance(narrowed, dict)
    assert set(narrowed["activated_directives"]) == set(effective) - {_DIRECTIVE_001_STEM}


def test_interview_narrow_activation_narrows_paradigms_to_the_interview_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Paradigms narrow to whatever the interview selected (``--defaults`` fills it from the profile defaults)."""
    _git_init(tmp_path)
    effective = resolve_effective_sets(tmp_path, ["activated_paradigms"])["activated_paradigms"].ids
    assert len(effective) > 1, "control: narrowing is observable"

    payload = _run_interview_json(tmp_path, monkeypatch, "--selected-paradigms", _PARADIGM_DDD, "--narrow-activation")

    assert _read_config(tmp_path)["activated_paradigms"] == [_PARADIGM_DDD]
    assert set(payload["narrowed"]["activated_paradigms"]) == set(effective) - {_PARADIGM_DDD}


@pytest.mark.parametrize("untouched_key", ["activated_paradigms", "activated_tactics"])
def test_interview_narrow_activation_with_defaults_leaves_empty_selection_kinds_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, untouched_key: str
) -> None:
    """Shipped ``--defaults`` select no paradigms or tactics, so ``--narrow-activation`` leaves those keys alone."""
    _git_init(tmp_path)
    payload = _run_interview_json(tmp_path, monkeypatch, "--selected-directives", "DIRECTIVE_001", "--narrow-activation")

    assert untouched_key not in _read_config(tmp_path)
    assert untouched_key not in payload["narrowed"]
    # Positive control: directives were narrowed in the same run.
    assert "activated_directives" in payload["narrowed"]


def test_interview_narrow_activation_with_explicit_paradigms_narrows_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_path)
    paradigm = sorted(resolve_effective_sets(tmp_path, ["activated_paradigms"])["activated_paradigms"].ids)[0]
    payload = _run_interview_json(
        tmp_path, monkeypatch, "--selected-paradigms", paradigm, "--narrow-activation"
    )

    assert "activated_paradigms" in payload["narrowed"]
    assert "activated_paradigms" in _read_config(tmp_path)


def test_interview_without_narrow_is_unchanged_and_reports_empty_narrowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without ``--narrow-activation`` an absent key stays absent and ``narrowed`` is empty (#6408, #6685)."""
    _git_init(tmp_path)

    payload = _run_interview_json(tmp_path, monkeypatch, "--selected-directives", "DIRECTIVE_001")

    assert payload["narrowed"] == {}
    surface = activation_ledger_path(tmp_path)
    written = YAML(typ="safe").load(surface.read_text(encoding="utf-8")) if surface.exists() else {}
    assert "activated_directives" not in (written or {}), "an absent key was seeded without --narrow-activation (#6685)"


def test_interview_narrow_activation_text_output_lists_dropped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_init(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal", "--selected-directives", "DIRECTIVE_001", "--narrow-activation"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "No longer in force" in result.stdout
    assert "activated_directives" in result.stdout


def test_interview_narrow_with_org_pack_keeps_org_required_stem_spelled_tactic(tmp_path: Path) -> None:
    """An org-required tactic whose stem differs from its id stays and is not reported dropped (#6408)."""
    from types import SimpleNamespace

    from specify_cli.cli.commands.charter.interview import _promote_interview_selections
    from tests.charter.org_pack_identity_support import ORG_PACK_NAME, write_identity_org_pack

    _git_init(tmp_path)
    pack = write_identity_org_pack(tmp_path)
    (pack / "org-charter.yaml").write_text(
        f'schema_version: "2"\norg_name: {ORG_PACK_NAME}\nrequired_tactics:\n  - qa-seven\n', encoding="utf-8"
    )
    interview_data = SimpleNamespace(selected_directives=[], selected_tactics=["qa-seven"], selected_paradigms=[])
    effective = resolve_effective_sets(tmp_path, ["activated_tactics"])["activated_tactics"].ids
    assert len(effective) > 1, "control: narrowing is observable"

    warnings, narrowed = _promote_interview_selections(tmp_path, interview_data, narrow=True)

    assert _read_config_yaml(tmp_path)["activated_tactics"][0] == "qa-tactic-seven"
    assert "qa-tactic-seven" in _read_config_yaml(tmp_path)["activated_tactics"]
    dropped = narrowed.get("activated_tactics", [])
    assert "qa-seven" not in dropped and "qa-tactic-seven" not in dropped
    assert set(dropped) == {item for item in effective if item not in {"qa-seven"}} - {"qa-tactic-seven"}
    assert not any("could not be listed" in warning for warning in warnings)


def test_effective_set_the_narrow_promotion_reads_is_already_in_stem_spelling(tmp_path: Path) -> None:
    """Re-pin (#6435): the seam emits stems, so the interview's former declared-id -> stem mapping is gone."""
    from tests.charter.org_pack_identity_support import write_identity_org_pack

    write_identity_org_pack(tmp_path)

    effective = resolve_effective_sets(tmp_path, ["activated_tactics"])["activated_tactics"].ids

    assert "qa-tactic-seven" in effective
    assert "qa-seven" not in effective


def test_interview_narrow_activation_failure_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An explicit --narrow-activation that cannot be applied fails, in JSON and text modes (#6408)."""
    import json

    import importlib

    interview_mod = importlib.import_module("specify_cli.cli.commands.charter.interview")

    _git_init(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("narrowing exploded")

    monkeypatch.setattr(interview_mod, "_promote_interview_selections", _boom)
    base = ["interview", "--defaults", "--profile", "minimal", "--selected-directives", "DIRECTIVE_001"]

    as_json = runner.invoke(charter_app, [*base, "--json", "--narrow-activation"])
    assert as_json.exit_code != 0
    payload = json.loads(as_json.stdout)
    assert payload["success"] is False
    assert "narrowing exploded" in payload["error"]

    as_text = runner.invoke(charter_app, [*base, "--narrow-activation"])
    assert as_text.exit_code != 0

    # Best-effort path preserved without --narrow-activation.
    best_effort = runner.invoke(charter_app, [*base])
    assert best_effort.exit_code == 0, best_effort.output


def test_interview_narrow_activation_compares_a_present_declared_id_list_by_stem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A present list spelled DIRECTIVE_003 narrowed to the same artifact's stem drops nothing (#6408)."""
    _git_init(tmp_path)
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("activated_directives:\n- DIRECTIVE_003\n", encoding="utf-8")

    payload = _run_interview_json(
        tmp_path, monkeypatch, "--selected-directives", "003-decision-documentation-requirement", "--narrow-activation"
    )

    assert "activated_directives" not in payload["narrowed"], payload["narrowed"]
    assert _read_config_yaml(tmp_path)["activated_directives"] == ["003-decision-documentation-requirement"]


# --- FR-009: the interview never re-adds an excluded id (ledger-seeded, mode-independent) ---


def test_interview_reselecting_a_denied_directive_keeps_it_excluded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    seed_activation_ledger(
        tmp_path,
        mission_type_activations=["software-dev"],
        activated_directives=[_DIRECTIVE_001_STEM],
        deactivated_directives=[_DIRECTIVE_010_STEM],
    )
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal", "--selected-directives", _DIRECTIVE_010_CANONICAL],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    ledger = read_activation_ledger(tmp_path)
    assert ledger["activated_directives"] == [_DIRECTIVE_001_STEM]
    assert ledger["deactivated_directives"] == [_DIRECTIVE_010_STEM]
    assert f"kept deactivated: directive {_DIRECTIVE_010_STEM}" in " ".join(result.stdout.split())


def test_interview_leaves_an_absent_key_absent_and_names_a_denied_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#6685 + FR-009: an absent key stays absent, and a deactivated selection is reported, never claimed as in force."""
    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], deactivated_directives=[_DIRECTIVE_001_STEM])
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal", "--selected-directives", _DIRECTIVE_001_STEM],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    surface = activation_ledger_path(tmp_path)
    written = YAML(typ="safe").load(surface.read_text(encoding="utf-8")) or {}
    assert "activated_directives" not in written, "an absent key stays absent (#6685)"
    out = " ".join(result.stdout.split())
    assert f"kept deactivated: directive {_DIRECTIVE_001_STEM}" in out, out
    assert "every selected directive is deactivated" in out, out


# --- F1/F2: promotion reads the effective deny only through the activation ledger seam ---


def _org_pack_project(tmp_path: Path, required_directives: list[str]) -> None:
    pack = tmp_path / "org-packs" / "acme"
    pack.mkdir(parents=True)
    listed = "".join(f"  - {item}\n" for item in required_directives)
    (pack / "org-charter.yaml").write_text(f"schema_version: 1\norg_name: Acme\nrequired_directives:\n{listed}", encoding="utf-8")
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(
        "charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: org-packs/acme\n", encoding="utf-8"
    )


def test_promotion_keeps_an_org_required_id_a_stale_deny_names(tmp_path: Path) -> None:
    """F1 (FR-006/FR-009): a stale deny of an org-required id is inert, so the selection is promoted."""
    from types import SimpleNamespace

    from specify_cli.cli.commands.charter.interview import _promote_interview_selections
    from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

    _git_init(tmp_path)
    _org_pack_project(tmp_path, [_DIRECTIVE_010_STEM])
    seed_activation_ledger(
        tmp_path, mission_type_activations=["software-dev"], activated_directives=[_DIRECTIVE_001_STEM], deactivated_directives=[_DIRECTIVE_010_STEM]
    )
    data = SimpleNamespace(selected_directives=[_DIRECTIVE_010_STEM], selected_tactics=[], selected_paradigms=[])

    warnings, _narrowed = _promote_interview_selections(tmp_path, data)

    assert _DIRECTIVE_010_STEM in read_activation_ledger(tmp_path)["activated_directives"]
    assert not [warning for warning in warnings if warning.startswith("kept deactivated")]


def test_promotion_on_an_unmigrated_project_never_applies_a_legacy_deny_key(tmp_path: Path) -> None:
    """F2 (FR-017, Option B): a hand-written legacy ``deactivated_<kind>`` key is reported, never applied."""
    from types import SimpleNamespace

    from specify_cli.cli.commands.charter.interview import _promote_interview_selections

    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(
        f"mission_type_activations:\n- software-dev\nactivated_directives:\n- {_DIRECTIVE_001_STEM}\ndeactivated_directives:\n- {_DIRECTIVE_010_STEM}\n",
        encoding="utf-8",
    )
    data = SimpleNamespace(selected_directives=[_DIRECTIVE_010_STEM], selected_tactics=[], selected_paradigms=[])

    warnings, _narrowed = _promote_interview_selections(tmp_path, data)

    config = _read_config_yaml(tmp_path)
    assert _DIRECTIVE_010_STEM in config["activated_directives"]
    assert config["deactivated_directives"] == [_DIRECTIVE_010_STEM]  # left on disk, untouched
    assert not activation_ledger_path(tmp_path).exists()
    assert not [warning for warning in warnings if warning.startswith("kept deactivated")]


# --- F7: a promotion that writes the activation ledger restamps the bundle hash (the ledger is hashed, FR-018) ---


def _stamp_manifest(root: Path) -> None:
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, SynthesisManifest, finalize_manifest
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
    from charter.bundle import compute_bundle_content_hash

    charter = root / ".kittify" / "charter"
    charter.mkdir(parents=True, exist_ok=True)
    (charter / "charter.yaml").write_text('schema_version: "2.0.0"\n', encoding="utf-8")
    stamped = finalize_manifest(
        SynthesisManifest(
            created_at="2026-10-21T00:00:00Z",
            run_id="01TESTRUN",
            adapter_id="project-direct-write",
            adapter_version="1",
            synthesizer_version="1",
            manifest_hash="0" * 64,
            built_in_only=False,
            bundle_content_hash=compute_bundle_content_hash(root),
        )
    )
    (root / MANIFEST_PATH).write_text(canonical_yaml(stamped.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")


def _stamp_is_current(root: Path) -> bool:
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, load_yaml
    from charter.bundle import compute_bundle_content_hash

    return bool(load_yaml(root / MANIFEST_PATH).bundle_content_hash == compute_bundle_content_hash(root))


def test_interview_promotion_restamps_the_bundle_hash(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from specify_cli.cli.commands.charter.interview import _promote_interview_selections
    from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_directives=[_DIRECTIVE_001_STEM])
    _stamp_manifest(tmp_path)
    assert _stamp_is_current(tmp_path), "control: the stamp starts current"

    _promote_interview_selections(tmp_path, SimpleNamespace(selected_directives=[_DIRECTIVE_010_STEM], selected_tactics=[], selected_paradigms=[]))

    assert _DIRECTIVE_010_STEM in read_activation_ledger(tmp_path)["activated_directives"]
    assert _stamp_is_current(tmp_path)


def test_org_required_promotion_restamps_the_bundle_hash(tmp_path: Path) -> None:
    from charter.activation.org_charter import OrgCharterPolicy, _promote_org_required_to_config
    from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

    _git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_directives=[_DIRECTIVE_001_STEM])
    _stamp_manifest(tmp_path)

    _promote_org_required_to_config(OrgCharterPolicy(required_directives=[_DIRECTIVE_010_STEM]), tmp_path)

    assert _DIRECTIVE_010_STEM in read_activation_ledger(tmp_path)["activated_directives"]
    assert _stamp_is_current(tmp_path)


# --------------------------------------------------------------------------- #
# The interview and the upgrade promotion resolve the same selection (#6686)
# --------------------------------------------------------------------------- #

_ORG_DIRECTIVE_STEM = "qa-003-no-fake-green"
_ORG_DIRECTIVE_ID = "QA_003"


def _identity_org_pack_project(tmp_path: Path) -> Path:
    """A git project registering the identity org pack, with one present activation list.

    The present list is deliberate: an absent key seeds the whole in-force set
    (which already holds the org artifact), so only a present list can show that
    the selection itself was resolved and appended.
    """
    from tests.charter.org_pack_identity_support import write_identity_org_pack

    _git_init(tmp_path)
    write_identity_org_pack(tmp_path, activated_directives=[_DIRECTIVE_010_STEM])
    return tmp_path


def _stored_directives(repo_root: Path) -> list[str]:
    """The stored ``activated_directives`` list: the activation ledger, else the legacy config.yaml."""
    yaml = YAML(typ="safe")
    for path in (activation_ledger_path(repo_root), repo_root / ".kittify" / "config.yaml"):
        if not path.exists():
            continue
        loaded = yaml.load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("activated_directives"), list):
            return [str(item) for item in loaded["activated_directives"]]
    raise AssertionError(f"no activated_directives list written under {repo_root}")


def test_interview_promotes_an_org_pack_selection_to_the_stem_the_upgrade_stores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#6686: the same org id resolves to the same stem on both writers' paths.

    The upgrade half is the migration test's expectation (the stem, not the
    declared id); this half drives the production CLI entry point.
    """
    from specify_cli.upgrade.migrations.m_4_0_0rc8_promote_interview_selections import PROMOTED_KINDS

    assert ArtifactKind.DIRECTIVE in PROMOTED_KINDS, "control: the kind is promoted by both writers"
    project = _identity_org_pack_project(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(project))
    monkeypatch.chdir(project)

    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal", "--selected-directives", _ORG_DIRECTIVE_ID],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    directives = _stored_directives(project)
    assert _ORG_DIRECTIVE_STEM in directives, directives
    assert _ORG_DIRECTIVE_ID not in directives, directives
    assert f"Could not resolve selected directive id {_ORG_DIRECTIVE_ID!r}" not in result.stdout


def test_interview_still_warns_for_an_id_no_layer_knows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The positive control for the parity test: an unknown id is still reported, not promoted."""
    project = _identity_org_pack_project(tmp_path)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(project))
    monkeypatch.chdir(project)

    result = runner.invoke(
        charter_app,
        ["interview", "--defaults", "--profile", "minimal", "--selected-directives", "999-does-not-exist-anywhere"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout
    assert "Could not resolve selected directive id '999-does-not-exist-anywhere'; skipped." in " ".join(result.stdout.split())
    assert "999-does-not-exist-anywhere" not in _stored_directives(project)
