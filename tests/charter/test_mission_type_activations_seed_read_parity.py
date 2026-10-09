"""Fold for PR #3246 (MINOR-1): unify the ``mission_type_activations`` seed-READ.

``spec-kitty init``/``upgrade``
(:func:`specify_cli.provisioning.default_charter.provision_default_mission_type_activations`)
and ``spec-kitty charter generate``
(:func:`charter.activation.compiler.provision_mission_type_activations`) both seed
``mission_type_activations`` from the same shipped
``src/charter/activation/packs/default.yaml``, but previously read it through two
independent, near-identical stacks with divergent fail-closed behaviour:
one (``specify_cli``) silently accepted an authored-empty list, the other
(``charter.activation.compiler``) already raised.

Both now consume the single, fail-closed
:func:`charter.activation.default_pack.load_default_mission_type_activations`. This
suite pins:

* both provisioners seed the IDENTICAL set from the real shipped
  ``default.yaml`` (the parity the shared read now guarantees);
* a malformed/absent default pack fails closed on BOTH write paths, each
  still surfacing its own historical exception type
  (``DefaultCharterPackMissingError`` for ``specify_cli``,
  ``ActiveCharterConfigError`` for ``charter.activation.compiler``).

Write-side behaviour (which config file, additive-only, idempotence,
authored-``[]``-preserved) is unchanged and already covered by
``tests/specify_cli/cli/commands/test_init_provisioning.py`` and
``tests/charter/test_mission_type_activation_emit.py``; this file is scoped
to the shared read.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

import charter.activation.default_pack as default_pack_module
from charter.activation.compiler import provision_mission_type_activations
from charter.activation.default_pack import load_default_mission_type_activations
from charter.activation.pack_context import ActiveCharterConfigError
from specify_cli.provisioning import default_charter
from specify_cli.provisioning.default_charter import (
    DefaultCharterPackMissingError,
    provision_default_mission_type_activations,
)

pytestmark = [pytest.mark.fast]

_SAFE_YAML = YAML(typ="safe")


def _load_config(config_file: Path) -> dict:
    return _SAFE_YAML.load(config_file) or {}


# ---------------------------------------------------------------------------
# Parity: both provisioners seed the identical set from the real default.yaml
# ---------------------------------------------------------------------------


def test_both_provisioners_seed_identical_set_from_real_default_pack(
    tmp_path: Path,
) -> None:
    """init/upgrade and charter-generate write the SAME activation list."""
    init_project = tmp_path / "init-project"
    assert provision_default_mission_type_activations(init_project) is True
    init_config = _load_config(init_project / ".kittify" / "config.yaml")

    gen_project = tmp_path / "gen-project"
    kittify = gen_project / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")
    assert provision_mission_type_activations(gen_project) is True
    gen_config = _load_config(kittify / "config.yaml")

    shared = load_default_mission_type_activations()

    assert init_config["mission_type_activations"] == shared
    assert gen_config["mission_type_activations"] == shared
    assert init_config["mission_type_activations"] == gen_config["mission_type_activations"]
    assert shared  # non-empty: a real fixture-free regression would be silent otherwise


# ---------------------------------------------------------------------------
# Fail-closed: a malformed/absent default pack blocks BOTH provisioners
# ---------------------------------------------------------------------------


def test_shared_helper_fails_closed_on_missing_default_pack(tmp_path: Path) -> None:
    missing_root = tmp_path / "no-such-charter-pkg"

    with pytest.raises(ActiveCharterConfigError):
        load_default_mission_type_activations(pack_path=missing_root / "default.yaml")


def test_shared_helper_fails_closed_on_pack_without_mission_type_key(
    tmp_path: Path,
) -> None:
    broken_pack = tmp_path / "broken-default.yaml"
    broken_pack.write_text("activated_kinds: []\n", encoding="utf-8")

    with pytest.raises(ActiveCharterConfigError):
        load_default_mission_type_activations(pack_path=broken_pack)


def test_shared_helper_fails_closed_on_authored_empty_list_in_shipped_pack(
    tmp_path: Path,
) -> None:
    """An empty list in the SHIPPED default.yaml is a broken-install signal.

    Distinct from an authored ``[]`` in a *project's* own config.yaml /
    charter.yaml (a legitimate zero-types opt-out preserved verbatim by both
    write paths) -- this is the shipped source-of-truth file itself, so an
    empty list there can never be provisioned from.
    """
    empty_pack = tmp_path / "empty-default.yaml"
    empty_pack.write_text("mission_type_activations: []\n", encoding="utf-8")

    with pytest.raises(ActiveCharterConfigError):
        load_default_mission_type_activations(pack_path=empty_pack)


def test_charter_generate_path_fails_closed_on_broken_default_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``charter.activation.compiler.provision_mission_type_activations`` fails closed too."""
    broken_pack = tmp_path / "broken-default.yaml"
    broken_pack.write_text("activated_kinds: []\n", encoding="utf-8")
    monkeypatch.setattr(
        default_pack_module, "_default_pack_yaml_path", lambda root: broken_pack
    )

    project = tmp_path / "project"
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text("vcs:\n  type: git\n", encoding="utf-8")

    with pytest.raises(ActiveCharterConfigError):
        provision_mission_type_activations(project)

    # Fail-closed means untouched: no partial/garbage key written.
    assert "mission_type_activations" not in _load_config(kittify / "config.yaml")


def test_init_upgrade_path_fails_closed_on_broken_default_pack_via_shared_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``specify_cli`` provisioning fails closed through the SAME shared reader.

    Regression guard for the divergence this fold closes: before, an
    authored-empty ``mission_type_activations: []`` in the shipped pack was
    silently ACCEPTED by this path (isinstance-list-only check) while
    ``charter.activation.compiler``'s already raised. Both must now raise identically.
    """
    empty_pack = tmp_path / "empty-default.yaml"
    empty_pack.write_text("mission_type_activations: []\n", encoding="utf-8")
    monkeypatch.setattr(default_charter, "resolve_builtin_pack_path", lambda name: empty_pack)

    project = tmp_path / "project"

    with pytest.raises(DefaultCharterPackMissingError):
        provision_default_mission_type_activations(project)

    assert not (project / ".kittify" / "config.yaml").exists()
