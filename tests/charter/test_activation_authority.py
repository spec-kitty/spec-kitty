"""WP07 (IC-05) — activation authority, absence semantics, fail-closed delivery.

These tests pin the three FR-017/FR-018/FR-012 guarantees for the single
activation authority:

* **SC-007 (T039)** — a *divergent-mirror* fixture where ``.kittify/config.yaml``
  and the pointed-at ``charter.yaml`` **disagree** on the activated set. This is
  the only case that proves which store won: a no-op that still read the
  config-embedded mirror would return the config value and fail here.
* **FR-018 (T038)** — a project whose resolved activation store *omits* an
  ``activated_<kind>`` key delivers **nothing** for that kind at the compiler
  delivery boundary — absence is not "all built-ins".
* **FR-012 error half / NFR-006 (T040)** — an activation-resolution error
  *propagates* through the runtime prompt builder rather than degrading into a
  silent legacy render.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.compiler import resolve_config_activated_roots
from charter.activation.pack_context import ActiveCharterConfigError, charter_activated_urns


pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(content, encoding="utf-8")


def _write_charter_yaml(tmp_path: Path, content: str) -> Path:
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.yaml"
    charter_path.write_text(content, encoding="utf-8")
    return charter_path


_POINTER_CONFIG_WITH_MIRROR = """\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
activated_tactics:
  - config-only-tactic
"""


def _charter_yaml(activated_tactics: str) -> str:
    return f"""\
schema_version: "2.0.0"
governance:
  testing: {{}}
directives: []
catalog: {{}}
{activated_tactics}metadata:
  bundle_schema_version: 2
"""


# ---------------------------------------------------------------------------
# T039 / SC-007 — divergent-mirror: the charter wins
# ---------------------------------------------------------------------------


def test_divergent_mirror_charter_wins(tmp_path: Path) -> None:
    """config.yaml and charter.yaml disagree -> charter.yaml is authoritative.

    SC-007: the ONLY case that proves which store won. ``config.yaml`` still
    carries an ``activated_tactics`` mirror (``config-only-tactic``); the
    pointed-at ``charter.yaml`` activates a DIFFERENT tactic
    (``charter-only-tactic``). The single authority must resolve to the
    charter's set and never the config mirror.
    """
    _write_config(tmp_path, _POINTER_CONFIG_WITH_MIRROR)
    _write_charter_yaml(
        tmp_path,
        _charter_yaml("activated_tactics:\n  - charter-only-tactic\n"),
    )

    urns = charter_activated_urns(tmp_path)

    assert urns == {"tactic:charter-only-tactic"}
    assert "tactic:config-only-tactic" not in urns


# ---------------------------------------------------------------------------
# T038 / FR-018 — absence resolves to empty at the compiler delivery boundary
# ---------------------------------------------------------------------------


_POINTER_CONFIG = """\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
"""

_CHARTER_YAML_OMITS_PARADIGMS = """\
schema_version: "2.0.0"
governance:
  testing: {}
directives: []
catalog: {}
activated_directives:
  - 010-specification-fidelity-requirement
mission_type_activations:
  - software-dev
metadata:
  bundle_schema_version: 2
"""


def test_absent_activated_key_delivers_empty_not_all_builtins(tmp_path: Path) -> None:
    """FR-018: a migrated project that OMITS an activated_<kind> key delivers
    nothing for that kind — absence is not "all built-ins".

    The charter activates a directive but carries no ``activated_paradigms``
    key at all. At the compiler delivery boundary (``resolve_config_activated_roots``)
    the omitted key must resolve to ``[]``, not to every built-in paradigm.
    """
    _write_config(tmp_path, _POINTER_CONFIG)
    _write_charter_yaml(tmp_path, _CHARTER_YAML_OMITS_PARADIGMS)

    roots = resolve_config_activated_roots(repo_root=tmp_path)

    # The activated directive still resolves (delivery is real, not blanket-empty).
    assert roots.directives == ["DIRECTIVE_010"]
    # The omitted key delivers nothing — the FR-018 retirement of "absence => all".
    assert roots.paradigms == []


def test_wholly_unconfigured_project_keeps_builtins_convenience(tmp_path: Path) -> None:
    """FR-018 boundary: absence-is-empty applies to CONFIGURED projects only.

    A project with no ``.kittify/config.yaml`` at all (a scaffold that activates
    nothing) is not a per-project delivery boundary — it keeps the all-built-ins
    convenience default so a fresh project still resolves shipped doctrine. Only
    a project that activates *some* kind but omits another delivers empty for the
    omitted kind (see the test above).

    ``mission_type_activations`` is the one exception (WP04, C-A1): it has no
    "absence => all" convenience default under ANY circumstance, "wholly
    unconfigured" included, and its absence is now a hard construction
    precondition rather than a per-kind delivery signal. A minimal config.yaml
    naming it is provisioned below so ``PackContext.from_config`` can build at
    all; every OTHER activation key (``activated_paradigms``/``activated_directives``
    among them) stays genuinely absent, so the "wholly unconfigured w.r.t.
    paradigms/directives" scenario this test actually pins is unchanged.
    """
    from charter.activation.catalog import load_offering_catalog

    # No activated_* keys written -> wholly unconfigured w.r.t. paradigms/
    # directives (the FR-018 boundary under test). Only mission_type_activations
    # is provisioned, for the orthogonal WP04 construction precondition.
    _write_config(tmp_path, "mission_type_activations:\n  - software-dev\n")
    roots = resolve_config_activated_roots(repo_root=tmp_path)

    catalog = load_offering_catalog()
    assert sorted(roots.paradigms) == sorted(catalog.paradigms)
    assert roots.directives  # non-empty: built-ins still delivered


# ---------------------------------------------------------------------------
# T040 / FR-012 error half / NFR-006 — fail-closed: activation errors propagate
# ---------------------------------------------------------------------------


_DANGLING_POINTER_CONFIG = """\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
"""


def test_activation_error_propagates_to_operator_governance(tmp_path: Path) -> None:
    """FR-012 error half / NFR-006: an activation-resolution failure PROPAGATES.

    The config ``charter:`` pointer names a ``charter.yaml`` that does not exist
    (a dangling pointer). Resolving activation raises the typed, named
    :class:`ActiveCharterConfigError`. The runtime prompt builder's governance
    seam MUST let that error reach the operator, not swallow it into a degraded
    ``Governance: unavailable (...)`` legacy render (the retired
    ``except Exception: pass`` behavior).
    """
    from runtime.next.prompt_builder import _governance_context

    _write_config(tmp_path, _DANGLING_POINTER_CONFIG)
    # A charter.md is present so context building proceeds past the
    # "charter file not found" short-circuit and actually resolves activation...
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")
    # ...but the 'charter:' pointer names a charter.yaml that does NOT exist ->
    # activation resolution raises ActiveCharterConfigError.

    with pytest.raises(ActiveCharterConfigError):
        _governance_context(tmp_path, action="specify")
