"""A retired ``governance.doctrine`` key fails closed at every reader (FR-011, #3732, T073).

``GovernanceConfig`` ignores unknown keys, so without the check a legacy
``doctrine:`` selection block would be dropped in silence and its selected
artifacts lost. :func:`charter.activation.sync.require_canonical_governance` is
the one check; each raw ``governance:`` reader calls it. Readers that are
diagnostics degrade instead of crashing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.pack_context import ActiveCharterConfigError
from charter.activation.sync import load_governance_config, require_canonical_governance

pytestmark = pytest.mark.fast

_LEGACY_BODY = "doctrine:\n  selected_directives:\n    - DIRECTIVE_001\n"
_CANONICAL_BODY = "charter:\n  selected_directives:\n    - DIRECTIVE_001\n"


def _write_governance_section(root: Path, governance_body: str) -> Path:
    """Write ``governance_body`` under ``charter.yaml``'s ``governance:`` key at the canonical root."""
    from charter.resolution import resolve_canonical_repo_root

    yaml = YAML()
    root.mkdir(parents=True, exist_ok=True)
    charter_dir = resolve_canonical_repo_root(root) / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    path = charter_dir / "charter.yaml"
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump({"governance": yaml.load(governance_body)}, fh)
    return path


def _assert_names_the_remedy(exc: ActiveCharterConfigError, source: Path) -> None:
    assert exc.code == "ACTIVE_CHARTER_CONFIG_INVALID"
    for needle in (str(source), "governance.doctrine", "spec-kitty upgrade", "docs/migrations/charter-pack-cutover.md"):
        assert needle in exc.body, exc.body


def test_require_canonical_governance_passes_the_canonical_mapping_through(tmp_path: Path) -> None:
    governance = {"charter": {"selected_directives": ["DIRECTIVE_001"]}}

    assert require_canonical_governance(governance, source=tmp_path / "charter.yaml") is governance


def test_require_canonical_governance_refuses_the_retired_key(tmp_path: Path) -> None:
    source = tmp_path / "charter.yaml"

    with pytest.raises(ActiveCharterConfigError) as caught:
        require_canonical_governance({"doctrine": {}, "charter": {}}, source=source)

    _assert_names_the_remedy(caught.value, source)


def test_load_governance_config_fails_closed_on_the_retired_key(tmp_path: Path) -> None:
    path = _write_governance_section(tmp_path, _LEGACY_BODY)

    with pytest.raises(ActiveCharterConfigError) as caught:
        load_governance_config(tmp_path)

    _assert_names_the_remedy(caught.value, path)


def test_load_governance_config_reads_the_canonical_key(tmp_path: Path) -> None:
    _write_governance_section(tmp_path, _CANONICAL_BODY)

    assert load_governance_config(tmp_path).charter.selected_directives == ["DIRECTIVE_001"]


def test_mission_type_override_probe_fails_closed(tmp_path: Path) -> None:
    from charter.activation.mission_type_profiles import _project_has_doctrine_overrides

    _write_governance_section(tmp_path, _LEGACY_BODY)
    with pytest.raises(ActiveCharterConfigError) as caught:
        _project_has_doctrine_overrides(tmp_path)
    assert "spec-kitty upgrade" in caught.value.body

    _write_governance_section(tmp_path, _CANONICAL_BODY)
    assert _project_has_doctrine_overrides(tmp_path) is True


def test_analysis_inputs_declared_paths_fail_closed(tmp_path: Path) -> None:
    from specify_cli.analysis_inputs import _declared_paths

    source = tmp_path / "charter.yaml"
    with pytest.raises(ActiveCharterConfigError) as caught:
        _declared_paths({"governance": {"doctrine": {"authority_paths": ["x.md"]}}}, source=source)
    assert "spec-kitty upgrade" in caught.value.body

    declared = _declared_paths({"governance": {"charter": {"authority_paths": ["x.md"]}}}, source=source)
    assert "x.md" in declared


def test_doctor_reports_the_retired_key_instead_of_dropping_it(tmp_path: Path) -> None:
    """A diagnostic reports, never crashes, never drops silently (T073 step 3, review B2)."""
    from specify_cli.cli.commands._doctrine_collect import _read_project_selections, _run_retired_governance_key_check
    from specify_cli.cli.commands._doctrine_health import DoctrineHealthReport

    path = _write_governance_section(tmp_path, _LEGACY_BODY)
    assert not any(_read_project_selections(tmp_path).values())
    report = DoctrineHealthReport(org_drg={})
    _run_retired_governance_key_check(report, tmp_path)
    finding = report.org_drg["retired_governance_key"]
    assert finding["file"] == str(path) and finding["key"] == "governance.doctrine"
    assert "spec-kitty upgrade" in finding["message"]
    assert report.healthy is False

    _write_governance_section(tmp_path, _CANONICAL_BODY)
    assert _read_project_selections(tmp_path)["directives"] == ["DIRECTIVE_001"]
    clean = DoctrineHealthReport(org_drg={})
    _run_retired_governance_key_check(clean, tmp_path)
    assert "retired_governance_key" not in clean.org_drg


@pytest.mark.parametrize("body", ["governance: [not, a, mapping]\n", "governance: {unclosed\n"], ids=["non-mapping", "malformed"])
def test_retired_key_check_ignores_what_it_cannot_read(tmp_path: Path, body: str) -> None:
    from charter.resolution import resolve_canonical_repo_root
    from specify_cli.cli.commands._doctrine_collect import _run_retired_governance_key_check
    from specify_cli.cli.commands._doctrine_health import DoctrineHealthReport

    charter_dir = resolve_canonical_repo_root(tmp_path) / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.yaml").write_text(body, encoding="utf-8")
    report = DoctrineHealthReport(org_drg={})
    _run_retired_governance_key_check(report, tmp_path)
    assert report.org_drg == {}


def test_active_charter_config_error_shape_is_unchanged() -> None:
    """contracts/errors.md: the shape is unchanged; ``str`` is the code, the remedy is ``.body``."""
    err = ActiveCharterConfigError("fix it")
    assert str(err) == "ACTIVE_CHARTER_CONFIG_INVALID"
    assert (err.code, err.body) == ("ACTIVE_CHARTER_CONFIG_INVALID", "fix it")


# --------------------------------------------------------------------------- #
# Best-effort wrappers: a retired shape propagates, anything else degrades
# --------------------------------------------------------------------------- #


def _retired_field_error() -> Exception:
    from charter.offering.packs.retired_fields import RETIRED_PACK_FIELDS, RetiredPackFieldError

    return RetiredPackFieldError(RETIRED_PACK_FIELDS[0])


def _retired_key_error() -> Exception:
    return ActiveCharterConfigError("governance.doctrine is retired; run `spec-kitty upgrade`")


def _load_governance_raising(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    import charter.activation.sync as sync_module

    def _raise(_root: Path) -> object:
        raise error

    monkeypatch.setattr(sync_module, "load_governance_config", _raise)


@pytest.mark.parametrize("make_error", [_retired_field_error, _retired_key_error], ids=["retired-pack-field", "retired-governance-key"])
def test_governance_activations_let_a_retired_shape_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_error: Callable[[], Exception]) -> None:
    from charter.activation.context_renderers.activation_block import _load_governance_activations

    error = make_error()
    _load_governance_raising(monkeypatch, error)

    with pytest.raises(type(error)):
        _load_governance_activations(tmp_path)


@pytest.mark.parametrize("make_error", [_retired_field_error, _retired_key_error], ids=["retired-pack-field", "retired-governance-key"])
def test_doctrine_selection_lets_a_retired_shape_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_error: Callable[[], Exception]) -> None:
    from charter.activation.org_pack_discovery import _load_governance_charter_config

    error = make_error()
    _load_governance_raising(monkeypatch, error)

    with pytest.raises(type(error)):
        _load_governance_charter_config(tmp_path)


def test_best_effort_loaders_still_degrade_on_other_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation.context_renderers.activation_block import _load_governance_activations
    from charter.activation.org_pack_discovery import _load_governance_charter_config
    from charter.activation.schemas import GovernanceCharterConfig

    _load_governance_raising(monkeypatch, ValueError("malformed governance section"))

    assert _load_governance_activations(tmp_path) == []
    assert _load_governance_charter_config(tmp_path) == GovernanceCharterConfig()
