"""Filesystem-derived inventory of the shipped ``packs/built-in`` doctrine (#3234).

The doctrine cardinality/inventory gates used to pin frozen literals
(``EXPECTED_PROFILE_COUNT = 25``, ``(345, 934)``, ``108`` glossary terms, ...).
Those were change-detectors: every built-in doctrine addition reddened them
even though nothing had regressed, and the numbers carried a growing ledger of
"why did this move" prose that a human had to hand-reconcile.

This module replaces those literals with values **derived from an independent
source** -- the on-disk inventory of ``packs/built-in/`` -- so the gates stay
real invariants ("the loader/extractor dropped or missed a shipped artifact")
without reddening on every legitimate addition.

Anti-tautology contract
-----------------------
The expectation is computed by **globbing the source files** the extractor/loader
consumes, never by reading the graph object under test. So:

* Adding a new shipped artifact file (a new ``*.tactic.yaml`` etc.) bumps the
  glob count and the loaded graph in lockstep -> still green (no false red).
* A loader/extractor that **skips** a shipped file counts it in the glob but not
  in the graph -> the graph falls short of this inventory -> **red**. Not vacuous.

The filesystem (source ``*.yaml`` files) is genuinely independent of the graph:
the extractor parses the source files to *produce* the graph, and the loader
deserializes the committed ``*.graph.yaml`` fragments; neither is this module's
glob of the raw source tree.

Node kinds that are NOT one-source-file-per-node
------------------------------------------------
``action`` (24) and ``template`` (24) are **structurally derived** -- actions
from the mission step projection, templates from ``iter_template_refs`` -- so
there is no 1:1 source file to glob. They are counted from the committed
per-kind fragments (``action.graph.yaml`` / ``template.graph.yaml``) via a raw
YAML parse (independent of the DRG loader's ``DRGGraph`` construction, so a
deserialization drop still reds). Their **exact** cardinality/edge integrity is
the job of ``spec-kitty charter pack regenerate-graph --check`` (committed
fragments == a fresh regeneration), not of a frozen literal here.

Edges
-----
Edge totals come from frontmatter refs and cannot be cheaply derived from the
filesystem independently, so this module deliberately exposes **no exact edge
integer**. Tests assert a floor (``edges >= nodes``) and lean on
``regenerate-graph --check`` (and the in-test byte-identity assertion in
``tests/charter_offering/drg/migration/test_extractor_projection.py::
test_shipped_graph_is_fresh_and_byte_identical``) for exact edge integrity.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
PACK_ROOT: Path = REPO_ROOT / "packs" / "built-in"

_YAML = YAML(typ="safe")

#: Node kinds shipped as exactly one source file per graph node. Globbed
#: recursively so nested pack subdirs (``tactics/refactoring/*.tactic.yaml`` ...)
#: are inventoried. This is the load-bearing, independent anti-drop signal.
FILE_BACKED_NODE_GLOBS: dict[str, str] = {
    "agent_profile": "agent_profiles/**/*.agent.yaml",
    "directive": "directives/**/*.directive.yaml",
    "tactic": "tactics/**/*.tactic.yaml",
    "styleguide": "styleguides/**/*.styleguide.yaml",
    "toolguide": "toolguides/**/*.toolguide.yaml",
    "procedure": "procedures/**/*.procedure.yaml",
    "paradigm": "paradigms/**/*.paradigm.yaml",
    "glossary_pack": "glossary_packs/**/*.glossary-pack.yaml",
    "asset": "assets/**/*.asset.yaml",
    "mission_step_contract": "missions/built_in_step_contracts/**/*.step-contract.yaml",
    "mission_type": "missions/mission_types/*.yaml",
}

#: Structurally-derived node kinds (no 1:1 source file). Counted from the
#: committed per-kind fragment; exact integrity is guaranteed by
#: ``regenerate-graph --check``, not by a frozen literal.
_STRUCTURAL_NODE_FRAGMENTS: tuple[str, ...] = (
    "action.graph.yaml",
    "template.graph.yaml",
)

_GLOSSARY_PACK_GLOB = "glossary_packs/*.glossary-pack.yaml"


def _fragment_node_count(fragment_name: str) -> int:
    """Count ``nodes`` entries in a committed ``*.graph.yaml`` fragment.

    Raw YAML parse -- deliberately NOT the DRG loader -- so a loader
    deserialization that drops a node still diverges from this count.
    """
    data = _YAML.load((PACK_ROOT / fragment_name).read_text(encoding="utf-8"))
    return len(data.get("nodes") or [])


def file_backed_node_count() -> int:
    """Number of shipped source files across the one-file-per-node kinds."""
    return sum(
        len(list(PACK_ROOT.glob(pattern)))
        for pattern in FILE_BACKED_NODE_GLOBS.values()
    )


def structural_node_count() -> int:
    """``action`` + ``template`` node count, from the committed fragments."""
    return sum(_fragment_node_count(name) for name in _STRUCTURAL_NODE_FRAGMENTS)


def pure_builtin_node_count() -> int:
    """Expected node count of a fresh ``generate_graph`` run (no overlay).

    = file-backed source files + structurally-derived (action/template).
    """
    return file_backed_node_count() + structural_node_count()


def hand_authored_node_count() -> int:
    """Number of hand-authored overlay nodes the extractor cannot mint."""
    from charter.offering.drg.migration.hand_authored_overlay import HAND_AUTHORED_NODES

    return len(HAND_AUTHORED_NODES)


def shipped_builtin_node_count() -> int:
    """Expected node count of the shipped graph (pure regeneration + overlay)."""
    return pure_builtin_node_count() + hand_authored_node_count()


def builtin_profile_ids() -> set[str]:
    """Every shipped agent-profile id, parsed from the source ``*.agent.yaml``."""
    ids: set[str] = set()
    for path in PACK_ROOT.glob(FILE_BACKED_NODE_GLOBS["agent_profile"]):
        data = _YAML.load(path.read_text(encoding="utf-8"))
        ids.add(data["profile-id"])
    return ids


def builtin_profile_count() -> int:
    """Number of shipped agent profiles."""
    return len(builtin_profile_ids())


def builtin_asset_urns() -> set[str]:
    """Every shipped asset URN (``asset:<id>``), parsed from the sidecar YAMLs."""
    urns: set[str] = set()
    for path in PACK_ROOT.glob(FILE_BACKED_NODE_GLOBS["asset"]):
        data = _YAML.load(path.read_text(encoding="utf-8"))
        urns.add(f"asset:{data['id']}")
    return urns


def builtin_glossary_term_count(pack_id: str = "spec-kitty-core") -> int:
    """Number of terms shipped by a built-in glossary pack.

    Parsed from the pack's source YAML (independent of
    ``GlossaryPackRepository``), so a loader that drops terms diverges.
    """
    for path in PACK_ROOT.glob(_GLOSSARY_PACK_GLOB):
        data = _YAML.load(path.read_text(encoding="utf-8"))
        if data.get("id") == pack_id:
            return len(data.get("terms") or [])
    raise AssertionError(
        f"no built-in glossary pack with id {pack_id!r} under {PACK_ROOT}"
    )
