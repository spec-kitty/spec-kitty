"""Golden-text ratchet for ``charter activate`` / ``charter deactivate`` (mission charter-cli-typed-errors-json, T001).

Pins the full human output of the positional activate/deactivate paths before
the report-extraction refactor and the ``--json`` wiring, so both are proven to
change nothing a reader sees on a success path. Each case asserts the whole
``result.output`` (only the tmp path is normalized).

Fixtures (ledger-seeded, ``--no-compile``):

* ``build_activation_project``: org pack ``acme`` with ``directive P -requires->
  tactic C -requires-> procedure G``, ``P -suggests-> styleguide S`` and
  ``P -suggests-> asset A`` (a kind-filtered node). Config stems differ from the
  declared ids.
* ``build_deactivation_project``: org pack ``acme`` with ``directive P1`` that
  requires tactics ``X`` (exclusive), ``T`` (shared with ``P2``) and ``R``
  (required by ``acme``), suggests ``styleguide S`` (no allow list) and
  ``asset A`` (kind-filtered).

The builders are shared with ``test_activation_json_6525.py``.

Not pinned here (no existing fixture constructs them without patching the
engine): a cascade target the manager refuses ("could not cascade-activate"),
a tension finding, and the zero-activatable-targets summary. Their line
formats are unchanged by the refactor and covered by their own focused tests.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

RUNNER = CliRunner()
PACK_DIR = "org-packs/acme"
#: Wide terminal so Rich never wraps a golden line.
WIDE_ENV = {"COLUMNS": "500"}

_ACTIVATION_ARTIFACTS = (
    ("directives", "directive", "p-dir", "DIRECTIVE_P"),
    ("tactics", "tactic", "c-tac", "TACTIC_C"),
    ("procedures", "procedure", "g-proc", "PROCEDURE_G"),
    ("styleguides", "styleguide", "s-style", "STYLEGUIDE_S"),
    ("assets", "asset", "a-asset", "ASSET_A"),
)
_ACTIVATION_EDGES = (
    ("directive:DIRECTIVE_P", "tactic:TACTIC_C", "requires"),
    ("tactic:TACTIC_C", "procedure:PROCEDURE_G", "requires"),
    ("directive:DIRECTIVE_P", "styleguide:STYLEGUIDE_S", "suggests"),
    ("directive:DIRECTIVE_P", "asset:ASSET_A", "suggests"),
)

_DEACTIVATION_ARTIFACTS = (
    ("directives", "directive", "p1-dir", "DIRECTIVE_P1"),
    ("directives", "directive", "p2-dir", "DIRECTIVE_P2"),
    ("tactics", "tactic", "x-tac", "TACTIC_X"),
    ("tactics", "tactic", "t-tac", "TACTIC_T"),
    ("tactics", "tactic", "r-tac", "TACTIC_R"),
    ("styleguides", "styleguide", "s-style", "STYLEGUIDE_S"),
    ("assets", "asset", "a-asset", "ASSET_A"),
)
_DEACTIVATION_EDGES = (
    ("directive:DIRECTIVE_P1", "tactic:TACTIC_X", "requires"),
    ("directive:DIRECTIVE_P1", "tactic:TACTIC_T", "requires"),
    ("directive:DIRECTIVE_P1", "tactic:TACTIC_R", "requires"),
    ("directive:DIRECTIVE_P2", "tactic:TACTIC_T", "requires"),
    ("directive:DIRECTIVE_P1", "styleguide:STYLEGUIDE_S", "suggests"),
    ("directive:DIRECTIVE_P1", "asset:ASSET_A", "suggests"),
)
_ACME_REQUIRES_R = """
    schema_version: 1
    org_name: Acme
    required_tactics:
      - r-tac
"""


def _write_pack(root: Path, artifacts: tuple[tuple[str, str, str, str], ...], edges: tuple[tuple[str, str, str], ...], org_charter: str | None) -> None:
    pack = root / PACK_DIR
    for plural, kind, stem, declared in artifacts:
        (pack / plural).mkdir(parents=True, exist_ok=True)
        (pack / plural / f"{stem}.{kind}.yaml").write_text(f"id: {declared}\ntype: {kind}\ntitle: {stem}\n", encoding="utf-8")
    nodes = "\n".join(f'  - urn: "{kind}:{declared}"\n    kind: {kind}' for _plural, kind, _stem, declared in artifacts)
    edge_lines = "\n".join(f'  - source: "{src}"\n    target: "{tgt}"\n    relation: {rel}' for src, tgt, rel in edges)
    (pack / "fixture.graph.yaml").write_text(
        f'schema_version: "1.0"\ngenerated_at: "2026-10-27T00:00:00Z"\ngenerated_by: "test"\nnodes:\n{nodes}\nedges:\n{edge_lines}\n',
        encoding="utf-8",
    )
    if org_charter is not None:
        (pack / "org-charter.yaml").write_text(textwrap.dedent(org_charter).lstrip(), encoding="utf-8")
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(f"charter_packs:\n  org:\n    packs:\n      - name: acme\n        local_path: {PACK_DIR}\n", encoding="utf-8")


def build_activation_project(root: Path, **ledger: list[str]) -> Path:
    """The activation fixture (see the module docstring)."""
    _write_pack(root, _ACTIVATION_ARTIFACTS, _ACTIVATION_EDGES, None)
    seed_activation_ledger(root, **{"mission_type_activations": ["software-dev"], "activated_directives": [], **ledger})
    return root


def build_deactivation_project(root: Path) -> Path:
    """The deactivation fixture (see the module docstring)."""
    _write_pack(root, _DEACTIVATION_ARTIFACTS, _DEACTIVATION_EDGES, _ACME_REQUIRES_R)
    seed_activation_ledger(
        root,
        mission_type_activations=["software-dev"],
        activated_directives=["p1-dir", "p2-dir"],
        activated_tactics=["x-tac", "t-tac", "r-tac"],
    )
    return root


def invoke(root: Path, command: str, *args: str) -> Result:
    """Run ``charter <command> --repo-root <root> --no-compile <args>`` on a wide terminal."""
    return RUNNER.invoke(charter_app, [command, "--repo-root", str(root), "--no-compile", *args], env=WIDE_ENV)


def normalized(result: Result, root: Path) -> str:
    """The command's stdout with the tmp root normalized (stderr carries only incidental loader warnings)."""
    return result.stdout.replace(str(root), "<ROOT>")


_NO_COMPILE = "Catalog not recompiled (--no-compile): catalog.references may go stale until the next `charter generate` or `charter activate --resynthesize`.\n"

_CASCADE_HINT = (
    "Hint: Re-run with `--cascade <scope>` (e.g. `--cascade all` for every referenced kind) to activate the referenced artifacts, "
    "or run `charter consistency-check` to confirm the activation set is coherent.\n"
)

#: name -> (fixture, command, args, ledger seed for the activation fixture, expected output)
CASES: dict[str, tuple[str, str, tuple[str, ...], dict[str, list[str]], str]] = {
    "activate_cascade_all": (
        "activation",
        "activate",
        ("--cascade", "all", "directive", "p-dir"),
        {},
        (
            "Activated: p-dir\n"
            "Cascade-activated: procedure/g-proc\n"
            "Cascade-activated: styleguide/s-style\n"
            "Cascade-activated: tactic/c-tac\n"
            "Not cascaded: asset/a-asset (kind not charter-activatable)\n" + _NO_COMPILE
        ),
    ),
    "activate_cascade_deactivated_child": (
        "activation",
        "activate",
        ("--cascade", "all", "directive", "p-dir"),
        {"deactivated_tactics": ["c-tac"]},
        (
            "Activated: p-dir\n"
            "Cascade-activated: styleguide/s-style\n"
            "Skipped, deactivated: tactic/c-tac (required by directive:DIRECTIVE_P — the parent no longer has this requirement)\n"
            "Unreached (behind a deactivated artifact): procedure/g-proc\n"
            "Hint: Run with --include-deactivated to activate these and clear their exclusions.\n"
            "Not cascaded: asset/a-asset (kind not charter-activatable)\n" + _NO_COMPILE
        ),
    ),
    "activate_cascade_include_deactivated": (
        "activation",
        "activate",
        ("--cascade", "all", "--include-deactivated", "directive", "p-dir"),
        {"deactivated_tactics": ["c-tac"]},
        (
            "Activated: p-dir\n"
            "Cascade-activated: procedure/g-proc\n"
            "Cascade-activated: styleguide/s-style\n"
            "Cascade-activated: tactic/c-tac\n"
            "Reinstated: tactic/c-tac (exclusion cleared)\n"
            "Not cascaded: asset/a-asset (kind not charter-activatable)\n" + _NO_COMPILE
        ),
    ),
    "activate_cascade_narrowed": (
        "activation",
        "activate",
        ("--cascade", "tactic", "directive", "p-dir"),
        {},
        (
            "Activated: p-dir\n"
            "Cascade-activated: tactic/c-tac\n"
            "Skipped (out of scope): procedure/g-proc\n"
            "Skipped (out of scope): styleguide/s-style\n"
            "Not cascaded: asset/a-asset (kind not charter-activatable)\n" + _NO_COMPILE
        ),
    ),
    "activate_cascade_out_of_scope_deactivated": (
        "activation",
        "activate",
        ("--cascade", "directive,procedure", "directive", "p-dir"),
        {"deactivated_tactics": ["c-tac"]},
        (
            "Activated: p-dir\n"
            "Skipped (out of scope): styleguide/s-style\n"
            "Skipped (out of scope): tactic/c-tac (deactivated; nothing behind it was walked)\n"
            "Unreached (behind a deactivated artifact): procedure/g-proc\n"
            "Hint: Run with --include-deactivated to activate these and clear their exclusions.\n"
            "Not cascaded: asset/a-asset (kind not charter-activatable)\n" + _NO_COMPILE
        ),
    ),
    "activate_direct": (
        "activation",
        "activate",
        ("directive", "p-dir"),
        {},
        (
            "Activated: p-dir\n"
            "Warning: referenced procedure/g-proc was not activated (no --cascade).\n"
            "Warning: referenced styleguide/s-style was not activated (no --cascade).\n"
            "Warning: referenced tactic/c-tac was not activated (no --cascade).\n"
            + _CASCADE_HINT
            + "Not cascaded: asset/a-asset (kind not charter-activatable)\n"
            + _NO_COMPILE
        ),
    ),
    "activate_direct_deactivated_child": (
        "activation",
        "activate",
        ("directive", "p-dir"),
        {"deactivated_tactics": ["c-tac"]},
        (
            "Activated: p-dir\n"
            "Warning: referenced procedure/g-proc was not activated (no --cascade).\n"
            "Warning: referenced styleguide/s-style was not activated (no --cascade).\n"
            "Warning: referenced tactic/c-tac is deactivated and was not activated.\n"
            + _CASCADE_HINT
            + "Not cascaded: asset/a-asset (kind not charter-activatable)\n"
            + _NO_COMPILE
        ),
    ),
    "activate_only": (
        "activation",
        "activate",
        ("--only", "tactic", "c-tac"),
        {"activated_tactics": ["adversarial-qa-handoff"]},
        (
            "Activated: c-tac\n"
            # a8dd1812 (#6457): --only names the list it wrote before the footer.
            "Now listed for tactic (1): c-tac\n"
            "No longer in force (1): adversarial-qa-handoff\n"
            "Warning: referenced procedure/g-proc was not activated (no --cascade).\n" + _CASCADE_HINT + _NO_COMPILE
        ),
    ),
    "deactivate_cascade_all": (
        "deactivation",
        "deactivate",
        ("--cascade", "all", "directive", "p1-dir"),
        {},
        (
            "Deactivated: p1-dir\n"
            "Cascade: styleguide/s-style: still active (no allow-list; only p1-dir excluded)\n"
            "Cascade: tactic/r-tac: skipped (required by acme)\n"
            "Cascade-deactivated: tactic/x-tac\n"
            "Skipped (shared artifact): tactic:TACTIC_T (still referenced by directive:DIRECTIVE_P2)\n"
            "Not cascaded: asset/a-asset (kind not charter-activatable)\n" + _NO_COMPILE
        ),
    ),
    "deactivate_direct": (
        "deactivation",
        "deactivate",
        ("directive", "p2-dir"),
        {},
        ("Deactivated: p2-dir\n" + _NO_COMPILE),
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_text_output_is_pinned(tmp_path: Path, name: str) -> None:
    fixture, command, args, ledger, expected = CASES[name]
    root = build_activation_project(tmp_path, **ledger) if fixture == "activation" else build_deactivation_project(tmp_path)

    result = invoke(root, command, *args)

    assert result.exit_code == 0, result.output
    assert normalized(result, root) == expected
