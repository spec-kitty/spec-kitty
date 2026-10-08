"""Gate 2 (FR-002/FR-008/FR-007, WP09): zero *unwrapped* raw
``charter.offering.service.CharterOfferingService`` construction outside the charter sole door.

Mission ``charter-sole-door-bypass-closure-01KZ3WAA``, WP09 / T038. Sibling of
Gate 1 (``test_charter_sole_door_agent_profile_repository.py``); both import
the shared qualname-resolution machinery from
:mod:`tests.architectural._sole_door_scan` rather than forking it (landing-fold
gate hardening — previously Gate 2 imported these primitives from Gate 1's
``test_`` module directly; see that shared module's docstring for why library
code cannot live inside a ``test_`` module).

Why this gate cannot be a text match
-------------------------------------
There are **two different classes** this gate must tell apart (until #3732
they shared the simple name ``DoctrineService``; WP19 renamed the raw one to
``CharterOfferingService`` and WP20 the wrapper to ``ActiveCharterService``):

* ``charter.offering.service.CharterOfferingService`` — the raw, ungated inner service. Direct
  construction of this outside the sole door is the FR-002 bypass.
* ``charter.activation.resolver.ActiveCharterService`` — the activation-aware wrapper. Its
  construction, *including* the ``pack_context=None`` unfiltered-diagnostic
  form, is the sanctioned fix FR-002 asked for.

Worse, live sites import them under ``as``-aliases in the *same* function
(e.g. ``ActiveCharterService as ActivationAware``), so alias spellings offer a
text-matcher nothing to key on reliably. This
gate resolves each call site's bound name to a canonical
``__module__``.``__qualname__`` via Gate 1's resolver, and only then decides.
:func:`test_wrapper_constructions_are_never_flagged_as_raw` pins the
discrimination against the live tree.

The two policies this module enforces
--------------------------------------
**Policy A — exclusion-free zero tolerance (the real invariant).** No raw
``charter.offering.service.CharterOfferingService`` may escape *unwrapped*. Every acquisition
outside the structural authorities must flow immediately — inline as an
argument, or through one local assignment consumed in the same scope — into a
``charter.activation.resolver.ActiveCharterService(...)`` call. This assertion has **no
allow-list at all** (C-002) and is what FR-002 actually established: "Eliminate
the *unwrapped* raw ... construction sites ... routing each through
``charter.activation.resolver.ActiveCharterService``".

Policy A covers **two acquisition routes**, because constructing the class is
not the only way to get one. WP09's sweep found that
``specify_cli/charter_runtime/lint/checks/org_layer.py`` obtains an unwrapped
raw service by *calling* the sanctioned raw builder,
``charter.activation.active_charter_service_builder._build_offering_service`` — WP01's approved,
documented design ("the ONE function in this codebase permitted to construct a
raw ``charter.offering.service.CharterOfferingService``"). That caller wraps correctly today,
but a construction-only gate would not have noticed a second caller that failed
to. Both routes are therefore policed. Charter-internal builder callers are
deliberately exempt: the builder's own docstring records that five of them
consume the unwrapped service on purpose, with an unchanged return type.

**Policy B — construction locality, with named composite-key exclusions.**
NFR-001 additionally phrases the target as "zero matches for
``charter.offering.service.CharterOfferingService`` ... outside ``src/charter/activation/resolver.py`` and
the one unified builder". Six live sites construct the raw service locally and
wrap it on the next statement, which satisfies FR-002 but not NFR-001's stricter
locality phrasing. Each is enumerated below as a composite-key exclusion, and
**each exclusion is conditional on Policy A still holding at that exact site** —
:func:`check_locality_gate` only honours an exclusion whose site is
machine-verified as immediately wrapped. Deleting the wrap at an excluded site
therefore reds the gate; the allow-list is not a blind carve-out.

Structural exemptions (file/directory keyed, never line keyed)
--------------------------------------------------------------
Imported from Gate 1: ``src/charter/activation/resolver.py`` (the sole door),
``src/charter/activation/active_charter_service_builder.py`` (the ONE unified builder — its
``_build_offering_service`` is documented by ``org_layer.py`` as "the ONE
function in this codebase permitted to construct a raw
``charter.offering.service.CharterOfferingService``"), and the ``src/charter/offering/`` layer that
owns the class.

The six named locality exclusions, and their provenance
--------------------------------------------------------
Pre-sanctioned by spec.md FR-002 / C-002 ("the ``_doctrine_collect.py``
diagnostic sites' explicit unfiltered mode ... named, reasoned exclusions"):

1. ``_doctrine_collect.py`` / ``_collect_profile_health``
2. ``_doctrine_collect.py`` / ``_collect_glossary_pack_health``
3. ``_doctrine_collect.py`` / ``_collect_doctrine_collisions``
4. ``_doctrine_collect.py`` / ``_build_selection_block``

   All four need the unfiltered, all-layer view so ``doctor``/health output is
   not silently narrowed for de-activated packs; all four wrap with an explicit
   ``pack_context=None``. :func:`test_unfiltered_diagnostic_sites_pass_none_pack_context`
   verifies that claim mechanically rather than trusting the comment.

**NOT pre-sanctioned — surfaced by WP09's sweep as escalated C-002 findings,
reported to the operator rather than silently allowlisted:**

5. ``cli/commands/charter/pack_asset.py`` / ``_build_asset_repository`` — WP03
   (approved) migrated this site into exactly the FR-002-prescribed shape (build
   raw, wrap immediately, real ``PackContext`` when a repo root exists), and its
   docstring says so explicitly. It satisfies FR-002 and Policy A but not
   NFR-001's locality phrasing. FR-002 lists this site among the six it set out
   to fix, so this is a *spec-internal tension* between FR-002's remedy and
   NFR-001's phrasing — not an unresolved bypass.
6. ``charter/activation/compiler.py`` / ``_default_active_charter_service`` — same shape and same
   provenance (WP03, approved). The ``repo_root is not None`` path already
   routes through the unified builder; only the legacy ``repo_root is None``
   branch, which has no config from which to source a ``PackContext``,
   constructs locally and wraps with the implicit ``pack_context=None``.

Both are recorded here, in WP09's Activity Log, and in the WP's hand-off summary
so the operator can decide whether to fold them onto the builder later. Neither
was quietly absorbed.

Relationship to sibling gates — no duplicated assertions
---------------------------------------------------------
``test_org_activation_seam.py`` polices raw ``org_dirs=`` splices past the
activation seam; ``test_layer_rules.py`` polices package-level import direction;
Gate 5 (``test_charter_sole_door_inner_reacharound.py``) polices ``._inner``
reach-around on an already-constructed wrapper. None of them resolves the
*construction* class, which is this gate's whole subject.
"""

from __future__ import annotations

import ast
import functools
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ratchet_keys import CompositeKey, ContentDescriptor
from tests.architectural._sole_door_scan import (
    REPO_ROOT,
    SRC_ROOT,
    ConstructionSite,
    FileScan,
    ScanResult,
    enclosing_scope,
    iter_source_files,
    rel_to_repo,
    resolve_exclusion_keys,
    scan_file_constructions,
    scratch_scan,
    structurally_exempt,
)

pytestmark = pytest.mark.architectural

#: The raw, ungated inner service. Constructing this outside the sole door is
#: the FR-002 bypass. Named verbatim by spec.md NFR-001.
RAW_OFFERING_SERVICE_QUALNAME = "charter.offering.service.CharterOfferingService"

#: The activation-aware wrapper — the sanctioned construction, including its
#: ``pack_context=None`` unfiltered-diagnostic form.
ACTIVE_CHARTER_SERVICE_QUALNAME = "charter.activation.resolver.ActiveCharterService"

#: The ONE function permitted to construct the raw service. Calling it is the
#: other way to *obtain* an unwrapped raw service — see
#: :data:`RAW_BUILDER_QUALNAME`'s note below.
RAW_BUILDER_QUALNAME = "charter.activation.active_charter_service_builder._build_offering_service"

#: Simple names worth canonicalising: the raw class (``CharterOfferingService``)
#: and the wrapper (``ActiveCharterService``), each possibly under an ``as``-alias,
#: which is precisely why the gate must canonicalise rather than text-match.
#: ``_build_offering_service`` is included because obtaining the raw service
#: from the sanctioned builder is the residual second route to an unwrapped
#: inner service (see :func:`check_unwrapped_escape_gate`).
CHARTER_SERVICE_CANDIDATE_NAMES = frozenset({"CharterOfferingService", "ActiveCharterService", "_build_offering_service"})

_PACK_CONTEXT_KWARG = "pack_context"

#: Constructions inside the charter layer are the layer's own business; the
#: builder's docstring records that charter-internal callers deliberately use
#: the unwrapped service (unchanged return type). The builder-call rule
#: therefore applies only outside this prefix.
CHARTER_LAYER_PREFIX = "src/charter/"


# =========================================================================== #
# Wrap-flow analysis: does a raw construction escape unwrapped?
# =========================================================================== #


@dataclass(frozen=True)
class WrapVerdict:
    """Whether one raw construction is immediately wrapped, and how."""

    wrapped: bool
    #: ``"inline"``, ``"assigned"``, or ``""`` when unwrapped.
    form: str
    #: ``True`` when the wrapping call passes an explicit ``pack_context=None``.
    explicit_none_pack_context: bool


def _wrapper_calls_in_scope(scope: ast.AST, scan: FileScan, wrapper_sites: set[int]) -> list[ast.Call]:
    """Every ``charter.activation.resolver.ActiveCharterService(...)`` call inside *scope*."""
    return [
        node for node in ast.walk(scope) if isinstance(node, ast.Call) and id(node) in wrapper_sites and enclosing_scope(scan.parents, node, scan.tree) is scope
    ]


def _assigned_target_name(call: ast.Call, scan: FileScan) -> str | None:
    """Local name a construction call is assigned to, if it is a simple assign."""
    parent = scan.parents.get(id(call))
    if not isinstance(parent, ast.Assign) or len(parent.targets) != 1:
        return None
    target = parent.targets[0]
    return target.id if isinstance(target, ast.Name) else None


def _passes_name(call: ast.Call, name: str) -> bool:
    return any(isinstance(arg, ast.Name) and arg.id == name for arg in [*call.args, *(kw.value for kw in call.keywords)])


def _explicit_none_pack_context(call: ast.Call) -> bool:
    return any(kw.arg == _PACK_CONTEXT_KWARG and isinstance(kw.value, ast.Constant) and kw.value.value is None for kw in call.keywords)


def _wrap_verdict_for(raw_call: ast.Call, scan: FileScan, wrapper_sites: set[int]) -> WrapVerdict:
    """Decide whether *raw_call*'s result reaches a wrapper construction.

    Two accepted shapes, both present in the live tree:

    * **inline** — the raw call is itself an argument to the wrapper call
      (``compiler.py``'s ``_ActivationAware(_Raw(project_root=None))``).
    * **assigned** — the raw call is assigned to one local name that a wrapper
      call in the same scope consumes (``inner = Raw(...)`` then
      ``Wrapper(inner, pack_context=...)`` — the shape used by
      ``_doctrine_collect.py`` and ``charter/pack_asset.py``).

    Deliberately narrow: a raw service threaded through a dict, a return value,
    or another module is NOT accepted as wrapped. Narrowness here errs toward
    RED, which is the correct bias for a zero-tolerance gate.
    """
    parent = scan.parents.get(id(raw_call))
    if isinstance(parent, ast.Call) and id(parent) in wrapper_sites:
        return WrapVerdict(True, "inline", _explicit_none_pack_context(parent))

    name = _assigned_target_name(raw_call, scan)
    if name is None:
        return WrapVerdict(False, "", False)
    scope = enclosing_scope(scan.parents, raw_call, scan.tree)
    for wrapper_call in _wrapper_calls_in_scope(scope, scan, wrapper_sites):
        if _passes_name(wrapper_call, name):
            return WrapVerdict(True, "assigned", _explicit_none_pack_context(wrapper_call))
    return WrapVerdict(False, "", False)


#: A raw service obtained by *constructing* ``charter.offering.service.CharterOfferingService``.
KIND_CONSTRUCTION = "construction"
#: A raw service obtained by *calling* the sanctioned raw builder.
KIND_BUILDER_CALL = "builder_call"


@dataclass(frozen=True)
class RawSite:
    """A site that obtains an unwrapped raw service, plus its wrap verdict."""

    site: ConstructionSite
    verdict: WrapVerdict
    kind: str = KIND_CONSTRUCTION

    @property
    def key(self) -> CompositeKey:
        return self.site.key


#: Both watched classes, classified in ONE parse so the resulting ``ast.Call``
#: node identities are directly comparable. Two separate parses would produce
#: two disjoint sets of node objects, and matching them back up by
#: ``(lineno, qualname)`` is ambiguous exactly where it matters —
#: ``charter/activation/compiler.py`` constructs the wrapper and the raw service on the
#: same source line.
DOCTRINE_SERVICE_TARGETS = frozenset(
    {
        RAW_OFFERING_SERVICE_QUALNAME,
        ACTIVE_CHARTER_SERVICE_QUALNAME,
        RAW_BUILDER_QUALNAME,
    }
)

#: Canonical qualname -> the kind of raw-service acquisition it represents.
_RAW_KIND_BY_QUALNAME = {
    RAW_OFFERING_SERVICE_QUALNAME: KIND_CONSTRUCTION,
    RAW_BUILDER_QUALNAME: KIND_BUILDER_CALL,
}


def scan_file_raw_sites(path: Path, rel_path: str) -> tuple[list[RawSite], ScanResult]:
    """Every site in one file that obtains an unwrapped raw service.

    Covers both acquisition routes — constructing
    ``charter.offering.service.CharterOfferingService`` and calling the sanctioned raw builder
    ``charter.activation.active_charter_service_builder._build_offering_service`` — each with its
    wrap verdict. The returned :class:`ScanResult` carries only those sites;
    wrapper constructions inform the verdicts and are never reported as
    violations.
    """
    scan = scan_file_constructions(
        path,
        rel_path,
        candidate_names=CHARTER_SERVICE_CANDIDATE_NAMES,
        target_qualnames=DOCTRINE_SERVICE_TARGETS,
    )
    if scan is None:
        return [], ScanResult([], [])

    wrapper_sites = {id(call) for call, site in scan.matches if site.canonical == ACTIVE_CHARTER_SERVICE_QUALNAME}
    raw_sites = [
        RawSite(
            site,
            _wrap_verdict_for(call, scan, wrapper_sites),
            _RAW_KIND_BY_QUALNAME[site.canonical],
        )
        for call, site in scan.matches
        if site.canonical in _RAW_KIND_BY_QUALNAME
    ]
    return raw_sites, ScanResult([raw.site for raw in raw_sites], scan.result.unresolved)


@functools.cache
def raw_service_census() -> tuple[tuple[RawSite, ...], ScanResult]:
    """Every raw-service construction under ``src/``, with wrap verdicts.

    Memoised for the test session (pure function of an unchanging tree).
    """
    sites: list[RawSite] = []
    unresolved: list[ConstructionSite] = []
    resolved: list[ConstructionSite] = []
    for path in iter_source_files(SRC_ROOT):
        rel_path = rel_to_repo(path)
        file_sites, result = scan_file_raw_sites(path, rel_path)
        sites.extend(file_sites)
        resolved.extend(result.sites)
        unresolved.extend(result.unresolved)
    return tuple(sites), ScanResult(resolved, unresolved)


# =========================================================================== #
# Policy A — exclusion-free zero tolerance on an *unwrapped* escape
# =========================================================================== #


def _policy_a_applies(raw: RawSite) -> bool:
    """Whether Policy A governs *raw*'s acquisition site.

    Construction sites are governed everywhere except the structural
    authorities. Builder *calls* are governed only outside ``src/charter/``:
    ``_build_offering_service``'s own docstring records that charter-internal
    callers deliberately consume the unwrapped service (five such callers, whose
    return type must stay unchanged), so policing them would contradict WP01's
    approved, documented design.
    """
    if raw.kind == KIND_BUILDER_CALL:
        return not raw.site.rel_path.startswith(CHARTER_LAYER_PREFIX)
    return not structurally_exempt(raw.site.rel_path)


def check_unwrapped_escape_gate(raw_sites: tuple[RawSite, ...]) -> list[str]:
    """Violations for raw services that escape without a wrapper. No allow-list.

    Covers **both** acquisition routes. The builder-call arm closes a residual
    vector WP09's sweep found: ``org_layer.py`` obtains an unwrapped raw service
    by calling ``charter.activation.active_charter_service_builder._build_offering_service``
    rather than constructing the class, so a construction-only gate would not
    have noticed if a second such caller failed to wrap it. Today the one live
    caller wraps correctly; this keeps that true.
    """
    verbs = {
        KIND_CONSTRUCTION: "constructs a raw charter.offering.service.CharterOfferingService",
        KIND_BUILDER_CALL: (
            "obtains a raw charter.offering.service.CharterOfferingService from charter.activation.active_charter_service_builder._build_offering_service"
        ),
    }
    return [
        f"{raw.site.describe()} {verbs[raw.kind]} that is NOT immediately wrapped "
        "in charter.activation.resolver.ActiveCharterService (FR-002) — the unwrapped inner "
        "service must never escape its acquisition site"
        for raw in raw_sites
        if _policy_a_applies(raw) and not raw.verdict.wrapped
    ]


# =========================================================================== #
# Policy B — construction locality, with conditional named exclusions
# =========================================================================== #

#: Named, individually-justified locality exclusions — composite-key anchored
#: (never a whole file, never a line number; see Gate 1's module docstring for
#: why the key is ``(file, qualname, token)``). Read this module's docstring
#: before touching this tuple.
RAW_LOCALITY_EXCLUSIONS: tuple[ContentDescriptor, ...] = (
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/_doctrine_collect.py",
        qualname="_collect_profile_health",
        token_substring="CharterOfferingService (",
        occurrence=None,
        rationale=(
            "FR-002 pre-sanctioned unfiltered-diagnostic site (agent-profile "
            "health): needs the all-layer view so doctor output is not silently "
            "narrowed for de-activated packs, so it wraps with an explicit "
            "pack_context=None. C-002 names these four as reasoned exclusions "
            "from the bypass count, not exceptions to it."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/_doctrine_collect.py",
        qualname="_collect_glossary_pack_health",
        token_substring="CharterOfferingService (",
        occurrence=None,
        rationale=(
            "FR-002 pre-sanctioned unfiltered-diagnostic site (glossary-pack "
            "health): same all-layer requirement and same explicit "
            "pack_context=None unfiltered mode as the sibling profile-health "
            "collector. C-002 reasoned exclusion, not an exception."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/_doctrine_collect.py",
        qualname="_collect_doctrine_collisions",
        token_substring="CharterOfferingService (",
        occurrence=None,
        rationale=(
            "FR-002 pre-sanctioned unfiltered-diagnostic site (cross-layer "
            "collision detection): collision detection is meaningless on a "
            "filtered catalog, so it wraps with an explicit pack_context=None. "
            "C-002 reasoned exclusion, not an exception."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/_doctrine_collect.py",
        qualname="_build_selection_block",
        token_substring="CharterOfferingService (",
        occurrence=None,
        rationale=(
            "FR-002 pre-sanctioned unfiltered-diagnostic site (provenance "
            "lookup for the selection block): needs the unfiltered provenance "
            "view, wrapped with an explicit pack_context=None. C-002 reasoned "
            "exclusion, not an exception."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/charter/pack_asset.py",
        qualname="_build_asset_repository",
        token_substring="CharterOfferingService (",
        occurrence=None,
        rationale=(
            "ESCALATED C-002 FINDING (WP09 sweep), reported not absorbed. WP03 "
            "migrated this site into exactly the shape FR-002 prescribed - "
            "build raw, wrap immediately in charter.activation.resolver.ActiveCharterService "
            "with a real PackContext when a repo root exists - and its own "
            "docstring states that intent. It therefore satisfies FR-002 and "
            "Policy A above but not NFR-001's stricter locality phrasing. FR-002 "
            "itself lists this site among the six it set out to fix, so this is "
            "a spec-internal tension between FR-002's remedy and NFR-001's "
            "wording, not an unresolved bypass. Folding it onto the unified "
            "builder is an operator decision outside WP09's write scope."
        ),
    ),
    ContentDescriptor(
        rel_path="src/charter/activation/compiler.py",
        qualname="_default_active_charter_service",
        token_substring="CharterOfferingService ( project_root = None )",
        occurrence=None,
        rationale=(
            "ESCALATED C-002 FINDING (WP09 sweep), reported not absorbed. Same "
            "provenance and shape as the charter/pack_asset.py entry: WP03 "
            "(approved) routes the repo_root-bearing path through the unified "
            "builder and only the legacy repo_root-is-None branch - which has no "
            "config from which to source a PackContext - constructs locally and "
            "wraps inline with the implicit pack_context=None. Satisfies FR-002 "
            "and Policy A, not NFR-001's locality phrasing. Operator decision, "
            "outside WP09's write scope."
        ),
    ),
)


def check_locality_gate(raw_sites: tuple[RawSite, ...]) -> list[str]:
    """Violations for raw constructions outside the sole door and the builder.

    An exclusion is honoured **only** while its site remains immediately
    wrapped: dropping the wrap turns the excluded site back into a violation, so
    the allow-list cannot be used to sanction a future unwrapped escape.
    """
    excluded = resolve_exclusion_keys(RAW_LOCALITY_EXCLUSIONS)
    violations: list[str] = []
    for raw in raw_sites:
        # Locality is about who may *construct* the class. A builder call is by
        # definition routed through the sanctioned authority, so it is Policy
        # A's subject only.
        if raw.kind != KIND_CONSTRUCTION or structurally_exempt(raw.site.rel_path):
            continue
        if raw.key in excluded and raw.verdict.wrapped:
            continue
        suffix = (
            " (its named locality exclusion no longer applies: the immediate charter.activation.resolver.ActiveCharterService wrap is gone)"
            if raw.key in excluded
            else ""
        )
        violations.append(
            f"{raw.site.describe()} constructs charter.offering.service.CharterOfferingService "
            "outside src/charter/activation/resolver.py and the one unified builder "
            f"(NFR-001) — route it through "
            f"charter.activation.active_charter_service_builder.build_active_charter_service{suffix}"
        )
    return violations


# =========================================================================== #
# Anti-vacuity: the scan sees the tree and discriminates the two classes
# =========================================================================== #


def test_raw_census_finds_the_unified_builders_own_constructions() -> None:
    """The scanner must actually resolve raw constructions.

    ``charter/activation/active_charter_service_builder.py``'s ``_build_offering_service`` is
    documented as the ONE function permitted to construct the raw service; if
    the census cannot see *that*, the gate's zero-violation assertion is
    vacuous.
    """
    raw_sites, result = raw_service_census()
    constructions = [raw for raw in raw_sites if raw.kind == KIND_CONSTRUCTION]
    builder_sites = [raw for raw in constructions if raw.site.rel_path == "src/charter/activation/active_charter_service_builder.py"]
    assert builder_sites, [raw.site.describe() for raw in constructions]
    assert all(site.canonical in (RAW_OFFERING_SERVICE_QUALNAME, RAW_BUILDER_QUALNAME) for site in result.sites)
    assert len(constructions) >= 8, [raw.site.describe() for raw in constructions]


def test_no_unresolved_doctrine_service_candidates() -> None:
    """No ``CharterOfferingService(`` / ``ActiveCharterService(``-shaped call may go unresolved.

    An unresolved candidate is a blind spot the gate could not classify as
    either class; treating it as clean is how a zero-violation gate goes
    vacuous.
    """
    _, result = raw_service_census()
    assert result.unresolved == [], [s.describe() for s in result.unresolved]


# =========================================================================== #
# The gates
# =========================================================================== #


def test_no_unwrapped_raw_doctrine_service_escapes_anywhere() -> None:
    """Policy A — zero tolerance, **no allow-list of any kind** (C-002)."""
    violations = check_unwrapped_escape_gate(raw_service_census()[0])
    assert violations == [], "\n".join(violations)


def test_no_raw_doctrine_service_construction_outside_the_sole_door() -> None:
    """Policy B — locality, honouring only the six named, wrap-verified sites."""
    violations = check_locality_gate(raw_service_census()[0])
    assert violations == [], "\n".join(violations)


# =========================================================================== #
# NFR-003 self-mutation proofs — function-local / nested scope injection.
# =========================================================================== #


def _raw_scratch(tmp_path: Path, rel_name: str, source: str) -> tuple[list[RawSite], ScanResult]:
    scratch_scan(
        tmp_path,
        rel_name,
        source,
        candidate_names=CHARTER_SERVICE_CANDIDATE_NAMES,
        target_qualnames=DOCTRINE_SERVICE_TARGETS,
    )
    return scan_file_raw_sites(tmp_path / Path(rel_name).name, rel_name)


def test_injected_unwrapped_function_local_raw_service_is_flagged(tmp_path: Path) -> None:
    """Policy A bites on a function-local, unwrapped raw construction.

    The exact pre-mission bypass shape: a function-local import of the raw
    service, constructed and returned bare. Injected at function-local scope,
    never module-level-only (NFR-003).
    """
    raw_sites, result = _raw_scratch(
        tmp_path,
        "regressed_unwrapped.py",
        "def build(project_root):\n"
        "    from charter.offering.service import CharterOfferingService\n"
        "\n"
        "    return CharterOfferingService(project_root=project_root)\n",
    )
    assert result.unresolved == [], [s.describe() for s in result.unresolved]
    assert [raw.site.qualname for raw in raw_sites] == ["build"], [raw.site.describe() for raw in raw_sites]
    assert raw_sites[0].site.qualname == "build"
    assert not raw_sites[0].verdict.wrapped

    escapes = check_unwrapped_escape_gate(tuple(raw_sites))
    assert escapes, "Policy A must bite on an unwrapped raw construction"
    assert "regressed_unwrapped.py" in escapes[0]
    assert "build" in escapes[0]
    assert check_locality_gate(tuple(raw_sites)), "Policy B must bite too"


def test_wrapper_only_construction_is_not_flagged(tmp_path: Path) -> None:
    """True negative: constructing only the wrapper is never a violation.

    The unfiltered-diagnostic form ``charter.activation.resolver.ActiveCharterService(inner,
    pack_context=None)`` shared the simple name ``DoctrineService`` with the
    forbidden raw construction until #3732 renamed both classes; NFR-001
    calls this out as the exact reason a name-only gate cannot work, and the
    gate still canonicalises rather than trusting either name.
    """
    raw_sites, result = _raw_scratch(
        tmp_path,
        "wrapper_only.py",
        "def build(inner):\n"
        "    from charter.activation.resolver import ActiveCharterService as ActivationAware\n"
        "\n"
        "    return ActivationAware(inner, pack_context=None)\n",
    )
    assert raw_sites == [], [raw.site.describe() for raw in raw_sites]
    assert result.unresolved == [], [s.describe() for s in result.unresolved]


def test_dropping_the_wrap_at_an_excluded_site_reds_the_gate(tmp_path: Path) -> None:
    """The named exclusions are conditional, not blind.

    Takes the real ``charter/pack_asset.py``, deletes the wrapping call so the raw
    service escapes bare, and asserts BOTH policies red — proving an
    allow-listed site cannot be quietly converted back into a bypass.
    """
    rel = "src/specify_cli/cli/commands/charter/pack_asset.py"
    original = (REPO_ROOT / rel).read_text(encoding="utf-8")
    mutated = original.replace(
        "    service = ActiveCharterService(inner, pack_context=pack_context)\n",
        "    service = inner\n",
    )
    assert mutated != original, "mutation target not found — refresh this test"
    scratch = tmp_path / "doctrine_asset_mutant.py"
    scratch.write_text(mutated, encoding="utf-8")

    raw_sites, _ = scan_file_raw_sites(scratch, rel)
    assert [raw.site.qualname for raw in raw_sites] == ["_build_asset_repository"], [raw.site.describe() for raw in raw_sites]
    assert not raw_sites[0].verdict.wrapped
    assert check_unwrapped_escape_gate(tuple(raw_sites))
    locality = check_locality_gate(tuple(raw_sites))
    assert locality, "the exclusion must stop applying once the wrap is gone"
    assert "no longer applies" in locality[0]


def test_injected_unwrapped_builder_call_outside_charter_is_flagged(
    tmp_path: Path,
) -> None:
    """Policy A's builder-call arm bites on a second, non-wrapping caller.

    Reproduces the residual vector WP09's sweep identified: a ``specify_cli``
    module obtains the raw service from ``_build_offering_service`` (the
    sanctioned constructor, so Policy B has nothing to say) and then uses it
    bare. Injected at function-local scope with a function-local import — the
    exact shape ``org_layer.py`` uses (NFR-003).
    """
    raw_sites, _ = _raw_scratch(
        tmp_path,
        "src/specify_cli/regressed_builder_call.py",
        "def scan(repo_root, org_roots):\n"
        "    from charter.activation.active_charter_service_builder import _build_offering_service\n"
        "\n"
        "    inner = _build_offering_service(repo_root, org_roots=org_roots)\n"
        "    return inner.agent_profiles\n",
    )
    assert [raw.site.qualname for raw in raw_sites] == ["scan"], [raw.site.describe() for raw in raw_sites]
    assert raw_sites[0].kind == KIND_BUILDER_CALL
    assert not raw_sites[0].verdict.wrapped

    escapes = check_unwrapped_escape_gate(tuple(raw_sites))
    assert escapes, "Policy A must bite on an unwrapped builder-call acquisition"
    assert "regressed_builder_call.py" in escapes[0]
    assert "_build_offering_service" in escapes[0]
    # Policy B is about construction locality, so it must stay silent here.
    assert check_locality_gate(tuple(raw_sites)) == []
