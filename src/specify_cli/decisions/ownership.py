"""Which project owns a decision record — answered from local files only (#3111).

Why this module exists
----------------------

``spec-kitty agent decision widen`` resolved the project root from the
**operator's location** (``locate_project_root() or Path.cwd()``,
``cli/commands/decision.py``) while ``decision_id`` is an **operator-supplied
argument**. Standing in consenting project A and widening a decision owned by B
sent **B's identifier to A's team, under A's token**, and every consent gate
answered *truthfully — about the wrong project*. That is consent **laundering**,
not unconsented egress: the gate at ``saas_client/client.py:157`` runs *before*
``url = f"{self._base_url}{path}"``, so a non-consenting checkout already
transmits nothing. The defect is the argument's **provenance**, not its type.

The invariant this module exists to hold, in the form that supersedes all others:

    **Consent must be keyed on something derived from the RECORD BEING SENT,
    never from ambient context.**

``resolve(project_uuid_of(locate_project_root()))`` is the same defect respelled
— it is still ambient. What makes this module different is that it consults the
**ledgers**, i.e. the records themselves.

Ownership is POSITIONAL, and that is why this is a within-checkout search (D-2)
-------------------------------------------------------------------------------

There is no ``decision_id`` → owning-project mapping anywhere, locally or
remotely: :class:`~specify_cli.decisions.models.IndexEntry` is
``frozen=True, extra="forbid"`` and carries only ``mission_id`` + ``mission_slug``,
so a ``project_uuid`` cannot even be *present* in a valid ledger file; creation
takes ``repo_root``, uses it and discards it; and the SaaS client's five
endpoints include no "get decision". **Ownership is encoded by which directory
the file sits in, never as data.**

So the search is: enumerate the mission directories one level under
``<repo_root>/kitty-specs/`` and membership-test each mission's ledger with the
existing :func:`~specify_cli.decisions.store.load_index`. The outcome is
*owns it* / *ownership not established* — **never an identified project B**
(C-009). Re-resolving token and team "from the owning root" is therefore not
implementable here: it requires *identifying* B, and what actually blocks that is
the absence of a **checkout enumeration**, which is a different and buildable
thing, deferred to a follow-up.

**There is no fall-through to the acting root.** When the search finds no
positive hit the answer is *not established*, full stop. Falling through — in the
broad form *or* in the narrow "no ``kitty-specs/`` at all, so allow it" form —
reinstates exactly the leak this module closes.

Why the ledger read does not lean on ``load_index``'s ``Path.exists()``
-----------------------------------------------------------------------

``store.load_index`` opens with ``if not path.exists(): return DecisionIndex(...)``.
For a ledger whose containing ``decisions/`` directory is unreadable, ``stat(2)``
needs **search permission on the parent** (POSIX, not an interpreter quirk), and
``Path.exists()`` handles the resulting ``EACCES`` **differently per interpreter**.
Measured in this clone today, non-root euid, through ``load_index`` itself,
control first::

                          3.11.15            3.12.13            3.14.4
    CONTROL readable      1 entry, hit       1 entry, hit       1 entry, hit
    file=0o000            PermissionError    PermissionError    PermissionError
    decisions/=0o000      PermissionError    PermissionError    OK, 0 entries

The last row is the trap: on **both CI interpreters** an unreadable ledger raises
out of ``load_index`` uncaught — a traceback, not an operator-actionable refusal
— while on 3.14 it silently yields an empty index, so a local run reports a green
that CI does not have. An implementation relying on ``load_index`` alone cannot
express FR-002's unreadable branch.

The fix is an **explicit readability probe** before the parse. ``open()`` asks the
kernel the same question and gets the same answer everywhere — re-measured on all
three interpreters::

                          3.11.15            3.12.13            3.14.4
    CONTROL readable      READABLE           READABLE           READABLE
    file absent           MISSING            MISSING            MISSING
    file=0o000            UNREADABLE         UNREADABLE         UNREADABLE
    decisions/=0o000      UNREADABLE         UNREADABLE         UNREADABLE

so this module's outcome is interpreter-independent, and its test reds on *both*
interpreters if the probe is removed rather than on only one.

**MISSING, MALFORMED and UNREADABLE are three different things and must not be
lumped.** A *missing* ledger is simply a mission that owns no decisions: it sets
**no** unreadable flag and the search moves on. *Malformed* (``JSONDecodeError``
from ``json.loads``, pydantic ``ValidationError`` from ``model_validate``) and
*unreadable* (``OSError``) both mean *ownership cannot be established from this
ledger*, and unreadable ownership is not consent — each sets the flag.

**The flag never vetoes a hit elsewhere.** Refusal is correct only when the
search terminates with **no positive hit AND at least one ledger was unreadable**.
An unreadable ``index.json`` in a mission that is not the answer is warned about,
never fatal — measured: 49 ledgers across 333 mission directories in this
repository, so an unrelated corrupt file is not theoretical, and such an
invocation succeeds today.

*Could not look* is not one condition, it is three (LOW-6, LOW-7, LOW-8)
-----------------------------------------------------------------------

The missing-vs-unreadable distinction above was first drawn per-ledger, then had
to be drawn again for the specs root (LOW-6) and again for a single mission
candidate (LOW-8), because each level had its own silent skip. And *unreadable*
itself splits: ``NotADirectoryError`` **is** an ``OSError``, so a ``kitty-specs``
that is a regular **file** took the permission branch and the refusal told the
operator to ``chmod u+rx`` a path whose mode bits are irrelevant — fail-closed
and right in verdict, confidently wrong about the cause (LOW-7). The three
conditions and their operator actions are therefore kept apart:

    ============================  ==================  ==========================
    ``kitty-specs`` is …          flag                operator action
    ============================  ==================  ==========================
    absent                        none                ``git pull``
    a regular file / non-dir      ``not-a-directory``   remove the file, restore
                                                      the directory
    unlistable (EACCES)           ``unlistable``        ``chmod u+rx``
    resolves out of the root      ``outside-acting-root``  remove/repoint the link
    ============================  ==================  ==========================

None of these reach for ``Path.exists()`` or ``Path.is_dir()`` on the specs root:
that is the EACCES-divergent call this module has removed **three** times, and
``NotADirectoryError`` is a distinct exception class, so catching it costs no
extra stat.
"""

from __future__ import annotations

import errno
import json
from dataclasses import dataclass
from pathlib import Path
from stat import S_ISDIR
from typing import Literal

from pydantic import ValidationError

# Q7: **reuse one existing ULID regex, do not write a fourth.** Three exist —
# ``decisions/verify.py`` (a sentinel-comment matcher, not an anchored id
# matcher), ``context/mission_resolver.py`` (``^[0-9A-Z]{26}$``, which admits the
# non-Crockford ``I``/``L``/``O``/``U``), and this one, which is the anchored
# Crockford form and therefore the right one to bind a CLI argument. Importing it
# by reference rather than copying its pattern is the whole point: a fourth
# pattern at the CLI and a fifth in the client would be this mission's own
# whack-a-field. ``invocation`` is a CORE package, so this import does not cross
# the CORE→INTEGRATION boundary that ``test_integration_boundary.py`` enforces.
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.decisions import store
from specify_cli.decisions.models import DecisionIndex
from specify_cli.invocation.record import _ULID_RE as ULID_RE


# Only names with a real ``src/`` consumer are advertised — the symbol-level
# dead-code gate (``tests/architectural/test_no_dead_symbols.py``) is a shrink-only
# ratchet and **does not count tests as callers**. This is the same idiom
# ``egress.py`` documents for ``UNDETERMINED_PROJECT_REFUSAL``, and this module
# originally failed to apply it: ``DecisionOwnership``, ``MISSION_DIR_GLOB`` and
# ``SpecsRootFault`` were advertised with zero ``src/`` importers, growing that
# ratchet's offender set from one to four and reding the gate on every PR (the
# ``arch-adversarial`` shard's ``if:`` is ``always()``).
#
# All three stay **importable and fully usable** — the test suite imports them by
# name today. Unadvertised is not private; it means "no production reader has
# landed yet". ``DecisionOwnership`` is the declared return type of the exported
# ``resolve_decision_ownership``, so a caller that needs the annotation imports it
# directly, exactly as the tests do.
__all__ = [
    "ULID_RE",
    "is_well_formed_decision_id",
    "ownership_refusal",
    "resolve_decision_ownership",
]

#: Why the specs root itself could not be enumerated — the *cause*, carried
#: separately from the unreadable flag because the flag only says *something*
#: could not answer while the refusal has to name a **different operator action**
#: per cause. ``"unlistable"`` is EACCES (LOW-6); ``"not-a-directory"`` is a
#: ``kitty-specs`` that exists but is not a directory (LOW-7), which reached the
#: operator as a permission diagnosis because ``NotADirectoryError`` is an
#: ``OSError``. ``"outside-acting-root"`` is a ``kitty-specs`` that resolves
#: out of the acting checkout (the HIGH-2 containment case) — **not** an
#: EACCES: the comparison happens before any stat and the target lists fine.
#: Absent is neither: it sets no fault and no flag.
SpecsRootFault = Literal["unlistable", "not-a-directory", "outside-acting-root"]


#: One level under ``kitty-specs/``, and the depth is **pinned by measurement,
#: not by construction**: a one-level enumeration and a repo-wide ``rglob`` both
#: find the same **49** ledgers across **333** mission directories here, with
#: **0** missed and **0** symlinks under ``kitty-specs/``. The glob stops at the
#: mission directory rather than descending to ``*/decisions/index.json`` because
#: an unreadable ``decisions/`` cannot be *listed* — globbing through it would
#: make the mission vanish from the search silently instead of raising the
#: ``OSError`` that FR-002's unreadable branch is built on.
MISSION_DIR_GLOB = "*"

#: Errnos that mean **absent**, not **unreadable** — so a candidate failing this way
#: is skipped in silence rather than recorded, because recording it would be LOW-8's
#: missing-vs-unreadable conflation running BACKWARDS: a "could not read it" refusal
#: naming something that simply is not there.
#:
#: This is deliberately the exact set ``pathlib._ignore_error`` used through 3.13,
#: reproduced here rather than imported, because that helper is private and 3.13 moved
#: it out of the top-level namespace. Replacing ``is_dir()`` with ``stat()`` is what
#: makes ``EACCES`` observable (see the call site's four-interpreter table); it must not
#: also change how the *absence-like* failures are classified, and ``stat`` raises for
#: all of them where the predicate returned ``False``.
#:
#: Concretely: a **dangling** mission symlink raises ``ENOENT`` and a non-directory
#: raises ``ENOTDIR``. Both were silent skips before and stay silent skips.
_ABSENT_ERRNOS = frozenset({errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP})

#: Canonical, not a new private spelling — see LOW-3 in review.
_SPECS_DIRNAME = KITTY_SPECS_DIR



@dataclass(frozen=True)
class DecisionOwnership:
    """The outcome of an ownership search — an explicit verdict, never a bare bool.

    ``owned`` is *owns it* / *ownership not established*. Per C-009 this can
    **never** name project B: the search answers membership within one checkout,
    and no ``decision_id`` → owning-project mapping exists to consult.
    """

    decision_id: str
    repo_root: Path
    owned: bool
    owning_mission_slug: str | None
    missions_searched: tuple[str, ...]
    unreadable_ledgers: tuple[str, ...]
    #: ``None`` unless the specs root itself defeated the enumeration. Keyed on
    #: the CAUSE rather than inferred from ``unreadable_ledgers == (_SPECS_DIRNAME,)``:
    #: two different faults produce that same tuple and need two different
    #: operator actions, so the tuple cannot carry the distinction.
    specs_root_fault: SpecsRootFault | None = None

    @property
    def has_unreadable_ledger(self) -> bool:
        """``True`` when at least one searched ledger could not be read or parsed."""
        return bool(self.unreadable_ledgers)


@dataclass(frozen=True)
class _LedgerRead:
    """One mission's ledger, classified as readable / missing / unreadable."""

    index: DecisionIndex | None
    unreadable: bool


@dataclass(frozen=True)
class _MissionScan:
    """What the enumeration found, and what it could not look at.

    Two outputs, not one, because a candidate can be *dropped from the search*
    and that dropping is itself operator-relevant: a mission directory the
    process cannot stat leaves the search **fail-closed** (it can only ever be
    removed, never added) but must not be indistinguishable from a checkout that
    simply has no missions — LOW-8, the same missing-vs-unreadable conflation
    this module fixes one level down (per-ledger) and one level up (the specs
    root, LOW-6).
    """

    #: Mission directories the search may consult, resolved and contained.
    mission_dirs: tuple[Path, ...]
    #: Names of candidates dropped because they could not be looked at.
    unreadable: tuple[str, ...]
    #: Set only when the specs root defeated the enumeration outright.
    fault: SpecsRootFault | None


def is_well_formed_decision_id(decision_id: str) -> bool:
    """Return ``True`` when *decision_id* is an exact Crockford-base32 ULID.

    Defence-in-depth at the CLI boundary (FR-005). **It does not establish
    ownership** — a bare shape check would leave the consent-laundering defect
    entirely open, which is why the acceptance criterion requires a *well-formed*
    ULID that is present in another project's ledger.
    """
    # `.fullmatch`, not `.match`: under a ``^...$`` pattern `.match` accepts a
    # TRAILING NEWLINE ('01K...042\n' -> match True / fullmatch False). Nil impact
    # on the live path (ownership refuses independently, since no ledger entry
    # carries the newline), but it is a hole in FR-005's defence-in-depth and a
    # silent divergence from `invocation/record.py:40`, the idiom Q7 said to reuse.
    return bool(ULID_RE.fullmatch(decision_id))


def _mission_dirs(repo_root: Path, mission_slug: str | None) -> _MissionScan:
    """Enumerate mission directories under *repo_root* that the search may consult.

    ``mission_slug`` narrows **within this enumeration** and never redirects
    outside it (FR-021 discharge (ii)): a slug naming a mission this checkout does
    not contain selects nothing and is therefore an ownership failure, not a
    lookup elsewhere. Containment then holds **by construction** rather than by
    assertion — there is no ambient ``cwd``/``env``-reading resolver in this path.

    Candidates are ``.resolve()``d **before** the containment test, because
    ``Path.glob`` follows a symlinked mission directory and ``is_relative_to`` on
    the *unresolved* path would answer ``True`` for a link pointing out of the
    checkout.

    Returns a :class:`_MissionScan` rather than a bare tuple (or the ``None``
    sentinel it used to return) because *what could not be looked at* is a second,
    operator-relevant output: three conditions defeat enumeration and each needs
    its own instruction — see the module docstring's table.
    """
    root = Path(repo_root).resolve()
    specs_root = (root / _SPECS_DIRNAME).resolve()

    # HIGH-2 — CONTAINMENT, ONE LEVEL UP FROM WHERE IT WAS.
    #
    # `.resolve()` follows a symlinked `kitty-specs/` **out of the acting root**,
    # and every downstream `is_relative_to(specs_root)` is then measured against
    # the RESOLVED target — so containment held trivially and the search read
    # another checkout's ledgers as if they were ours.
    #
    # Measured end-to-end with a paired control: with `A/kitty-specs -> B/kitty-specs`
    # the command exited 0 and PUT B's decision_id on the wire, addressed to A's
    # team under A's token — `#3111`'s request line verbatim, from the code that
    # exists to prevent it. The control (no symlink) refused with zero requests.
    #
    # The module already resolves-then-contains for mission directories and
    # documents why; it simply never asked whether `kitty-specs` is ITSELF a
    # link. The spec's symlink survey measured "0 symlinks UNDER kitty-specs/",
    # which is a different question. FR-021: any path used to answer the
    # ownership question must be proved to lie under the acting root before its
    # index is consulted.
    #
    # A symlink **within** the root still works — measured — so monorepo layouts
    # that link `kitty-specs` to a sibling inside the checkout are unaffected.
    if not specs_root.is_relative_to(root):
        # NOT "unlistable". This is a pure path comparison made BEFORE any
        # stat, and the target lists perfectly — it is simply not ours.
        # Reporting it as EACCES sent the operator to `chmod` for a healthy,
        # world-readable symlink: LOW-7's defect verbatim, inside the field
        # added to fix LOW-7. A fault member is what upgrades "omitting the
        # cause" to "asserting a wrong one", so it must carry its own.
        return _MissionScan((), (_SPECS_DIRNAME,), "outside-acting-root")

    # LISTABILITY PROBE. Two things here are load-bearing and both were learned
    # the hard way; do not "simplify" either.
    #
    # 1. It must not be a `glob` in a `try`. MEASURED on 3.11.15 / 3.12.13 /
    #    3.14.4, non-root euid, control first (a readable dir lists its entry):
    #    `Path.glob` **swallows** EACCES and returns [] on every interpreter,
    #    while `iterdir` / `os.listdir` raise. So an `except OSError` wrapped
    #    around the glob is UNREACHABLE — effect-free exception handling that
    #    reads as a handled case while handling nothing.
    #
    # 2. **There is no `Path.exists()` guard, and there must never be one.** An
    #    earlier form guarded this probe with `if specs_root.exists():` — which
    #    is the very call this module's header explains is EACCES-divergent,
    #    reintroduced one level up. When an ANCESTOR of `kitty-specs/` is
    #    unreadable, `stat(2)` fails and `exists()` RAISES on both CI
    #    interpreters: a traceback instead of an operator-actionable refusal
    #    (R3), green locally on 3.14 and broken on CI. `iterdir` answers both
    #    questions at once — FileNotFoundError for absent, OSError for
    #    unlistable — so the divergent call is not needed at all.
    try:
        next(iter(specs_root.iterdir()), None)
    except FileNotFoundError:
        # No `kitty-specs/` at all. Owns nothing, so refuses — this is NOT the
        # forbidden permissive fall-through, it is the absence of any ledger.
        return _MissionScan((), (), None)
    except NotADirectoryError:
        # LOW-7 — A SHAPE ERROR WEARING A PERMISSION ERROR'S CLOTHES.
        #
        # `NotADirectoryError` is an `OSError`, so a `kitty-specs` that is a
        # regular file fell into the branch below and the refusal read "This is a
        # PERMISSION problem ... `chmod u+rx`". Measured: fail-closed and correct
        # in verdict, confidently wrong in cause — worse prose than before LOW-6
        # was fixed, because it now asserts the wrong diagnosis instead of merely
        # omitting the right one. Mode bits are irrelevant here; the path is the
        # wrong KIND of object and no chmod will change that.
        #
        # Caught as its own class rather than probed for with `Path.is_dir()`:
        # that call is the EACCES-divergent stat this module has removed three
        # times (`load_index`'s `exists()`, the `specs_root.exists()` guard,
        # `candidate.is_dir()` in HIGH-3), and re-adding one here to improve a
        # message would trade a wrong diagnosis for a traceback on CI.
        return _MissionScan((), (_SPECS_DIRNAME,), "not-a-directory")
    except OSError:
        # Could not look, as distinct from looked-and-found-nothing. Fail closed
        # either way, but never report this as "no missions found" — that sends
        # the operator to `git pull` for a permission denial, the same
        # missing-vs-unreadable conflation this module avoids for each ledger.
        return _MissionScan((), (_SPECS_DIRNAME,), "unlistable")

    candidates = sorted(specs_root.glob(MISSION_DIR_GLOB))

    kept: list[Path] = []
    unreadable: list[str] = []
    for candidate in candidates:
        # The slug narrows FIRST, and deliberately: `candidate.name` is a
        # pure-path property needing no `stat(2)`, so filtering here both avoids
        # stat'ing candidates the slug already excluded and keeps the LOW-8 flag
        # below scoped to the missions actually in the search.
        if mission_slug is not None and candidate.name != mission_slug:
            continue
        # HIGH-3 — THE THIRD INSTANCE OF THE SAME EACCES TRAP, and the FOURTH is
        # why this reads `S_ISDIR(resolved.stat().st_mode)` and not
        # `resolved.is_dir()`.
        #
        # An unstattable candidate cannot answer the ownership question, so
        # skipping it is correct and stays fail-closed: it can only ever remove
        # a mission from the search, never add one. What is NOT correct is
        # skipping it *silently* — that is LOW-8 below.
        #
        # `Path.is_dir()` is EACCES-DIVERGENT, in the direction that makes the
        # LOW-8 recording below unreachable rather than merely wrong:
        #
        #   | call                    | 3.11.15 | 3.12.13 | 3.13.12 | 3.14.4  |
        #   | ----------------------- | ------- | ------- | ------- | ------- |
        #   | `Path.stat` / `os.stat` | RAISES  | RAISES  | RAISES  | RAISES  |
        #   | `Path.is_dir()`         | RAISES  | RAISES  | RAISES  | False   |
        #
        # MEASURED on all four, non-root euid, control first, via a symlink into a
        # 0o000 directory — `stat()` raising errno 13 in the same process that
        # `is_dir()` answered False.
        #
        # **The divergence begins at 3.14, not 3.13.** 3.14 rewrote the predicate
        # to `if follow_symlinks: return os.path.isdir(self)`, and
        # `os.path.isdir` swallows every `OSError`. Through 3.13 it was
        # `S_ISDIR(self.stat().st_mode)` under `except OSError: if not
        # _ignore_error(e): raise`, and `_ignore_error` covers only
        # `ENOENT`/`ENOTDIR`/`EBADF`/`ELOOP` — so EACCES propagated. (3.13 does
        # make `pathlib` a package, which moves `_ignore_error` out of the
        # top-level namespace. That is a layout change, not a behaviour change:
        # probing `hasattr(pathlib, "_ignore_error")` reports 3.13 as though it
        # had changed, and it had not. Measure the call, not the namespace.)
        #
        # `stat()` raises on every interpreter; only the predicate changed. So with
        # `is_dir()` here, an unreadable candidate on 3.14+ takes the silent
        # `continue` on the line below instead of the `except OSError` that records
        # it, and the operator is told "no missions were found ... run `git pull`"
        # for a permission denial — LOW-8's exact defect, with its fix present but
        # INERT. No CI job runs pytest above 3.12, so CI could not see it. Filed as
        # #3177 and initially deferred; fixed here instead.
        #
        # The evaluation order is load-bearing and unchanged: the stat is
        # evaluated BEFORE the containment check, so an unreadable candidate is
        # recorded as unreadable rather than dropped as escaping. A candidate that
        # stats fine and *then* fails containment is a different verdict, and the
        # silent skip is right for it — nothing was hidden from us there.
        try:
            resolved = candidate.resolve()
            if not S_ISDIR(resolved.stat().st_mode) or not resolved.is_relative_to(
                specs_root
            ):
                continue
        except OSError as exc:
            # ABSENT beats UNREADABLE, and the split is on errno — see
            # `_ABSENT_ERRNOS`. Replacing `is_dir()` with `stat()` made EACCES
            # observable, which is the fix; it also made the absence-like failures
            # raise where the predicate merely returned `False`, and those must NOT
            # become "could not read it". A dangling mission symlink is not an
            # unreadable ledger, and reporting one as unreadable is this module's
            # own conflation running backwards.
            if exc.errno in _ABSENT_ERRNOS:
                continue
            # LOW-8 — SKIP, BUT NOT IN SILENCE.
            #
            # Fail-closed was never the gap; the gap was that the operator was
            # told the wrong thing. Measured: an unstattable mission symlink with
            # no other mission yielded `unreadable_ledgers=()`, so the refusal
            # said "no missions were found ... run `git pull`" for a permission
            # problem — LOW-6's defect one level down.
            #
            # Recording the name does NOT make this a veto: `owned` is decided
            # solely by the ledger loop in `resolve_decision_ownership`, and
            # `ownership_refusal` permits on any positive hit before it ever
            # looks at this flag. That is R12's rule and it has its own control.
            unreadable.append(candidate.name)
            continue
        kept.append(resolved)
    return _MissionScan(tuple(kept), tuple(unreadable), None)


def _read_ledger(mission_dir: Path, acting_root: Path) -> _LedgerRead:
    """Read one mission's ``index.json``, classifying failures rather than raising.

    The explicit ``open()`` probe is what makes MISSING, UNREADABLE and MALFORMED
    three distinguishable answers on **every** interpreter — see the module
    docstring's two measurement tables. ``load_index``'s own ``Path.exists()``
    cannot do it: it swallows ``EACCES`` on 3.14 and raises on 3.11/3.12.

    **Containment is re-asserted HERE, on the file actually opened.** FR-021 says
    any path used to answer the ownership question must be proved to lie under the
    acting root **before its index is consulted**, and ``_mission_dirs`` proves it
    only for the *mission directory* — two levels above the file this function
    reads. Measured: symlinking either ``<mission>/decisions/`` or
    ``<mission>/decisions/index.json`` out of the checkout yielded ``owned=True``
    and put the other project's ``decision_id`` on the wire under this checkout's
    token — ``#3111``'s request line, at a depth the mission-directory check
    cannot see.

    An out-of-root ledger is classified **UNREADABLE, not MISSING**: it exists but
    cannot answer *for this checkout*, which is the same shape as a corrupt file
    and must not be silently skipped. Containment is measured against the **acting
    root**, not the mission directory, so a layout that links ``decisions/``
    elsewhere *inside* the checkout keeps working.
    """
    index_file = store.index_path(mission_dir)

    # No `.exists()` here — that call is EACCES-divergent and this module has
    # already had to remove it twice. Non-strict `resolve()` does not raise for a
    # missing path, so a mission with no ledger still resolves to a path under the
    # root, containment holds, and MISSING is decided below by `open()` exactly as
    # before. A resolve that *does* raise is a read failure, i.e. UNREADABLE.
    try:
        if not index_file.resolve().is_relative_to(acting_root):
            return _LedgerRead(index=None, unreadable=True)
    except OSError:
        return _LedgerRead(index=None, unreadable=True)

    try:
        with index_file.open("rb"):
            pass
    except FileNotFoundError:
        # MISSING is not an error: this mission simply owns no decisions. It
        # contributes no unreadable flag and the search moves on.
        return _LedgerRead(index=None, unreadable=False)
    except OSError:
        # UNREADABLE. Not optional and not decoration: on both CI interpreters
        # this is where a permission-denied ledger would otherwise escape as a
        # traceback instead of an operator-actionable refusal.
        return _LedgerRead(index=None, unreadable=True)

    try:
        return _LedgerRead(index=store.load_index(mission_dir), unreadable=False)
    except (OSError, json.JSONDecodeError, ValidationError, store.DecisionIndexReadError):
        # MALFORMED (bad JSON, or schema-invalid content), plus any residual read
        # failure between the probe and the parse. Ownership cannot be
        # established from this ledger, and unreadable ownership is not consent.
        return _LedgerRead(index=None, unreadable=True)


def resolve_decision_ownership(
    repo_root: Path,
    decision_id: str,
    *,
    mission_slug: str | None = None,
) -> DecisionOwnership:
    """Establish, from local files under *repo_root* only, whether it owns *decision_id*.

    Args:
        repo_root: The **acting** checkout. Ownership is decided by what this
            checkout's ledgers contain — never by what the operator typed.
        decision_id: The record whose owner is in question.
        mission_slug: Optional narrowing hint. It selects *among the missions this
            checkout already contains*; it is never an instruction to look
            elsewhere.

    Returns:
        A :class:`DecisionOwnership` verdict. **No fall-through**: "found nothing"
        is *ownership not established*, which refuses.
    """
    root = Path(repo_root).resolve()
    scan = _mission_dirs(root, mission_slug)
    searched: list[str] = []
    # Seeded, not started empty: whatever the enumeration could not look at is
    # already *could not answer*, and it flows through the one ordinary
    # construction below rather than an early return — one fewer place for the
    # two answers to drift apart.
    unreadable: list[str] = list(scan.unreadable)
    owning: str | None = None

    for mission_dir in scan.mission_dirs:
        searched.append(mission_dir.name)
        read = _read_ledger(mission_dir, root)
        if read.unreadable:
            # Recorded, never fatal on its own: an unreadable ledger in a mission
            # that is not the answer must not veto a positive hit elsewhere.
            unreadable.append(mission_dir.name)
            continue
        if read.index is not None and any(
            entry.decision_id == decision_id for entry in read.index.entries
        ):
            owning = mission_dir.name
            break

    return DecisionOwnership(
        decision_id=decision_id,
        repo_root=root,
        owned=owning is not None,
        owning_mission_slug=owning,
        missions_searched=tuple(searched),
        unreadable_ledgers=tuple(unreadable),
        specs_root_fault=scan.fault,
    )


def _specs_root_refusal(outcome: DecisionOwnership) -> str | None:
    """The refusal for a specs root that defeated the enumeration, or ``None``.

    Split out so each fault carries its **own operator action**. Naming the flag
    but not acting on it is half a fix (LOW-6); acting on it with one shared
    message is the other half of the same mistake, because the whole point of
    distinguishing *could not look* from *found nothing* is that they need
    different instructions — and *could not look* is itself two conditions.
    """
    if outcome.specs_root_fault is None:
        return None

    specs_path = outcome.repo_root / _SPECS_DIRNAME
    preamble = (
        f"the checkout at {outcome.repo_root} could not be searched for "
        f"decision {outcome.decision_id}: "
    )
    consequence = (
        "so ownership cannot be established and transmitting would ask the wrong "
        "project's consent; refusing to transmit. "
    )

    if outcome.specs_root_fault == "not-a-directory":
        # LOW-7. Says what is wrong with the path's SHAPE and never mentions
        # permissions: mode bits are irrelevant to an object of the wrong kind,
        # and the previous prose sent the operator to `chmod` for a file that
        # needed removing.
        return (
            f"{preamble}{specs_path} exists but is not a directory, so no mission "
            f"ledger can be enumerated under it, {consequence}This is not a "
            f"permission problem and not a missing checkout — neither `chmod` nor "
            f"`git pull` will fix it. To fix: inspect it with `ls -ld "
            f"{specs_path}`, remove or rename the file occupying that path, and "
            f"restore the directory (e.g. `git checkout -- {_SPECS_DIRNAME}`), "
            f"then retry."
        )

    if outcome.specs_root_fault == "outside-acting-root":
        # MEDIUM-1. Neither `chmod` nor `git pull` is the action here: the path is
        # present and healthy, it just resolves out of this checkout.
        #
        # **The resolved target is deliberately NOT interpolated.** Printing it
        # would name the project whose ledgers were nearly consulted — project B —
        # and C-009 forbids this module ever identifying B. `ls -ld` shows the
        # operator the target; the refusal does not have to disclose it.
        return (
            f"{preamble}{specs_path} resolves outside this checkout, so any ledger "
            f"under it belongs to a different project and cannot answer for this "
            f"one, {consequence}This is neither a permission problem nor a missing "
            f"checkout — neither `chmod` nor `git pull` will fix it. To fix: "
            f"inspect it with `ls -ld {specs_path}`; if it is a symlink, remove it "
            f"or repoint it inside this checkout, then retry."
        )

    return (
        f"{preamble}{specs_path} could not be listed, {consequence}This is a "
        f"PERMISSION problem, not a missing checkout — `git pull` will not fix "
        f"it. To fix: check the directory and its parents with `ls -ld "
        f"{specs_path}` and restore read+execute access (e.g. `chmod u+rx`), "
        f"then retry."
    )


def ownership_refusal(outcome: DecisionOwnership) -> str | None:
    """Return why *outcome* forbids transmission, or ``None`` to permit.

    ``None`` — and only ``None`` — is permission.

    The message **names the operator action**, not merely the failure. Silence
    about what to do is what makes the forbidden fall-through look reasonable to
    the next person holding a red test. It also never claims to identify the
    owning project: under C-009 that information does not exist locally.
    """
    if outcome.owned:
        return None

    # LOW-6 / LOW-7: the specs root itself defeated the enumeration. Reported
    # through the generic branch below, LOW-6 read "no missions were found ... 1
    # decision ledger(s) could not be read ... To fix: run `git pull`" — which
    # calls a DIRECTORY a ledger and sends the operator to git for a permission
    # denial. Keyed on the FAULT, not on `unreadable_ledgers == (_SPECS_DIRNAME,)`:
    # LOW-7 produces that identical tuple and needs a different instruction, so
    # the tuple cannot be the discriminator.
    specs_root_refusal = _specs_root_refusal(outcome)
    if specs_root_refusal is not None:
        return specs_root_refusal

    if outcome.missions_searched:
        searched = (
            f"{len(outcome.missions_searched)} mission(s) searched under "
            f"{outcome.repo_root / _SPECS_DIRNAME}: "
            f"{', '.join(outcome.missions_searched)}"
        )
    elif outcome.unreadable_ledgers:
        # LOW-8, the other half. Reached only when every mission the glob found
        # was dropped as unstattable, and in that case "no missions were found"
        # is simply FALSE — one was found, it could not be looked at. That
        # sentence is the misdiagnosis this residual quotes, so setting the flag
        # without removing it would be naming the cause and then contradicting it
        # in the same breath.
        searched = (
            f"no mission under {outcome.repo_root / _SPECS_DIRNAME} could be "
            "searched at all"
        )
    else:
        searched = (
            f"no missions were found under {outcome.repo_root / _SPECS_DIRNAME} "
            "to search"
        )

    unreadable = ""
    if outcome.unreadable_ledgers:
        # LOW-2: "decision ledger(s)" was accurate while every entry was a ledger.
        # LOW-8 added a new source — a mission DIRECTORY that could not be stat'ed —
        # and routed it into this sentence. This module's own LOW-6 comment names
        # "calls a DIRECTORY a ledger" as part of the defect it fixed, so naming one
        # here reintroduces it one level down. The name is also published in the
        # `--dry-run` payload under `unreadable_ledgers`, where a machine consumer
        # parsing it as ledger paths gets a wrong answer.
        unreadable = (
            f" {len(outcome.unreadable_ledgers)} mission ledger(s) or mission "
            f"directory(ies) could not be read or parsed and so could not answer: "
            f"{', '.join(outcome.unreadable_ledgers)}."
        )

    # LOW-1: the remedy has to match the diagnosis. LOW-8 removed the false
    # "no missions were found" clause but left `git pull` as the only action
    # offered — and `git pull` does not fix a permission denial. That is the same
    # misdirection LOW-6 was raised to remove one level up, surviving at the level
    # LOW-8 was raised to fix. A refusal that names the cause and then prescribes
    # the wrong action is not half-fixed; it is differently wrong.
    # LOW-4: keyed on `unreadable_ledgers` ALONE, not on the conjunction with an
    # empty search. The conjunction only covered "nothing was searchable at all",
    # which this module's own docstring measures as the RARE case — 49 ledgers
    # across 333 mission directories means "one of many was unreadable" is the
    # common one, and that path still offered only `git pull`. LOW-1's defect
    # survived on the likelier configuration; narrowing a condition is not closing
    # it. A cleanly not-owned or genuinely absent checkout still gets bare
    # `git pull`, which is correct there.
    if outcome.unreadable_ledgers:
        remedy = (
            f"To fix: this is not a missing checkout — `git pull` will not fix it. "
            f"Inspect the named path and its parents with `ls -ld` under "
            f"{outcome.repo_root / _SPECS_DIRNAME} and restore read+execute access "
            f"(e.g. `chmod u+rx`); if it is a symlink, check its target. Then retry."
        )
    else:
        remedy = (
            "To fix: run `git pull` (or otherwise restore kitty-specs/) and retry; "
            "if the decision was recorded in a different checkout, run the command "
            "from that checkout."
        )

    return (
        f"the checkout at {outcome.repo_root} does not own decision "
        f"{outcome.decision_id} — it is listed in no decision ledger in this "
        f"checkout, so this checkout's consent cannot answer for it, and "
        f"transmitting it would ask the wrong project's consent; refusing to "
        f"transmit ({searched}).{unreadable} {remedy}"
    )
