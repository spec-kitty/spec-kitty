"""Retired doctrine ids are no longer named under ``src/`` or ``packs/``.

The single-owner epic deleted, renamed, moved or re-kinded eight activatable
ids (the ``RETIREMENTS`` table of the
``m_4_0_0rc5_retire_single_owner_doctrine_ids`` migration) and retired the
``adversarial-evidence-contract`` reference file. A stale mention of one of
them in shipped source is either a dangling reference (the charter compiler
is fail-closed on an unknown id) or a restated copy of a rule that now has a
single owner. This module is the one absence guard for those artifacts: it
scans shipped text for the ids, checks that no artifact file or DRG node
survives under a retired id, and checks that no activation pack or action
index still lists one.

The scan is *identifier-shaped*, per id, because two retired stems share text
with live artifacts:

* ``locality-of-change`` -- the tactic is retired; the directive
  ``024-locality-of-change`` / ``DIRECTIVE_024`` is live.
* ``boring-code-review`` -- the tactic is retired; the styleguide of the same
  id is its successor.

So for those two only the tactic-shaped forms count (``tactic:<id>``,
``<id>.tactic.yaml``, a ``type: tactic`` reference, an entry of a ``tactics:``
list); the other ids count in any identifier form. Prose that names a retired
id *as retired* (for example "folds in the retired bug-fixing-checklist
tactic") is provenance, not a reference, and is not identifier-shaped.

Allowlist (the only permitted identifier hits):

* the retirement migration module itself (it must name what it retires);
* ``packs/internal/`` for the two ids that moved there
  (``iterative-deepening-review`` renamed on the move, and
  ``tracker-organisation-workflow``).

Synthetic positive and negative controls prove the scanner is neither vacuous
nor over-eager.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]

_MIGRATION_MODULE = "src/specify_cli/upgrade/migrations/m_4_0_0rc5_retire_single_owner_doctrine_ids.py"
_INTERNAL_PACK = "packs/internal/"
_MOVED_TO_INTERNAL = frozenset({"iterative-deepening-review", "tracker-organisation-workflow"})

_TEXT_SUFFIXES = frozenset({".py", ".yaml", ".yml", ".md", ".json", ".toml", ".txt", ".j2"})


def _any_identifier_form(stem: str) -> re.Pattern[str]:
    """Any use of *stem* as an identifier (not a substring of a longer id)."""
    return re.compile(rf"(?<![\w-]){re.escape(stem)}(?![\w-])")


def _tactic_forms_only(stem: str) -> re.Pattern[str]:
    """Only the tactic-shaped uses of *stem* (its twin id is live)."""
    s = re.escape(stem)
    return re.compile(
        rf"tactic:{s}(?![\w-])"
        rf"|(?<![\w-]){s}\.tactic\.yaml"
        rf"|type:\s*tactic\s*\n\s*(?:name:[^\n]*\n\s*)?id:\s*{s}\s*$",
        re.MULTILINE,
    )


#: stem -> identifier pattern for that stem.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "adversarial-squad-cadence": _any_identifier_form("adversarial-squad-cadence"),
    "bug-fixing-checklist": _any_identifier_form("bug-fixing-checklist"),
    "common-docs-curation": _any_identifier_form("common-docs-curation"),
    "behavior-driven-development": _any_identifier_form("behavior-driven-development"),
    "iterative-deepening-review": _any_identifier_form("iterative-deepening-review"),
    "tracker-organisation-workflow": _any_identifier_form("tracker-organisation-workflow"),
    "locality-of-change": _tactic_forms_only("locality-of-change"),
    "boring-code-review": _tactic_forms_only("boring-code-review"),
    "adversarial-evidence-contract": _any_identifier_form("adversarial-evidence-contract"),
}

#: Prose that names a retired id *as retired*. Each entry is (path, stem, the
#: exact phrase); the phrase is stripped before scanning so the file stays
#: scanned for any OTHER mention of the stem.
_PROVENANCE_PHRASES: tuple[tuple[str, str, str], ...] = (
    (
        "packs/built-in/procedures/test-first-bug-fixing.procedure.yaml",
        "bug-fixing-checklist",
        "the retired bug-fixing-checklist tactic",
    ),
    (
        "packs/built-in/missions/documentation/governance-profile.yaml",
        "common-docs-curation",
        "common-docs-curation was folded into",
    ),
)


def _is_allowlisted(rel: str, stem: str) -> bool:
    if rel == _MIGRATION_MODULE:
        return True
    return rel.startswith(_INTERNAL_PACK) and stem in _MOVED_TO_INTERNAL


def _scan_text(text: str, rel: str) -> list[str]:
    """Return ``stem`` for every retired id named in *text* (after provenance)."""
    for path, _stem, phrase in _PROVENANCE_PHRASES:
        if path == rel:
            text = text.replace(phrase, "")
    return [stem for stem, pattern in _PATTERNS.items() if pattern.search(text) and not _is_allowlisted(rel, stem)]


def _tracked_text_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", "src", "packs"],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [p for p in out.splitlines() if Path(p).suffix in _TEXT_SUFFIXES]


def test_no_retired_id_is_named_under_src_or_packs() -> None:
    hits: list[tuple[str, str]] = []
    for rel in _tracked_text_files():
        path = _REPO_ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        hits.extend((rel, stem) for stem in _scan_text(text, rel))
    assert hits == [], f"retired ids still named in shipped source: {hits}"


#: (artifact kind, id) of every retired built-in artifact that had a file and a
#: DRG node of its own. ``boring-code-review`` is listed as a tactic only: the
#: styleguide of the same id is its live successor.
_RETIRED_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("styleguide", "adversarial-squad-cadence"),
    ("tactic", "bug-fixing-checklist"),
    ("tactic", "locality-of-change"),
    ("tactic", "common-docs-curation"),
    ("tactic", "boring-code-review"),
    ("tactic", "behavior-driven-development"),
    ("tactic", "iterative-deepening-review"),
    ("procedure", "tracker-organisation-workflow"),
)


@pytest.mark.parametrize(("kind", "artifact_id"), _RETIRED_ARTIFACTS, ids=lambda v: str(v))
def test_retired_artifact_has_no_file_and_no_drg_node(built_in_graph: DRGGraph, kind: str, artifact_id: str) -> None:
    """No built-in artifact file and no shipped-graph node (or edge) survives a retired id."""
    files = sorted((_REPO_ROOT / "packs" / "built-in").rglob(f"{artifact_id}.{kind}.yaml"))
    assert files == [], f"retired {kind} {artifact_id} still ships as a file: {files}"
    urn = f"{kind}:{artifact_id}"
    assert urn not in built_in_graph.node_urns()
    dangling = [(e.source, e.target) for e in built_in_graph.edges if urn in (e.source, e.target)]
    assert dangling == []


def test_synthetic_positive_control_flags_every_shape() -> None:
    snippet = (
        "activated_tactics:\n  - bug-fixing-checklist\n"
        "edge: tactic:locality-of-change\n"
        "path: tactics/boring-code-review.tactic.yaml\n"
        "- type: styleguide\n  id: adversarial-squad-cadence\n"
        "see contracts/adversarial-evidence-contract.md\n"
    )
    assert set(_scan_text(snippet, "packs/built-in/x.yaml")) == {
        "bug-fixing-checklist",
        "locality-of-change",
        "boring-code-review",
        "adversarial-squad-cadence",
        "adversarial-evidence-contract",
    }


def test_synthetic_negative_control_spares_live_twins() -> None:
    """The live directive and the successor styleguide are never flagged."""
    snippet = (
        "activated_directives:\n  - 024-locality-of-change\n"
        "see DIRECTIVE_024 locality-of-change discipline\n"
        "- type: styleguide\n  id: boring-code-review\n"
        "styleguide:boring-code-review\n"
    )
    assert _scan_text(snippet, "packs/built-in/x.yaml") == []


def test_allowlist_is_scoped_to_the_moved_ids() -> None:
    """``packs/internal`` may name the moved ids, never the other retirements."""
    snippet = "- tracker-organisation-workflow\n- iterative-deepening-review\n- bug-fixing-checklist\n"
    assert _scan_text(snippet, "packs/internal/drg/fragment.yaml") == ["bug-fixing-checklist"]


# --------------------------------------------------------------------------- #
# Structural check: activation packs and action indexes list no retired tactic.
# --------------------------------------------------------------------------- #

_RETIRED_BY_LIST_KEY: dict[str, frozenset[str]] = {
    "activated_tactics": frozenset(
        {
            "bug-fixing-checklist",
            "locality-of-change",
            "common-docs-curation",
            "boring-code-review",
            "behavior-driven-development",
            "iterative-deepening-review",
        }
    ),
    "activated_styleguides": frozenset({"adversarial-squad-cadence"}),
    "activated_procedures": frozenset({"tracker-organisation-workflow"}),
}
_ACTION_LIST_KEY = {"tactics": "activated_tactics", "styleguides": "activated_styleguides", "procedures": "activated_procedures"}


def _listed(data: dict[str, object], key: str) -> set[str]:
    value = data.get(key) or []
    return {str(v) for v in value} if isinstance(value, list) else set()


def _structural_hits(data: dict[str, object], *, action_index: bool) -> list[str]:
    hits: list[str] = []
    for key, retired in _RETIRED_BY_LIST_KEY.items():
        list_key = next((k for k, v in _ACTION_LIST_KEY.items() if v == key), key) if action_index else key
        hits.extend(sorted(_listed(data, list_key) & retired))
    return hits


def _yaml(path: Path) -> dict[str, object]:
    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


@pytest.mark.parametrize("pack", ["default.yaml", "minimal.yaml"])
def test_activation_pack_lists_no_retired_id(pack: str) -> None:
    data = _yaml(_REPO_ROOT / "src/charter/activation/packs" / pack)
    assert _structural_hits(data, action_index=False) == []


def test_action_indexes_list_no_retired_id() -> None:
    hits = {
        str(p.relative_to(_REPO_ROOT)): _structural_hits(_yaml(p), action_index=True)
        for p in sorted((_REPO_ROOT / "packs/built-in/missions").glob("*/actions/*/index.yaml"))
    }
    assert {k: v for k, v in hits.items() if v} == {}


def test_structural_positive_control() -> None:
    assert _structural_hits({"tactics": ["boring-code-review", "tdd-red-green-refactor"]}, action_index=True) == ["boring-code-review"]
    assert _structural_hits({"activated_tactics": ["locality-of-change"]}, action_index=False) == ["locality-of-change"]
