"""Self-mutation tests for the owned-checkout single-authority gate (T005, DIRECTIVE_043).

Non-vacuity evidence for SC-004: every rule G1-G6 of
``contracts/architectural-gate.md`` must flag its synthetic offender and pass
a clean synthetic source. These tests **never** scan the live ``src/`` tree
for offenders -- the tree is full of offenders until WP18 (see the WP01
prompt's Context & Constraints: "Gate floors on the live tree are forbidden
in this WP"). The live-tree floors are the closing WP's red-first first
commit.
"""

from __future__ import annotations

import ast

import pytest

from tests.architectural._ast_scan import UnparseableSourceError, parse_source
from tests.architectural._owned_checkout_scan import (
    bare_owned_root_paths,
    claim_references,
    effective_root_identifiers,
    mint_references,
    owned_signature_pins,
    validator_calls,
)

pytestmark = pytest.mark.architectural


def _parse(src: str, name: str = "case.py") -> ast.Module:
    return parse_source(src, display=f"synthetic/{name}")


# ---------------------------------------------------------------------------
# G1 -- claim-primitive references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("src", "expected_detail_substr"),
    [
        pytest.param(
            "resolve_ownership_claim(p, resolved_primary=r)\n",
            "resolve_ownership_claim",
            id="g1-stray-call",
        ),
        pytest.param(
            "from specify_cli.core.checkout_ownership import resolve_ownership_claim as r\n",
            "import resolve_ownership_claim",
            id="g1-import-alias",
        ),
        pytest.param(
            "mod.resolve_ownership_claim(p)\n",
            "attribute",
            id="g1-attribute-access",
        ),
        pytest.param(
            'getattr(mod, "resolve_ownership_claim")\n',
            "dynamic lookup",
            id="g1-getattr-string-constant",
        ),
    ],
)
def test_g1_flags_every_claim_reference_form(src: str, expected_detail_substr: str) -> None:
    tree = _parse(src)
    offenders = claim_references(tree, "src/fake.py")
    assert len(offenders) == 1
    assert offenders[0].rule == "G1"
    assert expected_detail_substr in offenders[0].detail


def test_g1_import_alias_reports_the_import_statement_lineno() -> None:
    src = "from specify_cli.core.checkout_ownership import (\n    resolve_ownership_claim as r,\n)\n"
    tree = _parse(src)
    offenders = claim_references(tree, "src/fake.py")
    assert len(offenders) == 1
    assert offenders[0].lineno == 2


def test_g1_negative_docstring_mention_is_not_flagged() -> None:
    src = '"""Mentions resolve_ownership_claim in prose only."""\n'
    tree = _parse(src)
    assert claim_references(tree, "src/fake.py") == []


# ---------------------------------------------------------------------------
# G2 -- validator-call site
# ---------------------------------------------------------------------------


def test_g2_flags_resolve_owned_mission_call_outside_allowed_module() -> None:
    src = "resolve_owned_mission(r, p, h)\n"
    tree = _parse(src)
    offenders = validator_calls(tree, "src/specify_cli/cli/commands/status.py")
    assert len(offenders) == 1
    assert offenders[0].rule == "G2"


def test_g2_flags_adopt_owned_checkout_call() -> None:
    src = "adopt_owned_checkout(r, cwd, h, allowed_topologies=x)\n"
    tree = _parse(src)
    offenders = validator_calls(tree, "src/specify_cli/cli/commands/status.py")
    assert len(offenders) == 1


def test_g2_flags_import_alias_call() -> None:
    src = "from specify_cli.core.owned_mission import resolve_owned_mission as rom\nrom(r, p, h)\n"
    tree = _parse(src)
    offenders = validator_calls(tree, "src/specify_cli/cli/commands/status.py")
    assert len(offenders) == 1
    assert offenders[0].rule == "G2"


def test_g2_flags_dynamic_getattr_lookup() -> None:
    src = 'getattr(mod, "resolve_owned_mission")\n'
    tree = _parse(src)
    offenders = validator_calls(tree, "src/specify_cli/cli/commands/status.py")
    assert len(offenders) == 1


def test_g2_negative_unrelated_call_is_not_flagged() -> None:
    src = "resolve_owned_mission_something_else(r)\n"
    tree = _parse(src)
    assert validator_calls(tree, "src/fake.py") == []


# ---------------------------------------------------------------------------
# G3 -- mint-site reference
# ---------------------------------------------------------------------------


def test_g3_flags_direct_mint_reference_outside_minter() -> None:
    src = "OwnedCheckout._mint(repository_root=r, owned_root=o)\n"
    tree = _parse(src)
    offenders = mint_references(tree, "src/specify_cli/core/fake.py")
    assert len(offenders) == 1
    assert offenders[0].rule == "G3"


def test_g3_flags_mint_reference_via_import_alias() -> None:
    src = "from mission_runtime import OwnedCheckout as OC\nOC._mint(repository_root=r)\n"
    tree = _parse(src)
    offenders = mint_references(tree, "src/specify_cli/core/fake.py")
    assert len(offenders) == 1
    assert offenders[0].lineno == 2


def test_g3_flags_mint_reference_via_package_root_attribute_chain() -> None:
    """``mission_runtime.OwnedCheckout._mint(...)`` -- the spelling MR-1/MR-2 force."""
    src = "import mission_runtime\nmission_runtime.OwnedCheckout._mint(repository_root=r)\n"
    tree = _parse(src)
    offenders = mint_references(tree, "src/specify_cli/core/fake.py")
    assert len(offenders) == 1
    assert offenders[0].lineno == 2


def test_g3_flags_dynamic_getattr_mint_lookup() -> None:
    src = 'getattr(OwnedCheckout, "_mint")\n'
    tree = _parse(src)
    offenders = mint_references(tree, "src/specify_cli/core/fake.py")
    assert len(offenders) == 1


def test_g3_negative_unrelated_mint_attribute_is_not_flagged() -> None:
    src = "SomeOtherThing._mint(x)\n"
    tree = _parse(src)
    assert mint_references(tree, "src/fake.py") == []


# ---------------------------------------------------------------------------
# G4 -- effective_root identifier ban
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        pytest.param('def f(effective_root: "Path | None" = None): ...\n', id="g4-string-annotation-param"),
        pytest.param("from typing import Optional\ndef f(effective_root: Optional[Path]): ...\n", id="g4-optional-param"),
        pytest.param(
            "class T(TypedDict, total=False):\n    effective_root: Path\n",
            id="g4-typeddict-key",
        ),
        pytest.param('f(**{"effective_root": x})\n', id="g4-splat-string-key"),
    ],
)
def test_g4_flags_every_effective_root_form(src: str) -> None:
    tree = _parse(src)
    offenders = effective_root_identifiers(tree, "src/fake.py")
    assert len(offenders) >= 1
    assert all(o.rule == "G4" for o in offenders)


@pytest.mark.parametrize(
    "src",
    [
        pytest.param('def f(effective_root: "Path | None" = None): ...\n', id="g5-string-annotation-param"),
        pytest.param("from typing import Optional\ndef f(effective_root: Optional[Path]): ...\n", id="g5-optional-param"),
    ],
)
def test_g4_and_g5_both_flag_the_same_bare_path_effective_root_param(src: str) -> None:
    """T005 lists these two forms as "G4 and G5" (a `Path`-typed `effective_root` param is both shapes)."""
    tree = _parse(src)
    assert effective_root_identifiers(tree, "src/fake.py") != []
    assert bare_owned_root_paths(tree, "src/fake.py") != []


def test_g4_flags_walrus_target_but_not_the_org_pack_method_call() -> None:
    src = "x = 1\n(effective_root := pack.effective_root(repo_root))\n"
    tree = _parse(src)
    offenders = effective_root_identifiers(tree, "src/specify_cli/charter_runtime/lint/checks/org_layer.py")
    assert [o.detail for o in offenders] == ["identifier effective_root"]
    assert offenders[0].lineno == 2


def test_g4_typeddict_key_reports_the_field_lineno() -> None:
    src = "class T(TypedDict, total=False):\n    x: int\n    effective_root: Path\n"
    tree = _parse(src)
    offenders = effective_root_identifiers(tree, "src/fake.py")
    assert len(offenders) == 1
    assert offenders[0].lineno == 3


def test_g4_negative_docstring_mention_is_not_flagged() -> None:
    src = '"""This module never reads effective_root directly."""\n'
    tree = _parse(src)
    assert effective_root_identifiers(tree, "src/fake.py") == []


@pytest.mark.parametrize(
    "src",
    [
        pytest.param('"""effective_root"""\n', id="g4-exact-string-docstring-module"),
        pytest.param('class C:\n    """effective_root"""\n', id="g4-exact-string-docstring-class"),
        pytest.param('def f():\n    """effective_root"""\n', id="g4-exact-string-docstring-function"),
    ],
)
def test_g4_negative_exact_string_docstring_discriminates_the_skip(src: str) -> None:
    """The mutation-sanity control: a docstring that IS exactly ``"effective_root"`` is the shape that would
    be flagged if the docstring-``Constant`` skip were removed (``ast.walk`` yields it too, not just the
    wrapping ``Expr``) -- unlike a prose mention, which is never `==` the bare identifier either way.
    """
    tree = _parse(src)
    assert effective_root_identifiers(tree, "src/fake.py") == []


def test_g4_negative_called_org_pack_method_is_not_flagged() -> None:
    src = "pack.effective_root(repo_root)\n"
    tree = _parse(src)
    assert effective_root_identifiers(tree, "src/fake.py") == []


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/charter/offering/pack.py",
        "src/specify_cli/cli/commands/_doctrine_collect.py",
        "src/specify_cli/analysis_inputs.py",
    ],
)
def test_g4_negative_org_pack_module_rule_exempts_effective_root_param(rel_path: str) -> None:
    src = "def f(effective_root: Path | None = None): ...\n"
    tree = _parse(src)
    assert effective_root_identifiers(tree, rel_path) == []
    # ORG_PACK_MODULE_RULE takes the covered paths out of BOTH G4 and G5
    # scope (contracts/architectural-gate.md); the same parameter is also a
    # G5 shape (a bare-Path `effective_root`), so it must be empty there too.
    assert bare_owned_root_paths(tree, rel_path) == []


def test_g4_org_layer_module_itself_is_not_exempted() -> None:
    """The module ``org_layer.py`` is explicitly NOT covered by ORG_PACK_MODULE_RULE."""
    src = "def f(effective_root: Path | None = None): ...\n"
    tree = _parse(src)
    offenders = effective_root_identifiers(tree, "src/specify_cli/charter_runtime/lint/checks/org_layer.py")
    assert len(offenders) == 1


# ---------------------------------------------------------------------------
# G5 -- bare owned-root Path parameters/fields
# ---------------------------------------------------------------------------


def test_g5_flags_renamed_checkout_root_parameter() -> None:
    src = "def f(checkout_root: Path | None): ...\n"
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/fake.py")
    assert len(offenders) == 1
    assert offenders[0].rule == "G5"


def test_g5_flags_second_class_owned_root_field() -> None:
    src = "class Other:\n    owned_root: Path\n"
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/fake.py")
    assert len(offenders) == 1


def test_g5_flags_typer_option_owned_checkout_parameter() -> None:
    src = 'def cmd(owned_checkout: Annotated[Path | None, typer.Option("--owned-checkout")] = None): ...\n'
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/specify_cli/cli/commands/fake.py")
    assert len(offenders) == 1


def test_g5_negative_owned_checkout_option_alias_is_not_flagged() -> None:
    src = "def cmd(owned_checkout: OwnedCheckoutOption = None): ...\n"
    tree = _parse(src)
    assert bare_owned_root_paths(tree, "src/specify_cli/cli/commands/fake.py") == []


def test_g5_negative_qualified_owned_checkout_option_alias_is_not_flagged() -> None:
    """The ``_owned_checkout.``-qualified spelling is recognised too, not only the bare name."""
    src = "def cmd(owned_checkout: _owned_checkout.OwnedCheckoutOption = None): ...\n"
    tree = _parse(src)
    assert bare_owned_root_paths(tree, "src/specify_cli/cli/commands/fake.py") == []


def test_g5_negative_owned_checkout_option_helper_form_is_not_flagged() -> None:
    src = 'def cmd(owned_checkout: Annotated[Path | None, owned_checkout_option(help="x")] = None): ...\n'
    tree = _parse(src)
    assert bare_owned_root_paths(tree, "src/specify_cli/cli/commands/fake.py") == []


def test_g5_flags_checkout_root_outside_migrations() -> None:
    src = "def f(checkout_root: Path | None): ...\n"
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/specify_cli/core/fake.py")
    assert len(offenders) == 1


def test_g5_negative_checkout_root_under_migrations_is_not_flagged() -> None:
    src = "def f(checkout_root: Path | None): ...\n"
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/specify_cli/upgrade/migrations/m_1_2_3.py")
    assert offenders == []


def test_g5_negative_carrier_fields_under_the_defining_module_are_not_flagged() -> None:
    src = "class OwnedCheckout:\n    owned_root: Path\n    repository_root: Path\n"
    tree = _parse(src)
    assert bare_owned_root_paths(tree, "src/mission_runtime/owned_checkout.py") == []


def test_g5_carrier_exemption_does_not_leak_to_other_paths() -> None:
    """The exact same class body, at a different module path, IS flagged (exemption is by FQN)."""
    src = "class OwnedCheckout:\n    owned_root: Path\n"
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/specify_cli/core/fake.py")
    assert len(offenders) == 1


_MINT_DOOR_SRC = "class OwnedCheckout:\n    @classmethod\n    def _mint(cls, *, owned_root: Path, repository_root: Path): ...\n"


def test_g5_negative_carrier_mint_door_parameters_are_not_flagged() -> None:
    """``OwnedCheckout._mint`` populates the exempt fields; its keyword parameters are those fields."""
    tree = _parse(_MINT_DOOR_SRC)
    assert bare_owned_root_paths(tree, "src/mission_runtime/owned_checkout.py") == []


def test_g5_carrier_mint_door_exemption_does_not_leak_to_other_paths() -> None:
    """The same ``_mint`` at a different module path IS flagged (exemption is by FQN)."""
    tree = _parse(_MINT_DOOR_SRC)
    assert len(bare_owned_root_paths(tree, "src/specify_cli/core/fake.py")) == 1


def test_g5_carrier_mint_exemption_covers_only_the_mint_door() -> None:
    """Another method of the carrier class in the carrier module is still scanned."""
    src = "class OwnedCheckout:\n    def other(self, owned_root: Path): ...\n"
    tree = _parse(src)
    assert len(bare_owned_root_paths(tree, "src/mission_runtime/owned_checkout.py")) == 1


def test_g5_carrier_mint_exemption_does_not_cover_another_class() -> None:
    """A ``_mint`` on a different class in the carrier module is still scanned."""
    src = "class Other:\n    def _mint(self, owned_root: Path): ...\n"
    tree = _parse(src)
    assert len(bare_owned_root_paths(tree, "src/mission_runtime/owned_checkout.py")) == 1


def test_g5_negative_clean_module_using_owned_checkout_fact() -> None:
    src = "def f(owned: OwnedCheckout | None = None): ...\n"
    tree = _parse(src)
    assert bare_owned_root_paths(tree, "src/fake.py") == []


# ---------------------------------------------------------------------------
# G6 -- positive signature pin
# ---------------------------------------------------------------------------


def test_g6_flags_missing_pin_on_required_consumer() -> None:
    src = "def placement_seam(repo_root, mission_slug): ...\n"
    tree = _parse(src)
    offenders = owned_signature_pins(tree, "src/fake.py", {"placement_seam": "contracts §7"})
    assert len(offenders) == 1
    assert offenders[0].rule == "G6"


def test_g6_negative_hit_when_pin_present() -> None:
    src = "def placement_seam(repo_root, mission_slug, *, owned: OwnedCheckout | None = None): ...\n"
    tree = _parse(src)
    offenders = owned_signature_pins(tree, "src/fake.py", {"placement_seam": "contracts §7"})
    assert offenders == []


def test_g6_requires_none_form_not_just_owned_checkout_alone() -> None:
    src = "def placement_seam(repo_root, mission_slug, *, owned: OwnedCheckout): ...\n"
    tree = _parse(src)
    offenders = owned_signature_pins(tree, "src/fake.py", {"placement_seam": "contracts §7"})
    assert len(offenders) == 1


def test_g6_negative_absent_name_is_not_reported() -> None:
    """A required consumer that does not appear in this synthetic source is silently skipped."""
    tree = _parse("x = 1\n")
    offenders = owned_signature_pins(tree, "src/fake.py", {"placement_seam": "contracts §7"})
    assert offenders == []


# ---------------------------------------------------------------------------
# Fail-closed parsing
# ---------------------------------------------------------------------------


def test_unparseable_synthetic_source_raises() -> None:
    with pytest.raises(UnparseableSourceError):
        parse_source("def f(:\n", display="synthetic/broken.py")


# ---------------------------------------------------------------------------
# _is_bare_path_annotation spelling table (T004 helper, T005's ≥12-spelling requirement)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "src",
    [
        "def f(owned_root: Path): ...\n",
        "def f(owned_root: pathlib.Path): ...\n",
        "def f(owned_root: Path | None): ...\n",
        "def f(owned_root: None | Path): ...\n",
        "def f(owned_root: Optional[Path]): ...\n",
        "def f(owned_root: Union[Path, None]): ...\n",
        "def f(owned_root: os.PathLike): ...\n",
        "def f(owned_root: os.PathLike[str]): ...\n",
        'def f(owned_root: "Path"): ...\n',
        'def f(owned_root: "Path | None"): ...\n',
        'def f(owned_root: "Optional[Path]"): ...\n',
        "def f(owned_root: Annotated[Path, x]): ...\n",
        "def f(owned_root: Annotated[Path | None, x]): ...\n",
    ],
)
def test_bare_path_annotation_spelling_table(src: str) -> None:
    tree = _parse(src)
    offenders = bare_owned_root_paths(tree, "src/fake.py")
    assert len(offenders) == 1, src
