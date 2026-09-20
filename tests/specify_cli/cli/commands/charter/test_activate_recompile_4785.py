"""Red-first regression: `charter activate`/`deactivate` leave the compiled
catalog stale (issue #4785 Finding 1, WP03 T011).

Contract C1 (contracts/behavior-contracts.md): activating a built-in
directive absent from an established charter store's compiled catalog must
leave ``tests/doctrine/test_activation_parity_guard.py::
test_this_project_charter_pack_is_coherent``-shaped coherence GREEN by
default, with no manual edit -- `activate_cmd` recompiles
``catalog.references`` via the single compiler authority
(``compile_charter(..., from_interview=False)``) after every activation
unless ``--no-compile`` is passed. `deactivate_cmd` is symmetric (FR-002).

Before this fix, `activate`/`deactivate` were config-only writes (the
`--resynthesize` opt-in was the only recompile path), so this repro was RED
through the pre-existing entry point: the CLI wrote
``activated_directives: [<stem>]`` into ``config.yaml`` but left the
established ``charter.yaml`` catalog untouched, tripping the forward
ID-level parity check (the #2524 dangler class) the exact same way
``tests/doctrine/test_activation_parity_guard.py::
test_config_directive_absent_from_references_bites`` pins directly against
``run_consistency_check``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML
from typer.testing import CliRunner

from charter.activation.consistency_check import run_consistency_check
from charter.activation.invocation_context import ProjectContext
from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.regression, pytest.mark.integration]

# The same stable built-in directive `tests/doctrine/test_activation_parity_guard.py`
# uses: canonical id (`DIRECTIVE_001`) differs from its config stem, exercising
# the real stem<->canonical-id normalization the guard depends on.
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"


def _write_config(project_root: Path, content: str = "# empty config\n") -> Path:
    """Write a minimal .kittify/config.yaml; return .kittify/."""
    kittify = project_root / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")
    return kittify


def _write_established_catalog(kittify: Path) -> None:
    """Write a pre-existing, empty compiled catalog under .kittify/charter/charter.yaml.

    This is the "established charter store" baseline Contract C1 requires --
    a genuinely ABSENT charter.yaml short-circuits the guard's parity check
    as "not yet synthesized" (a legitimate no-op skip), which would make
    this repro vacuous. Mirrors
    ``tests/doctrine/test_activation_parity_guard.py::_write_charter_yaml_catalog``.
    """
    charter_dir = kittify / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0.0",
        "governance": {},
        "directives": {},
        "catalog": {
            "mission": "software-dev",
            "template_set": "software-dev-default",
            "languages": ["python"],
            "references": [],
        },
    }
    yaml = YAML()
    yaml.default_flow_style = False
    with (charter_dir / "charter.yaml").open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def _activate(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _deactivate(project_root: Path, *args: str) -> object:
    return runner.invoke(
        charter_app,
        ["deactivate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


def _coherent(project_root: Path) -> bool:
    ctx = ProjectContext.from_repo(project_root)
    report = run_consistency_check(ctx)
    return report.coherent


# ---------------------------------------------------------------------------
# T011/T012/T016 -- activate recompiles by default (FR-001)
# ---------------------------------------------------------------------------


def test_activate_default_recompiles_catalog_and_stays_coherent(tmp_path: Path) -> None:
    """Contract C1: default `activate` (no flags) recompiles catalog.references."""
    kittify = _write_config(tmp_path)
    _write_established_catalog(kittify)

    result = _activate(tmp_path, "directive", _REAL_DIRECTIVE_STEM)

    assert result.exit_code == 0, result.output
    assert _coherent(tmp_path), "activating a directive must recompile catalog.references by default so the coherence guard stays green with no manual edit"


def test_activate_no_compile_stays_config_only_and_prints_notice(tmp_path: Path) -> None:
    """Contract C1: `--no-compile` is the explicit opt-out -- config-only
    write, an explicit notice, and the catalog is left stale."""
    kittify = _write_config(tmp_path)
    _write_established_catalog(kittify)

    result = _activate(tmp_path, "directive", _REAL_DIRECTIVE_STEM, "--no-compile")

    assert result.exit_code == 0, result.output
    assert "not recompiled" in result.output.lower(), result.output
    assert not _coherent(tmp_path), (
        "--no-compile must skip the recompile -- catalog.references stays "
        "stale, proving the default-path assertion above is a real "
        "behavior change and not environment noise"
    )


# ---------------------------------------------------------------------------
# T013/T016 -- deactivate is symmetric (FR-002)
# ---------------------------------------------------------------------------


def test_activate_deactivate_round_trip_stays_coherent(tmp_path: Path) -> None:
    """Contract C1: `deactivate` symmetrically recompiles and keeps the
    guard green after removing the entry."""
    kittify = _write_config(tmp_path)
    _write_established_catalog(kittify)

    activated = _activate(tmp_path, "directive", _REAL_DIRECTIVE_STEM)
    assert activated.exit_code == 0, activated.output
    assert _coherent(tmp_path)

    deactivated = _deactivate(tmp_path, "directive", _REAL_DIRECTIVE_STEM)
    assert deactivated.exit_code == 0, deactivated.output
    assert _coherent(tmp_path)


def _catalog_reference_ids(project_root: Path) -> set[str]:
    """Return the set of ``catalog.references[*].id`` values in charter.yaml.

    A structural read (not the coherence guard): the guard's reverse
    (catalog -> config) orphan check is deliberately scoped to paradigms
    only (see ``consistency_check._check_reference_id_parity``'s
    docstring -- directives are DRG-transitively expanded, so a stale
    directive catalog entry left behind by a config-only deactivate is NOT
    something the guard's directive-kind check catches, by design). This
    helper asserts the actual, observable staleness directly instead.
    """
    yaml = YAML(typ="safe")
    loaded = yaml.load((project_root / ".kittify" / "charter" / "charter.yaml").read_text(encoding="utf-8"))
    return {ref["id"] for ref in loaded["catalog"]["references"]}


def test_deactivate_no_compile_stays_config_only_and_prints_notice(tmp_path: Path) -> None:
    """Sibling of the activate-side --no-compile case: deactivate's own
    opt-out must be independently real, not inherited by accident."""
    kittify = _write_config(tmp_path)
    _write_established_catalog(kittify)

    activated = _activate(tmp_path, "directive", _REAL_DIRECTIVE_STEM)
    assert activated.exit_code == 0, activated.output
    assert _coherent(tmp_path)
    assert "DIRECTIVE:DIRECTIVE_001" in _catalog_reference_ids(tmp_path)

    deactivated = _deactivate(tmp_path, "directive", _REAL_DIRECTIVE_STEM, "--no-compile")

    assert deactivated.exit_code == 0, deactivated.output
    assert "not recompiled" in deactivated.output.lower(), deactivated.output
    assert "DIRECTIVE:DIRECTIVE_001" in _catalog_reference_ids(tmp_path), (
        "--no-compile must skip deactivate's recompile -- the catalog must still carry the now-deactivated entry, unchanged"
    )
