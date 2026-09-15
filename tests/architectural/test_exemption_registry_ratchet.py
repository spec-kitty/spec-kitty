"""Exemption registry + anti-ninth ratchet + C8 rename-invariance (WP10 / R-017).

The **stall countermeasure** that lands *before* any retirement (owner contract
C5/C8/C9, spec FR-012/FR-013/NFR-006/NFR-008 amended). It is the SINGLE permitted
structural test for this mission (NFR-008 amended) and it is deliberately
**negative + registry-backed**, never a positive count:

* **Registry (T053, C5).** Every filename-based exemption *mechanism* is enumerated
  as ONE row file under ``tool_artifact_enrolment/registry/`` — one mechanism per
  file so a later retirement WP deletes *only its own* row and never collides with a
  sibling retirement editing a shared file (the squad-mandated design, and the plan's
  stated reason for rejecting golden-count mode: "a single shared registry file would
  make WP15/WP16/WP17 co-own one file"). The rows are the authority; a **negative
  structural scan** derived by rule R-014 asserts that no such mechanism exists
  *outside* the enumerated rows. The registry only SHRINKS: when a mechanism is
  retired onto the owner its literal/symbol vanishes from ``src/`` and the
  overcount / symbol-presence arm goes RED until the row file is deleted (red→green
  per retirement).

* **R-014 derivation rule.** A mechanism is *every frozenset / tuple / compiled-regex
  of filenames / basenames / suffixes / path-prefixes consulted by a dirty-state or
  churn-classification predicate*. The scan walks the churn-classification surfaces
  (the ``tool-artifact-owner.md`` **Surfaces** set) with an AST matcher for exactly
  that shape. The *rule* is authority, not the hand-list: if the scan discovers a
  filename-collection with no registry row, the suite fails and names the owner
  (:func:`is_toolchain_generated_churn`) as the supported route.

* **Anti-ninth ratchet (T054, C9).** Adding a NEW filename-based exemption is
  refused: driven behaviourally through the *real* undercount seam with a synthetic
  ninth literal, the failure message names the owner. A behavioural invariant, not a
  literal source scan (NFR-008) — a benign refactor neither false-reds nor
  false-greens it.

* **C8 rename-invariance (T058).** The classification the mission preserves is by
  *declared kind*, not filename. C8a: the kind-based authority is a pure function of
  the kind (two artifacts of the SAME kind with DIFFERENT basenames classify
  identically); a filename-keyed mutant cannot. C8b: an operator-authored file whose
  basename *collides* with a generated artifact's basename outside the mission
  artifact structure is NOT classified as generated; a filename-only mutant misfires.

Modelled on ``tests/architectural/untrusted_path_audit`` (the tool-derived inventory
with an undercount arm, an overcount/ghost arm, and a drift-proof key) — here the
drift-proof key is ``(module, symbol)``, stable across line moves and renames.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from mission_runtime import (
    is_primary_artifact_kind,
    kind_for_mission_file,
)
from specify_cli.coordination.coherence import is_coord_residue_churn, is_toolchain_generated_churn

pytestmark = [pytest.mark.architectural]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_REGISTRY_DIR = _THIS.parent / "tool_artifact_enrolment" / "registry"

#: The canonical owner every gate must route filename churn through. Named in the
#: anti-ninth ratchet's failure message as the ONE supported route (C9).
OWNER_ROUTE = "is_toolchain_generated_churn"

# ---------------------------------------------------------------------------
# Churn-classification surfaces — the tool-artifact-owner.md **Surfaces** set.
# The R-014 scan is scoped to these modules (repo-root-relative). Transcribed
# from contracts/tool-artifact-owner.md; a new module that grows a
# filename-exemption is folded here (and a matching registry row added) by the
# WP that introduces it.
# ---------------------------------------------------------------------------
CHURN_SURFACE_MODULES: tuple[str, ...] = (
    "src/specify_cli/coordination/transaction.py",
    "src/specify_cli/merge/bookkeeping_projection.py",
    "src/specify_cli/merge/executor.py",
    "src/mission_runtime/artifacts.py",
    "src/specify_cli/status/__init__.py",
    "src/specify_cli/coordination/commit_router.py",
    "src/specify_cli/cli/commands/implement_cores.py",
    "src/specify_cli/bulk_edit/diff_check.py",
    "src/specify_cli/git/ref_advance.py",
    "src/specify_cli/cli/commands/agent/tasks_move_task.py",
    "src/specify_cli/merge/ordering.py",
    "src/specify_cli/lanes/merge.py",
    "src/specify_cli/review/dirty_classifier.py",
    "src/specify_cli/merge/git_probes.py",
    "src/specify_cli/cli/commands/agent/mission_record_analysis.py",
    "src/specify_cli/acceptance/__init__.py",
    "src/specify_cli/coordination/coherence.py",
    "src/specify_cli/cli/commands/implement.py",
    "src/specify_cli/lanes/auto_rebase.py",
)

# ---------------------------------------------------------------------------
# R-014 filename-collection matcher (the "such mechanism" derivation rule).
# ---------------------------------------------------------------------------
_FILENAME_TOKENS: tuple[str, ...] = (
    ".json", ".jsonl", ".md", ".lock", ".yaml", ".yml", ".txt",
)


def _string_looks_like_filename(value: str) -> bool:
    """A string constant that names a file / basename / suffix / path-prefix.

    The tokens are deliberately conservative: an extension token, a trailing ``/``
    (a path-prefix like ``.kittify/``), or a leading ``.`` (a dotfile / dot-dir).
    """
    if any(token in value for token in _FILENAME_TOKENS):
        return True
    if value.endswith("/"):
        return True
    return value.startswith(".") and len(value) > 1


def _name_is_filename_ref(name: str) -> bool:
    """A ``Name`` element (e.g. ``EVENTS_FILENAME``) that resolves to a filename."""
    return name.endswith(("_FILENAME", "_FILES", "_SUFFIX", "_SUFFIXES"))


def _collection_elements(node: ast.expr) -> list[ast.expr] | None:
    """Elements of a ``frozenset({..})`` / ``set`` / ``tuple`` / ``list`` display.

    ``None`` when *node* is not a collection display. An empty list is returned for
    an element-less collection (``frozenset()``) so callers can distinguish
    "collection with no filename signal" from "not a collection".
    """
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
    ):
        if node.args and isinstance(node.args[0], (ast.Set, ast.List, ast.Tuple)):
            return list(node.args[0].elts)
        return []
    if isinstance(node, (ast.Set, ast.Tuple, ast.List)):
        return list(node.elts)
    return None


def _regex_pattern(node: ast.expr) -> str | None:
    """The literal pattern string of a ``re.compile("...")`` call, else ``None``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "compile"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def _has_filename_signal(elements: list[ast.expr]) -> bool:
    """True when any collection element is filename-like (string) or a filename ref."""
    for element in elements:
        if (
            isinstance(element, ast.Constant)
            and isinstance(element.value, str)
            and _string_looks_like_filename(element.value)
        ):
            return True
        if isinstance(element, ast.Name) and _name_is_filename_ref(element.id):
            return True
    return False


def _assigned_name(node: ast.stmt) -> tuple[str, ast.expr] | None:
    """``(symbol, value)`` for a module-level ``Assign`` / ``AnnAssign`` to a Name."""
    if (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ):
        return node.targets[0].id, node.value
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
        return node.target.id, node.value
    return None


def _scan_module(rel_module: str) -> dict[str, str]:
    """Discovered R-014 filename-collections in *rel_module*: ``{symbol: locator}``.

    Only module-level assignments are considered (every enumerated mechanism has
    this shape). A regex whose pattern is filename-like, or a collection with a
    filename signal, qualifies.
    """
    path = _REPO_ROOT / rel_module
    discovered: dict[str, str] = {}
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        assigned = _assigned_name(node)
        if assigned is None:
            continue
        symbol, value = assigned
        pattern = _regex_pattern(value)
        if pattern is not None:
            if _string_looks_like_filename(pattern):
                discovered[symbol] = f"{rel_module}:{node.lineno}"
            continue
        elements = _collection_elements(value)
        if elements is None:
            continue
        if _has_filename_signal(elements):
            discovered[symbol] = f"{rel_module}:{node.lineno}"
    return discovered


def discover_literals() -> dict[tuple[str, str], str]:
    """Every discovered R-014 literal across the surfaces: ``{(module, symbol): locator}``."""
    out: dict[tuple[str, str], str] = {}
    for rel_module in CHURN_SURFACE_MODULES:
        for symbol, locator in _scan_module(rel_module).items():
            out[(rel_module, symbol)] = locator
    return out


# ---------------------------------------------------------------------------
# Registry rows (one file per mechanism).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RegistryRow:
    """One enumerated exemption mechanism, parsed from a registry row file."""

    mechanism: str
    module: str
    symbol: str
    literals: tuple[str, ...]
    retirement_wp: str
    status: str
    row_path: Path = field(compare=False)

    def literal_keys(self) -> set[tuple[str, str]]:
        """The ``(module, literal-symbol)`` keys this row claims in the scan."""
        return {(self.module, name) for name in self.literals}


def _parse_row_field(text: str, key: str) -> str:
    """Return the ``- <key>: <value>`` value (backticks stripped), or ``""``."""
    prefix = f"- {key}:"
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip().strip("`").strip()
    return ""


def _parse_literals(text: str) -> tuple[str, ...]:
    raw = _parse_row_field(text, "literals")
    if not raw or raw == "(none)":
        return ()
    return tuple(part.strip().strip("`") for part in raw.split(",") if part.strip().strip("`"))


def load_registry() -> list[RegistryRow]:
    """Parse every ``registry/*.md`` row file into a :class:`RegistryRow`."""
    rows: list[RegistryRow] = []
    for path in sorted(_REGISTRY_DIR.glob("*.md")):
        if path.stem == "README":
            continue  # the format doc, not a mechanism row
        text = path.read_text(encoding="utf-8")
        rows.append(
            RegistryRow(
                mechanism=_parse_row_field(text, "mechanism"),
                module=_parse_row_field(text, "module"),
                symbol=_parse_row_field(text, "symbol"),
                literals=_parse_literals(text),
                retirement_wp=_parse_row_field(text, "retirement-wp"),
                status=_parse_row_field(text, "status"),
                row_path=path,
            )
        )
    return rows


def registry_literal_map(rows: list[RegistryRow]) -> dict[tuple[str, str], str]:
    """``{(module, literal-symbol): mechanism}`` across all rows."""
    out: dict[tuple[str, str], str] = {}
    for row in rows:
        for key in row.literal_keys():
            out[key] = row.mechanism
    return out


# ---------------------------------------------------------------------------
# The two negative-scan arms (PURE seams the tests drive — mirrors audit.py).
# ---------------------------------------------------------------------------
def check_undercount(
    discovered: dict[tuple[str, str], str],
    registry: dict[tuple[str, str], str],
) -> list[str]:
    """Every discovered R-014 literal must be claimed by a registry row.

    An unclaimed literal is a NEW (or reintroduced) filename-based exemption — the
    error names :data:`OWNER_ROUTE` as the ONE supported route (C9). PURE seam.
    """
    errors: list[str] = []
    for key in sorted(set(discovered) - set(registry)):
        module, symbol = key
        errors.append(
            f"R-014 filename-collection {symbol!r} in {discovered[key]} is NOT in the "
            f"exemption registry: a new filename-based exemption is refused. Route the "
            f"classification through the owner {OWNER_ROUTE!r} instead of adding a per-gate "
            f"list, OR (if it is a genuine, justified mechanism) add a per-mechanism row "
            f"under tests/architectural/tool_artifact_enrolment/registry/."
        )
    return errors


def check_overcount(
    discovered: dict[tuple[str, str], str],
    registry: dict[tuple[str, str], str],
) -> list[str]:
    """Every registry-claimed literal must still be live (the registry only shrinks).

    A claimed literal with no live scan hit is a retired mechanism whose row lingers —
    the retirement WP must DELETE its row file (red→green). PURE seam.
    """
    errors: list[str] = []
    for key in sorted(set(registry) - set(discovered)):
        module, symbol = key
        errors.append(
            f"registry row for {registry[key]!r} claims literal {symbol!r} in {module}, "
            f"but the scan finds no such live collection: the mechanism was retired onto "
            f"the owner. DELETE its registry row file so the registry shrinks."
        )
    return errors


def _module_references_symbol(rel_module: str, symbol: str) -> bool:
    """True when *symbol* is still present anywhere in *rel_module*.

    Covers all mechanism shapes: a module-level ``def`` / ``class`` / assignment, a
    dataclass field, OR a parameter / local variable name (``new_checkout_paths`` is a
    threaded variable, not a module-level symbol). When a retirement removes the
    mechanism entirely the name vanishes and this goes RED — the shrink signal for the
    non-literal mechanisms.
    """
    path = _REPO_ROOT / rel_module
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
            return True
        if isinstance(node, ast.Name) and node.id == symbol:
            return True
        if isinstance(node, ast.arg) and node.arg == symbol:
            return True
        if isinstance(node, ast.keyword) and node.arg == symbol:
            return True
    return False


# ===========================================================================
# T053 — the registry & the negative structural scan
# ===========================================================================
#: The two honest terminal states a row can carry. ``expected-present`` is the
#: WP10-landing default — a to-be-retired mechanism the strangler still expects
#: to find live in ``src/``. ``justified-survivor`` (plan.md L233-235: "a genuine
#: must-keep ... becomes an explicit, justified registry row, never a silent
#: survivor") marks a mechanism a retirement WP investigated and kept ON PURPOSE
#: because it is genuinely outside the owner's scope — it is never expected to
#: be retired, so it is exempt from the "eventually deleted" shrink narrative,
#: but it stays ENUMERATED (visible to any audit of unowned filename exemptions)
#: rather than disappearing into an unregistered, function-local predicate. The
#: current survivors were registered by WP14/IC-07d, WP15/IC-07e, and WP17/IC-07g.
_ROW_STATUSES: frozenset[str] = frozenset({"expected-present", "justified-survivor"})


def test_registry_is_non_empty_and_enumerated() -> None:
    """The registry is pre-populated with every mechanism, one file per mechanism."""
    rows = load_registry()
    assert rows, "registry/ is empty — the countermeasure must land pre-populated."
    # One file per mechanism (no shared file): file stem == mechanism name.
    for row in rows:
        assert row.row_path.stem == row.mechanism, (
            f"registry row {row.row_path.name} must be named <mechanism>.md so a "
            f"retirement WP deletes only its own file (got mechanism={row.mechanism!r})."
        )
    # Every row is either still-to-retire (``expected-present``, the WP10-landing
    # default) or an explicit, justified permanent survivor (``justified-survivor``,
    # IC-07d/WP14, IC-07e/WP15, IC-07g/WP17) — never an unrecognised status.
    for row in rows:
        assert row.status in _ROW_STATUSES, (
            f"row {row.mechanism!r} status must be one of {sorted(_ROW_STATUSES)} "
            f"(got {row.status!r})."
        )


def test_registry_covers_every_known_mechanism() -> None:
    """Every mechanism the contract C5 enumerates has a row (undercount of the list).

    Pins the ≥11 derived-by-R-014 mechanisms so a dropped row file fails loudly. The
    rule remains the authority (the scan below is the real negative property); this is
    the human-readable floor that keeps the row set honest.

    This floor SHRINKS in lockstep with the registry (T077): a retirement WP that
    deletes its own row file also removes its mechanism name here, so the floor
    keeps distinguishing "a row was legitimately retired" from "a row file was
    dropped without doing the retirement" — not freezing the registry at its WP10
    landing size. Retired examples (absent from ``required`` because their rows are
    deleted and the mechanism routed onto the owner ``is_toolchain_generated_churn``):
    ``is_self_bookkeeping_path`` (WP11/IC-07a), ``is_coordination_artifact_residue_path``
    (WP12/IC-07b, onto the residue leg ``is_coord_residue_churn``),
    ``COORD_OWNED_STATUS_FILES`` (WP13/IC-07c, the frozenset + the ``advance_branch_ref``
    ``coord_owned_filenames`` param + the coord-staging skip, onto
    ``MissionArtifactKind.STATUS_STATE``), the ``_drop_vcs_lock_only_meta`` /
    ``_drop_runtime_frontmatter_only_wp`` / ``_exclude_coord_owned`` trio (WP14/IC-07d
    deduplicated all three into ONE ``_drop_if(paths, predicate)`` call, routing
    ``_exclude_coord_owned`` onto the owner-exposed ``is_status_state_path`` leg),
    ``RUNTIME_STATE_ALLOWLIST`` (WP15/IC-07e), and — from WP17/IC-07g —
    ``ACCEPT_OWNED_PATHS`` (onto :func:`mission_runtime.kind_for_mission_file`), most
    of the ``dirty_classifier_bundle`` (onto the owner), and the dead
    ``ignores_primary_coord_residue`` (simply deleted).
    The floor also GROWS for genuine, justified permanent survivors: WP14 added
    ``_is_self_write_only_diff`` (the vcs-lock/frontmatter pair merged into one
    diff-scoped predicate that cannot route onto ``is_toolchain_generated_churn``
    without a C6 behaviour change), WP15 added ``_is_review_lifecycle_basename``, and
    WP17 added ``_is_review_handoff_survivor_path`` (``notes.md`` /
    ``review-cycle-*.md`` / review-handoff files are human-authored, outside the
    owner's toolchain-generated-write scope), keeping the census a truthful count of
    every *currently enumerated* mechanism, not only the shrinking to-be-retired ones.
    """
    rows = {row.mechanism for row in load_registry()}
    required = {
        "_is_self_write_only_diff",
        "_is_review_lifecycle_basename",
        "_is_review_handoff_survivor_path",
    }
    missing = required - rows
    assert not missing, (
        "exemption-registry rows missing for known mechanisms (a row file was dropped "
        "without retiring the mechanism):\n" + "\n".join(f"  - {m}" for m in sorted(missing))
    )


def test_no_r014_literal_exists_outside_the_registry() -> None:
    """NEGATIVE SCAN (C5): no R-014 filename-collection exists outside the rows.

    The derivation rule is the authority — the scan walks the churn surfaces and every
    discovered filename-collection must be claimed by a per-mechanism registry row.
    An unclaimed one fails (a new/reintroduced exemption), naming the owner route.
    """
    discovered = discover_literals()
    registry = registry_literal_map(load_registry())
    errors = check_undercount(discovered, registry)
    assert not errors, "R-014 mechanism(s) outside the registry:\n" + "\n".join(f"  {e}" for e in errors)


def test_registry_only_shrinks_no_ghost_rows() -> None:
    """OVERCOUNT (registry only shrinks): every claimed literal is still live.

    A ghost row (claimed literal the scan no longer finds) means the mechanism was
    retired but its row file lingers — the retirement WP must delete it.
    """
    discovered = discover_literals()
    registry = registry_literal_map(load_registry())
    errors = check_overcount(discovered, registry)
    assert not errors, "ghost registry row(s) — delete the retired mechanism's file:\n" + "\n".join(
        f"  {e}" for e in errors
    )


def test_every_registry_symbol_is_present_in_its_module() -> None:
    """Each mechanism's canonical symbol is still defined in its declared module.

    Covers the function/field-only mechanisms (no filename literal of their own):
    when a retirement removes the ``def`` / field, this arm goes RED until the row is
    deleted — the same shrink signal as overcount, for the non-literal mechanisms.
    """
    failures: list[str] = []
    for row in load_registry():
        if not _module_references_symbol(row.module, row.symbol):
            failures.append(
                f"registry mechanism {row.mechanism!r}: symbol {row.symbol!r} is no longer "
                f"defined in {row.module} — it was retired onto the owner. DELETE its row file."
            )
    assert not failures, "\n".join(failures)


def test_discovered_scan_is_non_vacuous() -> None:
    """The scan genuinely inspects real source (anti-vacuous guard).

    A scan that discovers zero literals would let every other arm pass trivially.
    """
    discovered = discover_literals()
    assert discovered, (
        "the R-014 scan discovered zero filename-collections across the churn surfaces — "
        "almost certainly a surface-path misconfiguration, not a genuinely empty result."
    )


# ===========================================================================
# T054 — anti-ninth ratchet (C9), behavioural through the real seam
# ===========================================================================
def test_ninth_filename_exemption_is_refused_naming_the_owner() -> None:
    """A synthetic ninth filename-exemption trips the real undercount seam (C9).

    Behavioural: drives :func:`check_undercount` (the same seam the negative scan runs)
    with a discovered literal absent from the registry and asserts (a) it fails and
    (b) the message names the owner :data:`OWNER_ROUTE` as the supported route. Not a
    source-line scan — a benign refactor of the gate modules cannot false-red it.
    """
    registry = registry_literal_map(load_registry())
    synthetic_ninth = {
        ("src/specify_cli/merge/some_new_gate.py", "_NEW_BENIGN_FILENAMES"): (
            "src/specify_cli/merge/some_new_gate.py:42"
        )
    }
    errors = check_undercount(synthetic_ninth, registry)
    assert errors, "a new filename-based exemption absent from the registry MUST be refused."
    assert OWNER_ROUTE in errors[0], (
        f"the refusal must name the owner {OWNER_ROUTE!r} as the supported route "
        f"(got: {errors[0]!r})."
    )


def test_ratchet_does_not_false_red_on_a_registered_mechanism() -> None:
    """The ratchet is precise: a registered literal does NOT trip undercount.

    Guards the other failure mode — a ratchet that reds on everything would be
    green-for-the-wrong-reason noise. Uses a real registered literal key.
    """
    registry = registry_literal_map(load_registry())
    assert registry, "registry produced no literal keys — the fixture is broken."
    one_registered = dict([next(iter(registry.items()))])
    # `one_registered` maps (module, symbol) -> mechanism; rebuild it as a discovered map.
    (module, symbol), _mechanism = next(iter(one_registered.items()))
    discovered = {(module, symbol): f"{module}:1"}
    assert check_undercount(discovered, registry) == []


# ===========================================================================
# T058 — C8 rename-invariance (classification by declared kind, not filename)
# ===========================================================================
def _basename_only_mutant(recognised_basename: str) -> Callable[[str], bool]:
    """A deliberately filename-based classifier — the mutant C8 must kill."""

    def _classify(path: str) -> bool:
        return path.rsplit("/", 1)[-1] == recognised_basename

    return _classify


def test_c8a_classification_is_a_pure_function_of_declared_kind() -> None:
    """C8a: two artifacts of the SAME kind at DIFFERENT basenames classify identically.

    The kind-based authority (:func:`is_primary_artifact_kind`) takes a *kind*, not a
    path — it is rename-invariant by construction. Two ``tasks/WP##.md`` files of the
    same ``WORK_PACKAGE_TASK`` kind but different basenames resolve to the same kind and
    therefore the same classification; a filename-keyed mutant does NOT.
    """
    path_a = "kitty-specs/m/tasks/WP01-alpha.md"
    path_b = "kitty-specs/m/tasks/WP07-zeta-renamed.md"
    kind_a = kind_for_mission_file(path_a, mission_slug="m")
    kind_b = kind_for_mission_file(path_b, mission_slug="m")

    assert kind_a is not None and kind_a == kind_b, (
        "the two WP task files must resolve to the same declared kind (different "
        "basenames, same kind) for the rename-invariance property to be meaningful."
    )
    # Kind-based authority: identical classification for the identical kind.
    assert is_primary_artifact_kind(kind_a) == is_primary_artifact_kind(kind_b)

    # The mutant a filename-based classifier would be: it disagrees across the rename.
    mutant = _basename_only_mutant("WP01-alpha.md")
    assert mutant(path_a) != mutant(path_b), (
        "a filename-based classifier cannot pass C8a — it flips across the rename, "
        "which is exactly the mutant this arm kills."
    )


def test_c8b_basename_collision_is_not_classified_generated() -> None:
    """C8b: an operator file whose basename collides with a generated artifact's is safe.

    An operator-authored ``status.events.jsonl`` living OUTSIDE the ``kitty-specs/<slug>/``
    artifact structure has no mission-artifact kind, so the kind/path-context authority
    (:func:`~specify_cli.coordination.coherence.is_coord_residue_churn`) does NOT
    treat it as generated residue — while a pure-basename mutant misfires.
    """
    operator_path = "docs/notes/status.events.jsonl"  # basename collides; not a mission artifact
    assert kind_for_mission_file(operator_path) is None, (
        "a file outside kitty-specs/<slug>/ must resolve to no mission-artifact kind."
    )
    assert is_coord_residue_churn(operator_path) is False, (
        "a basename collision outside the mission artifact structure must NOT be "
        "classified as generated residue (C8b)."
    )
    # And the canonical owner agrees it is not toolchain churn.
    assert is_toolchain_generated_churn(operator_path) is False

    # The mutant a filename-based classifier would be: it wrongly flags the collision.
    mutant = _basename_only_mutant("status.events.jsonl")
    assert mutant(operator_path) is True, (
        "a filename-based classifier cannot pass C8b — it flags the operator file by "
        "basename alone, the mutant this arm kills."
    )


def test_c8_generated_kind_is_classified_generated_and_rename_invariant() -> None:
    """C8 sanity floor: a genuinely generated coord artifact IS classified generated.

    Prevents C8a/C8b from passing vacuously (e.g. if the residue authority classified
    nothing). The status log — a real generated coord artifact — is residue, and the
    canonical owner agrees.
    """
    generated = "kitty-specs/m/status.events.jsonl"
    kind = kind_for_mission_file(generated, mission_slug="m")
    assert kind is not None, "the status log must resolve to a mission-artifact kind."
    assert is_coord_residue_churn(generated, mission_slug="m") is True
    assert is_toolchain_generated_churn(generated) is True
    # It is NOT a primary kind (it is coord-generated), keeping the partitions honest.
    assert is_primary_artifact_kind(kind) is False
