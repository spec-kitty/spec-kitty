"""Anti-regression ratchet for the built-in pack-location authority (WP04, #3039).

Mission ``doctrine-built-in-seam-consolidation-01KYW3TX`` centralizes "where does
built-in kind K live" and "where is the built-in root" into exactly two
callables in :mod:`charter.offering.pack_paths` -- :func:`~charter.offering.pack_paths.built_in_dir`
and :func:`~charter.offering.pack_paths.built_in_root`. WP01 created the authorities;
WP02/WP03/WP05 rerouted every production reader onto them; WP04 (this file)
drops the fail-open ``CharterOfferingService.built_in_root`` param that made the old
nested shape constructable, and makes the single-authority invariant a CI gate
so a sixth resolver cannot be quietly born (NFR-002).

This file is deliberately its OWN module -- NOT folded into
``test_no_dead_doctrine_paths.py`` (cf. #3039's planned split; C3.4). It covers
three independent contract clauses:

* **C3.1 / C3.1b -- the joins-only AST ratchet.** AST-scans ``src/`` for a
  built-in path *join* -- a ``resolve_pack_root("built-in") / …`` ``BinOp``
  (direct or **variable-indirected**: ``x = resolve_pack_root("built-in"); x /
  …``), or a ``<path> / "built-in"`` filesystem join. Both limbs are
  load-bearing: a ``BinOp``-only scan would false-green the indirected form
  paula flagged as the exact drift class (MAJOR-2); a naive *constant* scan
  would false-red the ~20 legitimate bare ``"built-in"`` string markers used as
  layer/provenance tags. This gate is **join-only, not a constant-scan** --
  it only inspects ``ast.BinOp`` nodes, so a bare string literal used as a
  dict key, docstring text, or comparison operand never trips it, with no
  per-site marker allowlist required. A bare ``resolve_pack_root("built-in")``
  root call (the sanctioned ``built_in_root()`` seam) is likewise permitted --
  it is never the ``.left`` of a ``Div`` ``BinOp`` at any of its call sites, so
  it never matches either limb.
* **C3.2 / NFR-003/005 -- positive per-kind coverage + the #3091 marker.** Every
  kind WITH a ``packs/built-in/<plural>/`` content dir (the 9) resolves inside
  an *existing* directory, asserted **through** :func:`resolve_pack_root`
  (never a raw repo-relative ``.exists()`` -- cf. #3036, survives the future
  wheel-split). The derived complement ``{mission_step_contract, template,
  anti_pattern}`` -- computed from :attr:`~charter.offering.artifact_kinds.ArtifactKind.has_built_in_content_dir`,
  never hand-listed -- raises :class:`~charter.offering.pack_paths.BuiltInContentDirNotAvailable`.
* **C3.3 / NFR-003 -- anti-vacuity.** The shipped ``agent_profiles`` set
  resolved through the authority is non-empty, so a stale/misconfigured root
  fails loudly instead of passing vacuously (the exact latent false-green this
  mission exists to kill; US2 acceptance #2).

Known pre-existing exemptions (read before extending ``_KNOWN_JOIN_SITES``)
-----------------------------------------------------------------------------
``src/charter/activation/kind_vocabulary.py``'s ``_org_scan_dirs`` joins
``flat / "built-in"`` (``flat = root / kind.plural``) while walking ``org_roots``
-- syntactically a filesystem join (C3.1's third limb), but *semantically* the
**ORG tier's** own legacy nested-pack contract (``<org_root>/<plural>/built-in``,
documented in-file: "this nested layout is still live for org packs (unaffected
by the built-in relocation)"). It does not call ``resolve_pack_root("built-in")``
or ``built_in_dir``/``built_in_root`` at all, and it is out of scope for the
built-in-tier consolidation. A pure syntax scan cannot distinguish "root walks
an org pack" from "root walks the built-in tier", so this ONE site is exempted
by a content descriptor, not by file, so any FUTURE join added to this file
(e.g. a resurrected built-in-tier dual-read) still fails the gate.
Reintroducing a similar org-tier convention elsewhere requires a deliberate
allowlist edit naming the new site's rationale, mirroring
``tests/architectural/test_protection_resolver_call_sites.py``.

Additional exemptions (2026-08-05, mission
``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP05 CI-remediation
fold, #3204) fall into two rationale classes, neither of which is a
``resolve_pack_root("built-in")``/``built_in_root()`` reconstruction:

1. **Layer-boundary / import-avoidance sibling-shape sites.** ``kernel`` sits
   *below* ``doctrine`` (``kernel <- doctrine <- charter <- specify_cli``,
   C-004) and cannot import ``charter.offering.pack_paths`` at all --
   ``src/kernel/paths.py``'s own module docstring states these functions "have
   no spec-kitty-specific dependencies". ``specify_cli/runtime/agent_commands.py``
   *could* import ``charter.offering.pack_paths`` (the layer allows it) but
   deliberately does not, to avoid triggering doctrine's heavy validation
   imports on every CLI startup (see its own module docstring: "Uses import
   metadata rather than ``import doctrine``"). It instead consumes
   ``kernel.paths.MISSION_ASSETS_SIBLING_PATTERN`` -- the kernel-owned
   ``packs/built-in/missions`` *relative-shape constant* (FR-012, mission
   ``resolution-activation-foundation-01KZ9FKG`` WP02 collapsed the
   independently-typed per-module literal onto this one authority) -- as the
   ``sibling_relative_path`` input to
   :func:`kernel.sibling_paths.resolve_installed_sibling`, a *different*,
   domain-agnostic primitive than the ``charter.offering.pack_paths`` authority this
   gate protects. Consuming an imported constant by plain-name reference is
   not a ``/``-join, so this site never trips the AST scan below regardless of
   its line number -- it needs no allowlist entry, and none of the class-1
   sites holds an exemption today.
   ``charter.offering.missions.repository.MissionTemplateRepository.default_missions_root``
   (formerly a peer convergent call site of this same primitive) was
   re-pointed by the same WP02 onto :func:`charter.offering.pack_paths.built_in_missions_root`
   -- a join that lives inside the authority file itself -- so it no longer
   performs its own sibling-resolution walk or needs a class-1 exemption
   either.
2. **Caller-supplied-root sites (env-var override / legacy dev-checkout
   acceptance).** Several sites resolve ``packs/built-in/missions`` relative to
   an arbitrary directory the *caller* supplied (``SPEC_KITTY_TEMPLATE_ROOT``,
   a ``--template-root``/``--local-repo`` override, or a lint's ``repo_root``
   parameter) rather than relative to the running installation's own module
   location. ``resolve_pack_root("built-in")``/``built_in_root()`` ignore any
   such caller-supplied root entirely -- they only ever resolve *this*
   installation's own built-in tier -- so routing these through the authority
   would silently substitute the real installed tree for the caller's
   explicitly-requested one, breaking the exact ``tmp_path``-rooted fixtures
   these functions are tested against (e.g.
   ``tests/charter/test_neutrality_lint.py::test_default_scan_roots_include_relocated_builtin_missions``,
   ``tests/test_template/test_manager.py::test_copy_specify_base_from_local_copies_expected_assets``).
   These are the "org-tier own contract" pattern above, generalized to a
   caller-root pattern instead of an org-pack pattern.

How exemptions match (descriptor identity, multiset, fail-on-stale)
-------------------------------------------------------------------
Each exempted site is a :class:`~tests.architectural._ratchet_keys.ContentDescriptor`
``(rel_path, qualname, token_substring, occurrence, rationale)`` resolved to the
site's ``(rel_path, qualname, token_line)`` composite key, never a
``(file, lineno)`` pin, so unrelated edits above a site no longer force a
re-pin (``test_join_allowlist_survives_line_drift``). Matching goes through
:mod:`tests.architectural._content_identity`, the single matching authority:

* **Multiset.** One entry suppresses at most one finding, and keys always carry
  ``rel_path``. ``composite_key`` strips strings, so the two scan-root statements
  in ``neutrality/lint.py``'s ``_default_scan_roots`` share a key; a second
  built-in join on the sibling line is reported, not blessed
  (``test_duplicated_allowlisted_join_is_suppressed_once``).
* **Fail-on-stale.** An entry that does not resolve to exactly one site, or
  whose site holds no live built-in join, fails
  ``test_join_allowlist_entries_each_suppress_a_live_join``. A dead entry is
  deleted, never left to re-bless a future join at its old site
  (``test_new_join_at_formerly_pinned_line_is_caught``).

Reintroducing a similar pattern elsewhere requires a deliberate descriptor
naming the new site's rationale.
"""

from __future__ import annotations

import ast
import functools
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

import pytest

from tests.architectural._content_identity import (
    partition_findings,
    resolve_allowlist,
    with_blank_line_at_top,
    with_probe_above_statement,
)
from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor, composite_key
from tests.architectural.conftest import SourceFile

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The single-authority module: only file permitted to construct a built-in
#: path join (both `built_in_dir` and `built_in_root` live here -- C2.1/C3.1).
#: Relocated from ``src/doctrine/pack_paths.py`` by
#: charter-code-topology-01M152G1 (MAP-000 / CR-06).
_AUTHORITY_FILE = Path("src/charter/offering/pack_paths.py")

_ORG_TIER_RATIONALE = (
    "Org tier's own legacy nested-pack contract (<org_root>/<plural>/built-in), scanned after "
    "the flat org layout; not a built-in-tier reconstruction and does not call "
    'resolve_pack_root("built-in") / built_in_dir / built_in_root. See module docstring.'
)
_CALLER_ROOT_RATIONALE = (
    "Joins packs/built-in/missions against a caller-supplied root, not this installation's "
    "own built-in tier; routing through built_in_root() would substitute the installed tree "
    "for the caller's. See module docstring class 2."
)

#: Content-addressed allowlist of the known pre-existing non-authority joins --
#: see the module docstring "Known pre-existing exemptions" section for the full
#: rationale of each. Each descriptor must resolve to exactly one site and
#: suppress exactly one live join (fail-on-stale). Extending this requires a
#: deliberate, documented policy decision naming the new site and WHY it is not
#: a built-in-tier reconstruction.
_KNOWN_JOIN_SITES: tuple[ContentDescriptor, ...] = (
    ContentDescriptor(
        rel_path="src/charter/activation/kind_vocabulary.py",
        qualname="_org_scan_dirs",
        token_substring="legacy = flat /",
        occurrence=None,
        rationale=_ORG_TIER_RATIONALE,
    ),
    ContentDescriptor(
        rel_path="src/charter/activation/neutrality/lint.py",
        qualname="_default_scan_roots",
        token_substring="_iter_mission_scan_roots ( repo_root / / /",
        # The packs/built-in/missions and src/specify_cli/missions scan-root
        # statements are token-identical once strings are stripped; the first
        # is the built-in join.
        occurrence=0,
        rationale=(
            f"{_CALLER_ROOT_RATIONALE} Scans a caller-supplied repo_root, tmp_path-rooted in "
            "tests/charter/test_neutrality_lint.py::test_default_scan_roots_include_relocated_builtin_missions."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/template/manager.py",
        qualname="copy_specify_base_from_local",
        token_substring="missions_src = repo_root /",
        occurrence=None,
        rationale=(
            f"{_CALLER_ROOT_RATIONALE} Copies from a caller-supplied local dev checkout; pinned by "
            "tests/test_template/test_manager.py::test_copy_specify_base_from_local_copies_expected_assets."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/template/manager.py",
        qualname="get_local_repo_root._is_template_root",
        token_substring="return ( path /",
        occurrence=None,
        rationale=(f"{_CALLER_ROOT_RATIONALE} Content-sniffs a caller-supplied override_path / checkout root for a template tree."),
    ),
)


def _read_repo_source(rel_path: str) -> str:
    return (_REPO_ROOT / rel_path).read_text(encoding="utf-8")


@functools.cache
def _resolved_join_allowlist() -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """``_KNOWN_JOIN_SITES`` resolved against the real tree, lazily and once.

    Resolved on first use rather than at import, so a stale descriptor fails
    its test instead of turning into a collection error for the whole module.
    Callers must not mutate the returned counter.
    """
    return resolve_allowlist(_KNOWN_JOIN_SITES, _read_repo_source)


_RESOLVE_PACK_ROOT_BUILTIN = "resolve_pack_root"
_BUILT_IN_LITERAL = "built-in"
_BUILT_IN_ROOT_FUNC = "built_in_root"


def _is_resolve_pack_root_builtin_call(node: ast.AST) -> bool:
    """Return whether *node* is a bare ``resolve_pack_root("built-in")`` call."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == _RESOLVE_PACK_ROOT_BUILTIN
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == _BUILT_IN_LITERAL
    )


def _is_built_in_root_call(node: ast.AST) -> bool:
    """Return whether *node* is a bare ``built_in_root()`` call (no args).

    Covers both ``built_in_root()`` (``ast.Name`` callee, the normal
    ``from charter.offering.pack_paths import built_in_root`` import shape) and
    ``<module-or-obj>.built_in_root()`` (``ast.Attribute`` callee). The
    sanctioned bare-root seam is legitimate on its own (C3.1b); joining its
    result with ``/`` to reconstruct a per-kind path is the drift this limb
    exists to catch (see :func:`_is_builtin_root_seam_call`).
    """
    return (
        isinstance(node, ast.Call)
        and not node.args
        and not node.keywords
        and (
            (isinstance(node.func, ast.Name) and node.func.id == _BUILT_IN_ROOT_FUNC)
            or (isinstance(node.func, ast.Attribute) and node.func.attr == _BUILT_IN_ROOT_FUNC)
        )
    )


def _is_builtin_root_seam_call(node: ast.AST) -> bool:
    """Return whether *node* is either sanctioned bare-root seam call.

    ``resolve_pack_root("built-in")`` and ``built_in_root()`` are the two
    call shapes that hand back the built-in root without a per-kind segment
    -- either one becoming the base of a ``/`` join is the "reconstruct a
    per-kind path locally" drift this gate exists to catch.
    """
    return _is_resolve_pack_root_builtin_call(node) or _is_built_in_root_call(node)


def _names_bound_to_builtin_root_call(tree: ast.AST) -> set[str]:
    """Return every bare name assigned directly from a sanctioned root-seam call.

    Backs the variable-indirected limb (``x = resolve_pack_root("built-in")``
    or ``x = built_in_root()``; later ``x / …``) -- a ``BinOp``-only scan of
    the assignment's later use would miss this, since the call itself never
    appears at the join site.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_builtin_root_seam_call(node.value):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _join_base(node: ast.AST) -> ast.AST:
    """Walk down the left spine of a ``/``-chain to its base operand.

    ``a / b / c`` parses as ``BinOp(BinOp(a, b), c)``; the base is ``a``,
    reached by following ``.left`` through every nested ``Div`` ``BinOp``.
    """
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        node = node.left
    return node


def _find_builtin_joins(tree: ast.AST) -> set[int]:
    """Return the line numbers of every built-in path-join ``BinOp`` in *tree*.

    Flags (C3.1):
      * a ``resolve_pack_root("built-in") / …`` join, direct or
        variable-indirected;
      * a ``built_in_root() / …`` join, direct or variable-indirected -- the
        sanctioned bare-root seam reused to reconstruct a per-kind path
        locally, the most natural future drift once callers stop spelling
        ``resolve_pack_root("built-in")`` directly;
      * a ``<path> / "built-in"`` filesystem join (any base).
    Permits (C3.1b): a bare ``resolve_pack_root("built-in")`` or
    ``built_in_root()`` call that is never the base of a ``/`` join (the
    sanctioned seams themselves), and any bare ``"built-in"`` string literal
    that never appears as the right-hand operand of a ``/`` ``BinOp`` (the
    ~20 layer/provenance markers) -- both are structurally invisible to this
    join-only scan.
    """
    indirected_names = _names_bound_to_builtin_root_call(tree)
    offenders: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)):
            continue
        base = _join_base(node)
        is_direct_or_indirected = _is_builtin_root_seam_call(base) or (isinstance(base, ast.Name) and base.id in indirected_names)
        is_filesystem_join = isinstance(node.right, ast.Constant) and node.right.value == _BUILT_IN_LITERAL
        if is_direct_or_indirected or is_filesystem_join:
            offenders.add(node.lineno)
    return offenders


def _rel(path: Path) -> Path:
    return path.relative_to(_REPO_ROOT)


class _JoinSite(NamedTuple):
    """One built-in join finding: its content identity plus its current line."""

    key: CompositeKey
    lineno: int


@functools.cache
def _joins_in_source(source: str) -> frozenset[int]:
    """Parse *source* once per distinct text and return its built-in join lines.

    Cached on the source text so the drift tests, which rescan the whole tree
    with a single file mutated, only re-parse the mutated file.
    """
    return frozenset(_find_builtin_joins(ast.parse(source)))


def _join_sites(sources: Mapping[Path, str]) -> list[_JoinSite]:
    """Every built-in join outside the authority file, keyed by content identity."""
    sites: list[_JoinSite] = []
    for abs_path, source in sorted(sources.items()):
        rel = _rel(abs_path)
        if rel == _AUTHORITY_FILE:
            continue
        for lineno in sorted(_joins_in_source(source)):
            qualname, token_line = composite_key(source, lineno)
            sites.append(_JoinSite((rel.as_posix(), qualname, token_line), lineno))
    return sites


def _partition_join_sites(sources: Mapping[Path, str], allowed: Counter[CompositeKey]) -> tuple[list[_JoinSite], list[_JoinSite], Counter[CompositeKey]]:
    """Split the join findings in *sources* into ``(unexpected, suppressed, unused)``.

    Matching is delegated to :func:`partition_findings`: multiset, keyed by
    ``(rel_path, qualname, token_line)``, so one allowlist entry suppresses at
    most one finding.
    """
    sites = _join_sites(sources)
    unexpected, unused = partition_findings(((site.key, site) for site in sites), allowed)
    reported = set(unexpected)
    return unexpected, [site for site in sites if site not in reported], unused


def _resolve_from(sources: Mapping[Path, str]) -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """Resolve ``_KNOWN_JOIN_SITES`` against *sources* (possibly mutated), not the disk."""
    return resolve_allowlist(_KNOWN_JOIN_SITES, lambda rel: sources[_REPO_ROOT / rel])


def _join_partition(sources: Mapping[Path, str]) -> tuple[Counter[CompositeKey], Counter[CompositeKey]]:
    """The gate's detection path as content identities: ``(unexpected, suppressed)``.

    The allowlist is resolved from the same *sources* the scan reads, so a
    mutation that stops a descriptor resolving shows up as a changed partition.
    Multisets of composite keys (line numbers dropped), so two runs over
    sources that differ only by line drift compare equal.
    """
    allowed, _ = _resolve_from(sources)
    unexpected, suppressed, _ = _partition_join_sites(sources, allowed)
    return Counter(site.key for site in unexpected), Counter(site.key for site in suppressed)


def _sources_of(src_source_tree: Mapping[Path, SourceFile]) -> dict[Path, str]:
    """A private, mutable ``{abs_path: source}`` copy of the read-only session cache."""
    return {abs_path: entry.source for abs_path, entry in src_source_tree.items()}


def test_no_builtin_path_joins_outside_pack_paths_authority(
    src_source_tree: Mapping[Path, SourceFile],
) -> None:
    """C3.1/C3.1b/NFR-002: only ``pack_paths.py`` may join a built-in path.

    Any other ``src/`` module constructing a ``resolve_pack_root("built-in")
    / …`` join (direct or variable-indirected) or a ``<path> / "built-in"``
    filesystem join is a sixth resolver being reborn -- the exact regression
    class this gate exists to prevent. See the module docstring for the
    documented, content-addressed exceptions (``_KNOWN_JOIN_SITES``).
    """
    unexpected, _, _ = _partition_join_sites(_sources_of(src_source_tree), _resolved_join_allowlist()[0])

    if unexpected:
        details = "\n".join(f"  {site.key[0]}:{site.lineno}  [{site.key[1]}] {site.key[2]}" for site in unexpected)
        pytest.fail(
            "Found built-in path join(s) outside the charter.offering.pack_paths authority.\n"
            "Route through built_in_dir(kind) (per-kind) or built_in_root() (bare root)\n"
            'instead of composing resolve_pack_root("built-in") / ... or <path> / "built-in"\n'
            "locally -- that reintroduces a scattered, fail-open resolver "
            "(NFR-002).\n\n"
            f"Violations:\n{details}"
        )


# ---------------------------------------------------------------------------
# Allowlist integrity: fail-on-stale (FR-007) and line-drift tolerance (NFR-001)
# ---------------------------------------------------------------------------

#: The distinct files the join allowlist exempts a site in -- the drift test's
#: parameter set, derived from the allowlist itself.
_DRIFT_FILES: tuple[str, ...] = tuple(sorted({descriptor.rel_path for descriptor in _KNOWN_JOIN_SITES}))

#: Floor on ``_DRIFT_FILES`` so the drift proof cannot pass over a shrunken set.
_DRIFT_FILES_FLOOR = 3

#: Floor on the allowlist size so the stale test cannot pass over an empty list.
_JOIN_ALLOWLIST_FLOOR = 4


def _allowlist_count_for(rel_posix: str) -> int:
    return sum(1 for descriptor in _KNOWN_JOIN_SITES if descriptor.rel_path == rel_posix)


def _count_for(keys: Counter[CompositeKey], rel_posix: str) -> int:
    return sum(count for key, count in keys.items() if key[0] == rel_posix)


def test_join_allowlist_entries_each_suppress_a_live_join(
    src_source_tree: Mapping[Path, SourceFile],
) -> None:
    """FR-007 (hand-curated policy): every allowlist entry must suppress a live join.

    Resolving is not enough: an entry must resolve to exactly one site AND that
    site must hold a live built-in join, or it is dead weight that could
    silently re-bless a future violation.
    """
    allowed, errors = _resolved_join_allowlist()
    _, _, unused = _partition_join_sites(_sources_of(src_source_tree), allowed)
    checked = len(errors) + sum(allowed.values())
    stale = [f"  {descriptor.rel_path}::{descriptor.qualname}: {reason}" for descriptor, reason in errors]
    stale += [f"  {key[0]} [{key[1]}] {key[2]!r} suppresses no live built-in join" for key in sorted(unused)]
    assert checked == len(_KNOWN_JOIN_SITES) >= _JOIN_ALLOWLIST_FLOOR
    assert not stale, "Stale join allowlist entries (fix or delete them):\n" + "\n".join(stale)


def test_join_drift_files_meet_floor(src_source_tree: Mapping[Path, SourceFile]) -> None:
    """NFR-002: the drift parameter set is non-trivial and every file in it is live."""
    assert len(_DRIFT_FILES) >= _DRIFT_FILES_FLOOR
    _, suppressed = _join_partition(_sources_of(src_source_tree))
    empty = [rel for rel in _DRIFT_FILES if _count_for(suppressed, rel) < 1]
    assert not empty, f"Drift files with no suppressed join on the unmutated tree: {empty}"


def _probe_every_site(source: str, linenos: list[int]) -> str:
    """Insert a drift probe above each site's statement, bottom-up so lines stay valid."""
    for lineno in sorted(linenos, reverse=True):
        source = with_probe_above_statement(source, lineno)
    return source


@pytest.mark.parametrize("rel_posix", _DRIFT_FILES)
def test_join_allowlist_survives_line_drift(
    rel_posix: str,
    src_source_tree: Mapping[Path, SourceFile],
) -> None:
    """NFR-001: line drift above or around the exempted sites changes nothing the gate sees.

    Two mutations of *rel_posix*, each rescanned and re-resolved from the
    mutated mapping: (i) a blank line at the top of the file, (ii) a
    ``# drift-probe`` / ``pass`` pair above every exempted site's statement.
    """
    sources = _sources_of(src_source_tree)
    baseline = _join_partition(sources)
    expected = _allowlist_count_for(rel_posix)
    assert _count_for(baseline[1], rel_posix) == expected, (
        f"{rel_posix}: {_count_for(baseline[1], rel_posix)} suppressed join(s) on the unmutated tree, expected {expected}"
    )

    target = _REPO_ROOT / rel_posix
    _, suppressed_sites, _ = _partition_join_sites(sources, _resolve_from(sources)[0])
    site_lines = [site.lineno for site in suppressed_sites if site.key[0] == rel_posix]
    mutations = {
        "blank line at top": with_blank_line_at_top(sources[target]),
        "probe above each site": _probe_every_site(sources[target], site_lines),
    }
    for label, mutated_source in mutations.items():
        mutated = dict(sources)
        mutated[target] = mutated_source
        assert _resolve_from(mutated)[1] == [], f"{rel_posix} ({label}): an allowlist descriptor stopped resolving"
        drifted = _join_partition(mutated)
        assert drifted == baseline, f"{rel_posix} ({label}): drift changed the gate's partition.\nbefore: {baseline}\nafter:  {drifted}"
        assert _count_for(drifted[1], rel_posix) == expected


#: The formerly pinned ``src/kernel/paths.py`` site (a dead ``(file, lineno)``
#: pin: ``if is_windows():`` inside ``get_kittify_home``). Located by content,
#: not by line number, so an edit above it cannot shift the probe into a comment.
_FORMER_PIN_FILE = "src/kernel/paths.py"
_FORMER_PIN_ANCHOR = "    if is_windows():\n"


def _former_pin_line(source: str) -> int:
    """Return the 1-based line of the formerly pinned ``if is_windows():`` site."""
    return source.splitlines(keepends=True).index(_FORMER_PIN_ANCHOR) + 1


def test_new_join_at_formerly_pinned_line_is_caught(
    src_source_tree: Mapping[Path, SourceFile],
) -> None:
    """A dead line pin must never re-bless a new violation planted at that line."""
    sources = _sources_of(src_source_tree)
    target = _REPO_ROOT / _FORMER_PIN_FILE
    pin_line = _former_pin_line(sources[target])
    lines = sources[target].splitlines(keepends=True)
    planted = '    _probe = Path("root") / "built-in"\n'
    lines.insert(pin_line - 1, planted)
    mutated_source = "".join(lines)
    sources[target] = mutated_source

    planted_key = (_FORMER_PIN_FILE, *composite_key(mutated_source, pin_line))
    unexpected, suppressed = _join_partition(sources)
    assert planted_key in unexpected, f"planted join at {_FORMER_PIN_FILE}:{pin_line} was not reported (suppressed: {planted_key in suppressed})"


def test_duplicated_allowlisted_join_is_suppressed_once(
    src_source_tree: Mapping[Path, SourceFile],
) -> None:
    """Multiset on real data: a copy of an allowlisted join is reported, not blessed.

    ``neutrality/lint.py``'s exempted join is token-identical to its sibling
    statement once strings are stripped; duplicating it in memory yields two
    findings with one composite key, and the single entry may suppress only one.
    """
    rel_posix = "src/charter/activation/neutrality/lint.py"
    sources = _sources_of(src_source_tree)
    target = _REPO_ROOT / rel_posix
    _, suppressed_sites, _ = _partition_join_sites(sources, _resolve_from(sources)[0])
    (site,) = [s for s in suppressed_sites if s.key[0] == rel_posix]

    lines = sources[target].splitlines(keepends=True)
    lines.insert(site.lineno, lines[site.lineno - 1])
    sources[target] = "".join(lines)

    unexpected, suppressed = _join_partition(sources)
    assert unexpected[site.key] == 1
    assert suppressed[site.key] == 1


def test_negative_bite_direct_and_variable_indirected_joins_are_caught() -> None:
    """NFR-002 anti-vacuity: prove the gate actually flags both join limbs.

    Without this, a gate that always passes (e.g. an empty offender set from a
    typo'd AST match) would be indistinguishable from a correct, strict gate.
    Two synthetic snippets are parsed directly (never written to ``src/``):
    one direct ``resolve_pack_root("built-in") / …`` join, one
    variable-indirected join. Both must be flagged.
    """
    direct_source = (
        "from charter.offering.pack_paths import resolve_pack_root\n\ndef sneaky_direct(kind):\n    return resolve_pack_root('built-in') / kind.plural\n"
    )
    indirected_source = (
        "from charter.offering.pack_paths import resolve_pack_root\n"
        "\n"
        "def sneaky_indirected(kind):\n"
        "    root = resolve_pack_root('built-in')\n"
        "    return root / kind.plural\n"
    )
    filesystem_join_source = "def sneaky_filesystem_join(some_root, kind):\n    return some_root / kind.plural / 'built-in'\n"

    direct_hits = _find_builtin_joins(ast.parse(direct_source))
    indirected_hits = _find_builtin_joins(ast.parse(indirected_source))
    filesystem_hits = _find_builtin_joins(ast.parse(filesystem_join_source))

    assert direct_hits, "Direct resolve_pack_root('built-in') / ... join must be flagged"
    assert indirected_hits, "Variable-indirected join (x = resolve_pack_root('built-in'); x / ...) must be flagged"
    assert filesystem_hits, "<path> / 'built-in' filesystem join must be flagged"

    # And the permitted forms must NOT be flagged (proves the gate is
    # join-only, not a constant-scan -- C3.1b).
    bare_root_call_source = (
        "from charter.offering.pack_paths import resolve_pack_root\n\ndef permitted_bare_root_call():\n    return resolve_pack_root('built-in')\n"
    )
    bare_marker_source = "def permitted_bare_marker(layer):\n    return {'built-in': 'built-in', 'org': 'org'}.get(layer, layer)\n"
    assert not _find_builtin_joins(ast.parse(bare_root_call_source))
    assert not _find_builtin_joins(ast.parse(bare_marker_source))


def test_negative_bite_built_in_root_call_joins_are_caught() -> None:
    """NFR-002 anti-vacuity, ``built_in_root()``-join limb (FOLD 6 widening).

    The most natural future drift is not re-spelling
    ``resolve_pack_root("built-in")`` -- it is reusing the *sanctioned*
    ``built_in_root()`` seam and then joining a per-kind segment onto it
    locally, e.g. ``built_in_root() / kind.plural``, instead of calling
    :func:`charter.offering.pack_paths.built_in_dir`. Both the direct and
    variable-indirected shapes must be flagged, while a bare
    ``built_in_root()`` call -- the sanctioned form itself -- must stay
    permitted (mirrors the ``resolve_pack_root("built-in")`` proof above).
    """
    direct_source = "from charter.offering.pack_paths import built_in_root\n\ndef sneaky_direct(kind):\n    return built_in_root() / kind.plural\n"
    indirected_source = (
        "from charter.offering.pack_paths import built_in_root\n\ndef sneaky_indirected(kind):\n    root = built_in_root()\n    return root / kind.plural\n"
    )
    attribute_call_source = "from doctrine import pack_paths\n\ndef sneaky_attribute_call(kind):\n    return pack_paths.built_in_root() / kind.plural\n"

    direct_hits = _find_builtin_joins(ast.parse(direct_source))
    indirected_hits = _find_builtin_joins(ast.parse(indirected_source))
    attribute_hits = _find_builtin_joins(ast.parse(attribute_call_source))

    assert direct_hits, "Direct built_in_root() / ... join must be flagged"
    assert indirected_hits, "Variable-indirected join (x = built_in_root(); x / ...) must be flagged"
    assert attribute_hits, "Attribute-call join (mod.built_in_root() / ...) must be flagged"

    # The sanctioned bare call itself -- with no join -- must stay permitted.
    bare_built_in_root_source = "from charter.offering.pack_paths import built_in_root\n\ndef permitted_bare_built_in_root():\n    return built_in_root()\n"
    assert not _find_builtin_joins(ast.parse(bare_built_in_root_source))


# ---------------------------------------------------------------------------
# C3.2 / NFR-003 / NFR-005 -- positive per-kind coverage + the #3091 marker
# ---------------------------------------------------------------------------

#: The 9 kinds WITH a shipped `packs/built-in/<plural>/` content directory
#: (derived from `has_built_in_content_dir`, asserted below -- not hand-listed
#: independently of that attribute).

#: #3091 marker (NFR-005): the DERIVED complement of `_CONTENT_DIR_KINDS` --
#: `{mission_step_contract, template, anti_pattern}` -- package-resource/
#: graph-only kinds with no shipped content dir (relocation deferred to
#: mission #3091). This assertion is the single place that must be edited if
#: a fourth kind joins the carve-out, or if one of these three kinds later
#: GAINS a content dir: either change is a deliberate, reviewed edit here, not
#: a silent drift, because the set below is compared against the LIVE
#: `ArtifactKind` complement rather than repeated as an independent literal.


# ---------------------------------------------------------------------------
# C3.3 / NFR-003 -- anti-vacuity
# ---------------------------------------------------------------------------
