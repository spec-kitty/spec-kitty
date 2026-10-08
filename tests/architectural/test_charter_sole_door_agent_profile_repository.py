"""Gate 1 (FR-001/FR-007, WP09): zero raw ``AgentProfileRepository``
construction outside the charter sole door.

Mission ``charter-sole-door-bypass-closure-01KZ3WAA``, WP09 / T037. First of the
three mission-wide durability gates this work package ships; Gate 4 lives in
``test_charter_sole_door_hardcoded_paths.py`` (WP06) and Gate 5 in
``test_charter_sole_door_inner_reacharound.py`` (WP04).

What it proves
--------------
NFR-001 requires that every ``AgentProfileRepository(`` call site in ``src/``
resolve its **bound qualname** to the originating module, and that zero of them
resolve to ``charter.offering.agent_profiles.repository.AgentProfileRepository`` outside
the sole door (``src/charter/activation/resolver.py``), the one unified builder
(``src/charter/activation/active_charter_service_builder.py``, FR-008), and the named,
composite-key-anchored exclusions below.

**Why a text grep is not acceptable here** (NFR-001, verbatim: "explicitly NOT a
text-only grep"): the class is re-exported through several facades, so the same
class is spelled ``charter.profiles.AgentProfileRepository`` in
``tool_surface/profiles/projection.py`` and
``charter.offering.agent_profiles.AgentProfileRepository`` in
``charter/activation/profile_resolution.py`` — both resolve to the single originating
``charter.offering.agent_profiles.repository.AgentProfileRepository``. Conversely, a
future ``AgentProfileRepository`` defined in some unrelated module would share
the literal substring while being an entirely different class. This gate
resolves each call site's bound name to a real ``(module, name)`` pair by AST
import analysis — module-level **and** function-local **and** nested
``try``/``except`` imports, plus ``as``-aliases, module-qualified calls and
**per-scope** re-bindings — and then asks Python itself where the object came
from via ``__module__``/``__qualname__``. A rename, a new facade re-export or an
alias therefore cannot slip past it, and a same-named unrelated class cannot
false-positive into it.

Shared scan machinery
----------------------
The qualname-resolution primitives (``scan_file_constructions``,
``scan_constructions``, ``structurally_exempt``, ``resolve_exclusion_keys``,
``assert_rationales_are_substantive``, ``scratch_scan``, and their supporting
AST helpers) now live in :mod:`tests.architectural._sole_door_scan` — a
non-test library module, not a fourth gate. Gates 1, 2, and 3 all import from
it directly; see that module's docstring for why library code cannot live
inside a ``test_`` module (pytest collects it, and ``src/`` cannot import
``tests/``) and for the per-scope alias-rebind fix (A1, landing-fold gate
hardening) applied there: the predecessor ``_module_level_rebinds`` walked
only module scope, so ``Local = AgentProfileRepository`` inside a function
body — a measured miss against injection probes — evaded both this gate and
Gate 2.

Structural exemptions (directory/file keyed, never line keyed)
---------------------------------------------------------------
* ``src/charter/offering/`` — the offering *owns* this class and the raw
  ``charter.offering.service.CharterOfferingService`` that composes it
  (``charter/offering/service.py``'s ``CharterOfferingService.agent_profiles`` cache). That
  construction is the thing the sole door wraps, not a bypass of it — the same
  shape as Gate 5's ``src/charter/`` exemption.
* ``src/charter/activation/resolver.py`` — the sole door itself (NFR-001).
* ``src/charter/activation/active_charter_service_builder.py`` — the ONE unified builder
  (FR-008/NFR-001).

Named exclusions are **composite-key anchored, never whole-file**
------------------------------------------------------------------
Each entry below is a :class:`ContentDescriptor` resolving to exactly one live
site, keyed on ``(rel_path, enclosing_qualname, token_line)``. Sanctioning one
construction in a module does NOT waive the module: a genuinely new bypass added
to ``registry.py`` still reds because its qualname/token differ — proven by
:func:`test_excluding_one_site_does_not_waive_its_module`.

**Why the key is ``(file, qualname, token)`` rather than the
``(file, qualname, line)`` spec.md NFR-001 phrases.** A raw line number is
banned as an authoritative comparand anywhere under ``tests/architectural/`` by
the standing gate ``test_ratchet_positional_anchor_ban.py`` (DIR-041 / #2077,
mission ``content-address-ratchet-allowlists-01KX8M4D``); an allow-list seeded
with ``(rel, N)`` rows reds it. The canonical repo primitive is
``composite_key``'s drift-proof ``(qualname, token_line)`` pair, with the line
kept only as a non-authoritative locator. This is strictly stronger, not a
weakening: this mission *empirically* demonstrated the drift — every line number
spec.md pinned had already moved by the time this gate was written
(``registry.py`` 48→73, ``projection.py`` 84→115, ``profile_resolution.py``
81→95, and Gate 2's four ``_doctrine_collect.py`` sites 193/283/420/828 →
209/314/468/920). Using the canonical primitive is also the repo rule (never
improvise a second key-builder).

The four named exclusions, and their provenance
-------------------------------------------------
1. ``invocation/registry.py`` (``ProfileRegistry.__init__``) — C-006: builds
   against ``.kittify/profiles``, a local-override directory outside the
   doctrine activation model, explicitly out of scope by operator decision.
   **Pre-sanctioned** by spec.md FR-001/C-006.
2. ``cli/commands/profiles_cmd.py`` (``_profile_catalog``) — C-006, same
   ``.kittify/profiles`` rationale. **Pre-sanctioned** by spec.md FR-001/C-006.
3. ``charter/activation/profile_resolution.py`` (``_default_agent_profile_repository``) —
   FR-001's *confirmed bootstrap carve-out*: a zero-argument, module-level
   cached built-in-only repository with no ``repo_root`` from which to build a
   factory. spec.md FR-001 directs, verbatim, "document it as a genuine C-002
   bootstrap case, do not attempt to route it through the factory".
   **Pre-sanctioned.**
4. ``tool_surface/profiles/projection.py`` (``default_profile_repository``) —
   **NOT pre-sanctioned; added by WP09 as an escalated C-002 finding, and a
   tracked follow-up rather than a permanent carve-out.** WP02 named this site
   as an in-scope FR-001 migration target and then could not close it: the
   factory's ``agent_profile_repository`` accessor is built from a raw service
   whose project-overlay directory comes from
   ``charter.activation._project_root_candidates.resolve_project_root``'s three fixed candidates
   (``.kittify/doctrine``, ``src/doctrine``, ``doctrine``), none of which is
   ``.kittify/agent_profiles``, and ``build_active_charter_service``
   exposes no parameter to retarget it. Both WP02's implementer and its reviewer
   independently forced the naive migration and reproduced three real test
   breakages (project-overlay profiles silently dropped). Closing it correctly
   needs a builder-level change on WP01's already-approved surface — new scope,
   outside WP09's write scope. That function's own docstring carries the full
   evidence trail. **This entry must be DELETED, not renewed, once the builder
   gains a project-overlay override.**

No other exclusion may be added without the same standard of written
justification (C-002: no shrink-only escape hatch, zero exceptions).
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest

from tests.architectural._ratchet_keys import ContentDescriptor
from tests.architectural._sole_door_scan import (
    REPO_ROOT,
    SRC_ROOT,
    ConstructionSite,
    ScanResult,
    resolve_exclusion_keys,
    scan_constructions,
    scan_file_constructions,
    scratch_scan,
    structurally_exempt,
)

pytestmark = pytest.mark.architectural

#: The originating qualname every sanctioned and unsanctioned spelling of the
#: agent-profile repository collapses to. Named verbatim by spec.md NFR-001.
AGENT_PROFILE_REPOSITORY_QUALNAME = "charter.offering.agent_profiles.repository.AgentProfileRepository"

#: Gate 1 watches exactly one canonical class.
AGENT_PROFILE_TARGETS = frozenset({AGENT_PROFILE_REPOSITORY_QUALNAME})

#: Simple names a call site may spell to reach the class. Only calls whose
#: callee resolves to one of these *original* names (pre-``as``-alias) get a
#: canonical lookup, keeping the scan's dynamic-import surface tiny.
AGENT_PROFILE_CANDIDATE_NAMES = frozenset({"AgentProfileRepository"})


# =========================================================================== #
# Gate 1 policy
# =========================================================================== #

#: Named, individually-justified exclusions — composite-key anchored via a
#: content descriptor, never a whole file and never a line number. Read the
#: module docstring's "four named exclusions" section before touching this.
AGENT_PROFILE_EXCLUSIONS: tuple[ContentDescriptor, ...] = (
    ContentDescriptor(
        rel_path="src/specify_cli/invocation/registry.py",
        qualname="ProfileRegistry.__init__",
        token_substring="AgentProfileRepository (",
        occurrence=None,
        rationale=(
            "C-006: constructs against .kittify/profiles, a local-override "
            "directory outside the doctrine activation model; explicitly out of "
            "scope by operator decision (spec.md FR-001/C-006). Do not route it "
            "through the factory and do not fold its rework into this mission."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/profiles_cmd.py",
        qualname="_profile_catalog",
        token_substring="AgentProfileRepository (",
        occurrence=None,
        rationale=(
            "C-006: the same .kittify/profiles local-override rationale as "
            "invocation/registry.py; explicitly out of scope by operator "
            "decision (spec.md FR-001/C-006), slated for separate future rework."
        ),
    ),
    ContentDescriptor(
        rel_path="src/charter/activation/profile_resolution.py",
        qualname="_default_agent_profile_repository",
        token_substring="AgentProfileRepository ( )",
        occurrence=None,
        rationale=(
            "FR-001 confirmed bootstrap carve-out: a zero-argument, "
            "module-level cached built-in-only repository with no repo_root "
            "from which to build a factory. spec.md FR-001 directs documenting "
            "it as a genuine C-002 bootstrap case rather than routing it "
            "through the factory."
        ),
    ),
)


@functools.cache
def agent_profile_census() -> ScanResult:
    """Every resolved ``AgentProfileRepository`` construction under ``src/``.

    Memoised for the test session: the scan is a pure function of an unchanging
    working tree, and several tests below need it. Nothing mutates the returned
    lists.
    """
    return scan_constructions(
        SRC_ROOT,
        candidate_names=AGENT_PROFILE_CANDIDATE_NAMES,
        target_qualnames=AGENT_PROFILE_TARGETS,
    )


def check_agent_profile_gate(sites: list[ConstructionSite]) -> list[str]:
    """Return violation strings for *sites* — zero-tolerance, no wildcards."""
    excluded = resolve_exclusion_keys(AGENT_PROFILE_EXCLUSIONS)
    return [
        f"{site.describe()} constructs the raw agent-profile repository outside "
        "the charter sole door (FR-001/NFR-001) — obtain it from "
        "charter.activation.resolver.ActiveCharterService.agent_profile_repository instead"
        for site in sites
        if not structurally_exempt(site.rel_path) and site.key not in excluded
    ]


# =========================================================================== #
# Anti-vacuity: the scan really walks the tree and really resolves facades
# =========================================================================== #


def test_census_is_non_empty_and_includes_the_doctrine_owner() -> None:
    """The resolver must actually find the known live constructions.

    A gate whose scanner silently resolves nothing would pass its
    zero-violation assertion vacuously. This pins the opposite: the census finds
    sites, and specifically finds ``doctrine/service.py``'s own construction
    (the structurally exempt owner), proving the resolution path works end to
    end rather than short-circuiting.
    """
    census = agent_profile_census()
    assert len(census.sites) >= 5, [s.describe() for s in census.sites]
    assert any(s.rel_path == "src/charter/offering/service.py" for s in census.sites), [s.describe() for s in census.sites]
    assert all(s.canonical == AGENT_PROFILE_REPOSITORY_QUALNAME for s in census.sites)


def test_no_unresolved_agent_profile_candidates() -> None:
    """No ``AgentProfileRepository(``-shaped call may go unresolved.

    An unresolved candidate is a blind spot, not a pass: the gate could not
    decide whether the site is the watched class. Treating those as clean is
    exactly how a "zero violations" gate goes vacuous, so they fail here.
    """
    unresolved = agent_profile_census().unresolved
    assert unresolved == [], [s.describe() for s in unresolved]


# =========================================================================== #
# The gate
# =========================================================================== #


def test_no_raw_agent_profile_repository_construction_outside_the_sole_door() -> None:
    """Zero-tolerance (C-002): nothing beyond the four named exclusions."""
    violations = check_agent_profile_gate(agent_profile_census().sites)
    assert violations == [], "\n".join(violations)


# =========================================================================== #
# NFR-003 self-mutation proofs — function-local and nested scope, never
# module-level-only (the WP10 lesson from charter.offering-charter-split-unification).
# =========================================================================== #


def _agent_profile_scratch(tmp_path: Path, rel_name: str, source: str) -> ScanResult:
    return scratch_scan(
        tmp_path,
        rel_name,
        source,
        candidate_names=AGENT_PROFILE_CANDIDATE_NAMES,
        target_qualnames=AGENT_PROFILE_TARGETS,
    ).result


def test_injected_function_local_construction_is_flagged(tmp_path: Path) -> None:
    """A reintroduced bypass with a **function-local** import is caught.

    This is the real violation shape: every live site in this codebase imports
    the class inside a function body, not at module level. A gate that only
    inspected module-level imports would pass this vacuously (NFR-003).
    """
    result = _agent_profile_scratch(
        tmp_path,
        "regressed_local.py",
        "def build(project_dir):\n    from charter.profiles import AgentProfileRepository\n\n    return AgentProfileRepository(project_dir=project_dir)\n",
    )
    assert result.unresolved == [], [s.describe() for s in result.unresolved]
    assert len(result.sites) == 1, [s.describe() for s in result.sites]
    site = result.sites[0]
    assert site.qualname == "build"
    assert site.canonical == AGENT_PROFILE_REPOSITORY_QUALNAME
    violations = check_agent_profile_gate(result.sites)
    assert violations, "the gate must bite on a function-local reintroduction"
    assert "regressed_local.py" in violations[0]
    assert "build" in violations[0]


def test_detector_ignores_a_same_named_unrelated_class(tmp_path: Path) -> None:
    """A different class that merely shares the name must NOT be flagged.

    The true-negative half of the qualname requirement: a text grep for
    ``AgentProfileRepository(`` flags this; resolving the bound qualname does
    not, because the canonical origin differs.
    """
    result = _agent_profile_scratch(
        tmp_path,
        "unrelated_same_name.py",
        "class AgentProfileRepository:\n"
        "    def __init__(self, project_dir=None):\n"
        "        self.project_dir = project_dir\n"
        "\n"
        "\n"
        "def build():\n"
        "    return AgentProfileRepository()\n",
    )
    assert result.sites == [], [s.describe() for s in result.sites]
    assert result.unresolved == [], [s.describe() for s in result.unresolved]


def test_excluding_one_site_does_not_waive_its_module(tmp_path: Path) -> None:
    """Composite-key keying, proven: a NEW bypass in an excluded file still reds.

    Injects a second construction into a copy of ``invocation/registry.py`` — the
    file carrying the ``ProfileRegistry.__init__`` exclusion (C-006, builds
    against ``.kittify/profiles``) — inside a *different* function. The excluded
    site stays excluded; the new one is reported. A whole-file exclusion would
    have swallowed both. (Re-pointed off ``projection.py``'s
    ``default_profile_repository`` after that site migrated onto the builder
    overlay seam in mission M4/WP02 (#3176) and its exclusion descriptor was
    deleted; ``registry.py`` imports ``AgentProfileRepository`` at module level,
    so the appended site resolves without any extra import.)
    """
    original = (REPO_ROOT / "src/specify_cli/invocation/registry.py").read_text(encoding="utf-8")
    scratch = tmp_path / "registry_mutant.py"
    scratch.write_text(
        original + ("\n\ndef sneaky_second_door(project_root):\n    return AgentProfileRepository(project_dir=project_root)\n"),
        encoding="utf-8",
    )
    scan = scan_file_constructions(
        scratch,
        "src/specify_cli/invocation/registry.py",
        candidate_names=AGENT_PROFILE_CANDIDATE_NAMES,
        target_qualnames=AGENT_PROFILE_TARGETS,
    )
    assert scan is not None
    qualnames = {site.qualname for site in scan.result.sites}
    assert {"ProfileRegistry.__init__", "sneaky_second_door"} <= qualnames, qualnames

    violations = check_agent_profile_gate(scan.result.sites)
    assert len(violations) == 1, violations
    assert "sneaky_second_door" in violations[0]
    assert "ProfileRegistry.__init__" not in violations[0]
