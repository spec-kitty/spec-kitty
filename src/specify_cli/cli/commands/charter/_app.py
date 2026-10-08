"""The charter typer app — shared instance for all subcommand modules.

Created by WP06 (MS-1: per-subcommand split of the legacy 3,328-line
``charter.py``). All subcommand modules import ``charter_app`` from here and
register their handler via ``@charter_app.command(...)``. ``app`` is kept as
the canonical legacy alias so historic imports (and the registration of the
``charter_bundle`` sub-app + ``charter_preflight`` command) keep working.
"""

from __future__ import annotations

import logging

import typer

# Re-export the canonical CLI console seam so every charter subcommand module
# can ``from ..._app import charter_app, console`` unchanged. The redundant
# ``as console`` alias marks this as an intentional re-export (PEP 484) so
# pyflakes does not treat it as an unused import.
from specify_cli.cli.console import console as console
from specify_cli.cli.commands.charter.activate import activate_cmd
from specify_cli.cli.commands.charter.deactivate import deactivate_cmd
from specify_cli.cli.commands.charter.list_cmd import charter_list_app
from specify_cli.cli.commands.charter.pack import charter_pack_app
from specify_cli.cli.commands.charter_bundle import app as charter_bundle_app
from specify_cli.cli.commands.charter.mission_type import charter_mission_type_app
from specify_cli.cli.commands.charter.authoring import fetch, new, validate
from specify_cli.cli.commands.charter.consistency_check import consistency_check_cmd
from specify_cli.cli.commands.charter.org import org_app
from specify_cli.cli.commands.charter.pack_asset import asset_app
from specify_cli.cli.commands.charter.pack_tooling import pack_assemble, pack_validate, regenerate_graph

logger = logging.getLogger("specify_cli.cli.commands.charter")

#: Filename of the (retired) charter bundle metadata sidecar. Kept for
#: migration/back-compat references only — the authoritative bundle file is
#: ``charter.yaml`` (see ``CHARTER_YAML_FILENAME``).
METADATA_FILENAME = "metadata.yaml"

#: Filename of the authoritative, git-tracked charter bundle file
#: (consolidate-charter-bundle #2773). Existence of this file — not the retired
#: ``metadata.yaml`` — gates the bundle-compatibility check on every charter
#: command surface, so a v2 bundle with an incompatible schema is still caught.
CHARTER_YAML_FILENAME = "charter.yaml"

#: The typer app exposed under ``spec-kitty charter``.
charter_app = typer.Typer(
    name="charter",
    help="Charter management commands",
    no_args_is_help=True,
)
#: Legacy alias; tests and downstream code import both names.
app = charter_app

# WP01 introduced ``charter_bundle_app`` as a self-contained Typer sub-app.
# WP03 registers it under ``bundle`` so users can invoke
# ``spec-kitty charter bundle validate`` from the unified CLI surface
# (FR-013).
charter_app.add_typer(charter_bundle_app, name="bundle")

# WP14 (FR-016): ``spec-kitty charter mission-type list`` — activated types only.
charter_app.add_typer(charter_mission_type_app, name="mission-type")

# WP06 (FR-004): ``spec-kitty charter activate <kind> <id>`` — pack activation.
# (FR-008 governs only the in-flight step-removal warning branch reached for the
# ``mission-type`` kind inside ``activate_cmd``, not this general registration.)
charter_app.command("activate")(activate_cmd)

# WP06 (FR-005): ``spec-kitty charter deactivate <kind> <id>`` — pack deactivation.
charter_app.command("deactivate")(deactivate_cmd)

# WP06 (FR-004/005/006/007): ``spec-kitty charter list`` — activation state table.
charter_app.add_typer(charter_list_app, name="list")

# ``spec-kitty charter pack list|path`` (pack.py) plus the pack tooling homes
# (mission charter-pack-cutover-01M491G6, FR-006): ``validate``, ``assemble``,
# ``regenerate-graph`` and the ``asset`` sub-app. Registered here, not in
# pack.py, so the handler modules stay independent of the pack listing.
charter_pack_app.command("validate")(pack_validate)
charter_pack_app.command("assemble")(pack_assemble)
charter_pack_app.command("regenerate-graph")(regenerate_graph)
charter_pack_app.add_typer(asset_app, name="asset")
charter_app.add_typer(charter_pack_app, name="pack")

# ``spec-kitty charter consistency-check`` checks the active charter (OD-8).
charter_app.command("consistency-check")(consistency_check_cmd)

# Authoring commands (FR-006 homes; handlers in charter/authoring.py and charter/org.py).
charter_app.command("new")(new)
charter_app.command("validate")(validate)
charter_app.command("fetch")(fetch)
charter_app.add_typer(org_app, name="org")
