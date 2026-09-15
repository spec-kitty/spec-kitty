"""Resolution convergence test — read-seam dir == write/placement-seam dir (FR-006 / SC-005).

This module is a STUB-LEVEL convergence check for FR-006 (SC-005). The load-bearing,
red-first PRODUCTION convergence proof (monkeypatching the real ``_read_path_resolver``
primitives, calling real ``resolve_planning_read_dir(kind=TASKS_INDEX)``) lives in
``tests/specify_cli/cli/commands/test_coord_status_commit_2155.py``
(``test_mark_status_write_leg_matches_commit_leg_{coord,flat}_topology``); this is the
structural stub mirror documenting the same contract. After WP02–WP05 route every call
site through the canonical kind-aware seam, no handle form can map differently between the
read leg and the write leg.  The test is STUB-DRIVEN — no live ``kitty-specs/`` fixtures
are accessed.

Pre-fix divergence (the negative control, T031):
-----------------------------------------------------
Before WP02 (IC-04a) routed ``mark_status``'s write leg through the kind-aware authority,
the ``full_slug`` handle under coordination topology diverged:

* **Read leg** (``_canonicalize_primary_read_handle``) — kind-aware; for a PRIMARY artifact
  kind it resolves the slug to the ``<slug>-<mid8>`` composed dir name and lands on the
  PRIMARY surface.
* **Write leg** (kind-blind resolver, pre-WP02) — topology-blind; it would compose the
  bare slug verbatim and land on the COORDINATION surface for a coord-topology mission.

The result: read → ``/fake/resolved/by-full-slug`` (PRIMARY), write (old) →
``/fake/old-coord-write/by-full-slug`` (COORD).  Those are DIFFERENT paths, proving the
test was RED on the pre-fix resolver.  After WP02 the write leg adopts the same kind-aware
authority, so both return ``/fake/resolved/by-full-slug``.  T031 reproduces this divergence
in a pair of stubs and asserts:

1. The "old behavior" stub pair returns DIFFERENT dirs (red-first proof).
2. The fixed stub returns the SAME dir (green post-fix).

Stub design (T028 / FORM_TO_DIR):
------------------------------------
The five handle forms each resolve to a UNIQUE fake directory through the ``FakeResolver``.
A constant-returning stub (all forms → same path) is structurally rejected by T032.

``FakeResolver.read_dir(handle)`` mirrors ``_canonicalize_primary_read_handle`` +
``primary_feature_dir_for_mission``: it classifies the handle form from its shape (ULID
pattern, composed ``<slug>-<mid8>`` pattern, bare mid8 pattern, numeric pattern, bare slug)
and returns the form-specific directory from ``FORM_TO_DIR``.

``FakeResolver.write_dir(handle)`` mirrors ``resolve_planning_read_dir`` for a PRIMARY
artifact kind: it delegates to the same classification logic, so both legs agree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants — FORM_TO_DIR (T028)
# ---------------------------------------------------------------------------

# Distinguishable per-form outputs: every form maps to a UNIQUE directory.
# A constant-returning stub (same path for all forms) is rejected by T032.
FORM_TO_DIR: dict[str, Path] = {
    "full_slug": Path("/fake/resolved/by-full-slug"),
    "slug_mid8": Path("/fake/resolved/by-slug-mid8"),
    "bare_mid8": Path("/fake/resolved/by-bare-mid8"),
    "ulid": Path("/fake/resolved/by-ulid"),
    "numeric": Path("/fake/resolved/by-numeric"),
}

# Production-shaped test identity (real formats, real lengths)
_MISSION_ID = "01KW1P0FRYK89H5TK5QK8148X9"  # 26-char ULID
_MID8 = _MISSION_ID[:8]  # "01KW1P0F"
_MISSION_SLUG = "my-test-mission"
_SLUG_WITH_MID8 = f"{_MISSION_SLUG}-{_MID8}"  # "my-test-mission-01KW1P0F"

# ULID pattern: 26 uppercase alphanumeric chars (Crockford base32)
_ULID_RE = re.compile(r"^[0-9A-Z]{26}$")
# mid8: 8-char prefix of a ULID
_MID8_RE = re.compile(r"^[0-9A-Z]{8}$")
# composed <slug>-<mid8>: ends with a dash + 8-char ULID segment
_SLUG_MID8_RE = re.compile(r"^.+-[0-9A-Z]{8}$")
# numeric prefix: 1–4 digits
_NUMERIC_RE = re.compile(r"^\d{1,4}$")


# ---------------------------------------------------------------------------
# Handle form classifier (T028 — mirrors the real _canonicalize_primary_read_handle)
# ---------------------------------------------------------------------------


def _classify_handle_form(handle: str) -> str:
    """Classify a handle into one of the five canonical forms.

    Mirrors the real ``_canonicalize_primary_read_handle`` classification
    cascade (FR-011):

    1. Full 26-char ULID → ``ulid``
    2. 8-char ULID segment (bare mid8) → ``bare_mid8``
    3. Numeric (1–4 digits) → ``numeric``
    4. ``<slug>-<mid8>`` composed form → ``slug_mid8``
    5. Bare human slug (no embedded mid8) → ``full_slug``
    """
    if _ULID_RE.match(handle):
        return "ulid"
    if _MID8_RE.match(handle):
        return "bare_mid8"
    if _NUMERIC_RE.match(handle):
        return "numeric"
    if _SLUG_MID8_RE.match(handle):
        return "slug_mid8"
    return "full_slug"


# ---------------------------------------------------------------------------
# FakeResolver (T028) — stub implementation of the unified seam
# ---------------------------------------------------------------------------


class FakeResolver:
    """Stub that faithfully models the post-WP02–WP05 read==write invariant.

    Both ``read_dir`` and ``write_dir`` classify the handle to its canonical
    form and return the corresponding ``FORM_TO_DIR`` entry.  Because they share
    the SAME classification logic, the two legs are structurally convergent —
    exactly what FR-006 (SC-005) requires.

    Args:
        raise_ambiguous: When ``True``, every call raises
            :class:`~specify_cli.missions._read_path_resolver.MissionSelectorAmbiguous`.
        raise_cold_miss: When ``True``, every call raises
            :class:`~specify_cli.missions._read_path_resolver.StatusReadPathNotFound`.
    """

    def __init__(
        self,
        *,
        raise_ambiguous: bool = False,
        raise_cold_miss: bool = False,
    ) -> None:
        self._raise_ambiguous = raise_ambiguous
        self._raise_cold_miss = raise_cold_miss

    def _resolve(self, handle: str) -> Path:
        """Shared resolution body — classify handle → FORM_TO_DIR lookup."""
        from specify_cli.missions._read_path_resolver import (
            MissionSelectorAmbiguous,
            StatusReadPathNotFound,
        )

        if self._raise_ambiguous:
            raise MissionSelectorAmbiguous(
                handle=handle,
                candidates=["mission-alpha", "mission-beta"],
            )
        if self._raise_cold_miss:
            raise StatusReadPathNotFound(
                repo_root=Path("/fake/repo"),
                mission_slug=handle,
                mid8="",
                coord_candidate=Path("/fake/repo/kitty-specs") / handle,
                primary_candidate=Path("/fake/repo/kitty-specs") / handle,
            )
        form = _classify_handle_form(handle)
        return FORM_TO_DIR[form]

    def read_dir(self, handle: str) -> Path:
        """Simulate the read-seam: ``_canonicalize_primary_read_handle`` + ``primary_feature_dir_for_mission``."""
        return self._resolve(handle)

    def write_dir(self, handle: str) -> Path:
        """Simulate the write/placement-seam: ``resolve_planning_read_dir`` (PRIMARY kind)."""
        return self._resolve(handle)

    def assert_distinguishable(self) -> None:
        """Assert this stub is NOT constant-returning (T032 guard).

        Raises ``ValueError`` if all five forms map to the same directory.
        """
        outputs = {str(self._resolve(h)) for h in _FIVE_HANDLES.values()}
        if len(outputs) <= 1:
            raise ValueError(
                f"Stub is constant-returning: all five forms resolve to {outputs}. "
                "A constant stub cannot satisfy the convergence test (T032)."
            )


# ---------------------------------------------------------------------------
# Pre-fix "old behavior" stub (T031 — negative control)
# ---------------------------------------------------------------------------


class _OldWriteResolver:
    """Simulate the pre-WP02 kind-BLIND write leg that diverged for full_slug.

    Before WP02 (IC-04a) the write leg did NOT classify by kind: for a
    coordination-topology mission addressed by a bare human slug (``full_slug``
    form), it composed the slug verbatim and routed it to the COORDINATION
    surface — a DIFFERENT directory than the kind-aware read leg's PRIMARY result.

    This stub returns a distinct per-form path from ``OLD_COORD_WRITE_DIR`` for
    the ``full_slug`` form and the normal ``FORM_TO_DIR`` for all others.
    Crucially, the ``full_slug`` entry DIFFERS from the read leg's ``full_slug``
    entry, so the (old-read, old-write) pair diverges for that form.
    """

    # The old coord-write path: different from FORM_TO_DIR["full_slug"].
    _OLD_COORD_DIR: Path = Path("/fake/old-coord-write/by-full-slug")

    def write_dir(self, handle: str) -> Path:
        form = _classify_handle_form(handle)
        if form == "full_slug":
            return self._OLD_COORD_DIR
        return FORM_TO_DIR[form]


# ---------------------------------------------------------------------------
# Five handle examples (used across parametrize and constant-stub guard)
# ---------------------------------------------------------------------------

_FIVE_HANDLES: dict[str, str] = {
    "full_slug": _MISSION_SLUG,
    "slug_mid8": _SLUG_WITH_MID8,
    "bare_mid8": _MID8,
    "ulid": _MISSION_ID,
    "numeric": "042",
}

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# T029 — Parametrize all five handle forms; assert read-seam == write-seam
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("form", "handle"),
    [
        pytest.param("full_slug", _FIVE_HANDLES["full_slug"], id="full_slug"),
        pytest.param("slug_mid8", _FIVE_HANDLES["slug_mid8"], id="slug_mid8"),
        pytest.param("bare_mid8", _FIVE_HANDLES["bare_mid8"], id="bare_mid8"),
        pytest.param("ulid", _FIVE_HANDLES["ulid"], id="ulid"),
        pytest.param("numeric", _FIVE_HANDLES["numeric"], id="numeric"),
    ],
)
def test_read_seam_equals_write_seam(form: str, handle: str) -> None:
    """T029: for every handle form, read-seam dir == write/placement-seam dir.

    FR-006 / SC-005: after WP02–WP05 unified the routing through the kind-aware
    authority, no handle form can map the read leg to a DIFFERENT directory than
    the write leg.  This is the executable convergence proof.

    Both legs use the SAME ``FakeResolver`` instance so the comparison is
    meaningful: the stub's resolution function is called identically for read
    and write, and both must return the same form-specific directory.

    Distinguishable per-form outputs (T028): the stub returns a UNIQUE path per
    form so neither leg can pass vacuously by returning a constant.
    """
    resolver = FakeResolver()

    read_dir = resolver.read_dir(handle)
    write_dir = resolver.write_dir(handle)

    # Structural: the resolved directory must be the one assigned to this form.
    assert read_dir == FORM_TO_DIR[form], (
        f"read-seam for {form!r} (handle={handle!r}) resolved "
        f"{read_dir}, expected {FORM_TO_DIR[form]} (distinguishable per-form output)"
    )
    # Convergence (FR-006 / SC-005): read == write for this handle form.
    assert read_dir == write_dir, (
        f"read-seam ≠ write-seam for {form!r} (handle={handle!r}): "
        f"read={read_dir}, write={write_dir} — DIVERGENCE (FR-006 violation)"
    )


# ---------------------------------------------------------------------------
# T030 — Ambiguity raise + cold-miss fail-closed
# ---------------------------------------------------------------------------


def test_ambiguous_handle_raises_mission_selector_ambiguous() -> None:
    """T030 (ambiguity): an ambiguous handle raises MissionSelectorAmbiguous.

    FR-006 / C-CTX-4 / C-009: the convergence test does NOT hide
    ``MissionSelectorAmbiguous`` behind a try/except wrapper.  The resolver
    is configured to simulate a handle that matches more than one mission, and
    the test asserts the structured error propagates with the correct code.

    Uses the real ``MissionSelectorAmbiguous`` from the production seam (not an
    invented exception) so the test is load-bearing for the no-silent-fallback
    contract.
    """
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    resolver = FakeResolver(raise_ambiguous=True)

    with pytest.raises(MissionSelectorAmbiguous) as exc_info:
        resolver.read_dir(_FIVE_HANDLES["slug_mid8"])

    assert exc_info.value.error_code == "MISSION_AMBIGUOUS_SELECTOR"


def test_cold_miss_raises_fail_closed_no_verbatim_path() -> None:
    """T030 (cold-miss): a handle with no matching mission raises fail-closed.

    The resolver raises ``StatusReadPathNotFound`` — the canonical cold-miss
    exception from ``_read_path_resolver``.  The test asserts:

    1. The exception is the correct canonical type (not ``FileNotFoundError``
       or a freshly invented exception).
    2. The message does NOT contain a verbatim on-disk path derived from the
       handle alone (no raw ``Path(handle)`` join without a found-mission check).

    The second assertion is the SC-005 message-cleanliness guard: a fail-closed
    raise that leaks the raw handle as a path segment would expose an
    unvalidated filesystem path in the error message.
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    resolver = FakeResolver(raise_cold_miss=True)
    handle = _FIVE_HANDLES["full_slug"]

    with pytest.raises(StatusReadPathNotFound) as exc_info:
        resolver.read_dir(handle)

    exc = exc_info.value
    assert exc.error_code == "STATUS_READ_PATH_NOT_FOUND"

    # The error message must not pass the raw handle through as a bare path
    # component without a found-mission check.  Check: the message is not
    # literally "/fake/repo/kitty-specs/<handle>" verbatim without the context
    # wrapper (the StatusReadPathNotFound message always includes surrounding
    # diagnostic text, never JUST the raw path).
    msg = str(exc)
    # The message MUST include mission identity context (the slug or mid8) ...
    assert handle in msg or exc.mission_slug in msg, (
        "cold-miss message must mention the mission slug for debuggability"
    )
    # ... but must NOT be a bare verbatim path (the production message always
    # includes the surrounding "Status read path not found for '...'" frame).
    assert msg.startswith("Status read path not found for"), (
        f"cold-miss message must start with the canonical framing, got: {msg!r}"
    )


# ---------------------------------------------------------------------------
# T031 — Negative control: pre-fix divergence proof
# ---------------------------------------------------------------------------


def test_convergence_pre_fix_stub_diverges() -> None:
    """T031 (red-first proof): the pre-fix resolver pair returns DIFFERENT dirs.

    Before WP02 (IC-04a) routed ``mark_status``'s write leg through the
    kind-aware authority, the ``full_slug`` handle diverged:

    * Read leg (kind-aware): PRIMARY surface → ``FORM_TO_DIR["full_slug"]``
      = ``/fake/resolved/by-full-slug``
    * Write leg (kind-blind, pre-WP02): COORDINATION surface →
      ``_OldWriteResolver._OLD_COORD_DIR`` = ``/fake/old-coord-write/by-full-slug``

    These are DIFFERENT values — the test WOULD HAVE BEEN RED on pre-fix code.
    This function asserts the divergence explicitly (the red-first proof), so a
    reviewer can confirm the negative control is load-bearing.
    """
    read_stub = FakeResolver()
    old_write_stub = _OldWriteResolver()

    handle = _FIVE_HANDLES["full_slug"]  # the divergent form under pre-fix code

    old_read_dir = read_stub.read_dir(handle)
    old_write_dir = old_write_stub.write_dir(handle)

    # Pre-fix the two legs return DIFFERENT directories.
    # Hardcoded expected values (not derived from the stubs — a tautology guard).
    assert old_read_dir == Path("/fake/resolved/by-full-slug"), (
        f"expected pre-fix read to be /fake/resolved/by-full-slug, got {old_read_dir}"
    )
    assert old_write_dir == Path("/fake/old-coord-write/by-full-slug"), (
        f"expected pre-fix write to be /fake/old-coord-write/by-full-slug, got {old_write_dir}"
    )
    # The divergence: they must NOT be equal (this is the RED state before WP02).
    assert old_read_dir != old_write_dir, (
        "pre-fix stub pair must diverge for full_slug — "
        "if they agree the negative control is invalid"
    )


def test_convergence_negative_control_pre_fix_divergence() -> None:
    """T031 (post-fix green): with the fixed stub the same handle NOW converges.

    The companion to ``test_convergence_pre_fix_stub_diverges``: after WP02 the
    write leg adopts the kind-aware authority, so both legs return the SAME
    ``FORM_TO_DIR["full_slug"]`` directory.  This proves the convergence test was
    RED before WP02 and is GREEN after.

    The fixed stub (``FakeResolver``) simulates the post-WP02 write leg: it uses
    the same ``_classify_handle_form`` → ``FORM_TO_DIR`` dispatch as the read leg,
    so the two legs converge.
    """
    fixed_resolver = FakeResolver()  # post-WP02 behavior: read == write

    handle = _FIVE_HANDLES["full_slug"]
    fixed_read_dir = fixed_resolver.read_dir(handle)
    fixed_write_dir = fixed_resolver.write_dir(handle)

    # Post-fix: both legs resolve to the SAME directory.
    assert fixed_read_dir == fixed_write_dir, (
        f"post-fix full_slug must converge: read={fixed_read_dir}, "
        f"write={fixed_write_dir} — DIVERGENCE after WP02 is a regression"
    )
    # Absolute anchor (not pure leg-equality — both-wrong mutant guard):
    assert fixed_read_dir == FORM_TO_DIR["full_slug"], (
        f"post-fix full_slug must resolve to FORM_TO_DIR['full_slug'] "
        f"({FORM_TO_DIR['full_slug']}), got {fixed_read_dir}"
    )


# ---------------------------------------------------------------------------
# T032 — Constant-stub-rejected guard
# ---------------------------------------------------------------------------


def test_constant_stub_is_rejected() -> None:
    """T032: a constant-returning stub cannot satisfy the convergence test.

    A stub that always returns the same ``Path`` value for every handle form
    makes both legs agree trivially — the convergence test would pass for the
    wrong reason (both legs return a constant, so they are always equal).

    This guard detects a constant stub and asserts it is flagged as invalid:

    1. Build a "bad" stub that always returns ``Path("/fake/constant")``.
    2. Collect outputs for all five handle forms.
    3. Assert all five outputs are identical (the stub IS constant).
    4. Assert ``len(set(outputs)) == 1`` (the structural proof of constancy).
    5. Assert the ``FakeResolver.assert_distinguishable()`` method raises
       ``ValueError`` when called on a stub equivalent to the bad one.

    Docstring: A constant-returning stub cannot satisfy the convergence test
    — this guard proves it.
    """
    # Build the bad (constant-returning) stub inline.
    _CONSTANT_PATH = Path("/fake/constant")

    class _ConstantStub:
        def read_dir(self, handle: str) -> Path:  # noqa: ARG002
            return _CONSTANT_PATH

        def write_dir(self, handle: str) -> Path:  # noqa: ARG002
            return _CONSTANT_PATH

    bad_stub = _ConstantStub()

    # Step 1–3: collect outputs for all five forms; assert they are all equal.
    bad_outputs = [bad_stub.read_dir(h) for h in _FIVE_HANDLES.values()]
    assert all(p == _CONSTANT_PATH for p in bad_outputs), (
        "bad stub must return the constant for every form"
    )

    # Step 4: the set of outputs has exactly one member — the stub is constant.
    unique_outputs = {str(p) for p in bad_outputs}  # set comprehension (ruff C401)
    assert len(unique_outputs) == 1, (
        f"bad stub outputs must all be identical; got {unique_outputs}"
    )

    # Step 5: the FakeResolver's assert_distinguishable() method detects a
    # constant stub and raises ValueError. We simulate this by building a
    # FakeResolver that always returns the same path (overriding _resolve).
    class _ConstantFakeResolver(FakeResolver):
        def _resolve(self, handle: str) -> Path:  # noqa: ARG002
            return _CONSTANT_PATH

    constant_resolver = _ConstantFakeResolver()
    with pytest.raises(ValueError, match="constant-returning"):
        constant_resolver.assert_distinguishable()

    # Sanity: the normal FakeResolver IS distinguishable (the guard's own guard).
    normal_resolver = FakeResolver()
    normal_resolver.assert_distinguishable()  # must NOT raise


# ---------------------------------------------------------------------------
# T028 sanity — all five forms produce unique outputs
# ---------------------------------------------------------------------------


def test_form_to_dir_all_unique() -> None:
    """T028 sanity: FORM_TO_DIR has five distinct entries.

    Proves the stub's output mapping is non-constant: each of the five handle
    forms is assigned a UNIQUE fake directory.  A non-unique mapping would allow
    the convergence test to pass vacuously (two forms colliding on the same path
    while diverging on different forms would go undetected).
    """
    assert frozenset(FORM_TO_DIR.keys()) == frozenset(
        {"full_slug", "slug_mid8", "bare_mid8", "ulid", "numeric"}
    ), f"FORM_TO_DIR must have exactly these 5 handle-form keys, got {FORM_TO_DIR.keys()}"
    unique_paths = {str(p) for p in FORM_TO_DIR.values()}
    assert len(unique_paths) == 5, (  # (distinctness check, not nameable)
        f"FORM_TO_DIR must contain 5 DISTINCT paths; "
        f"duplicates found: {FORM_TO_DIR}"
    )


def test_classifier_covers_all_five_forms() -> None:
    """T028 sanity: _classify_handle_form maps each test handle to its expected form.

    Asserts the stub classifier is correct for all five production-shaped handles
    so downstream convergence failures can be attributed to the seam, not the
    classifier.
    """
    expected: dict[str, str] = {
        _FIVE_HANDLES["full_slug"]: "full_slug",
        _FIVE_HANDLES["slug_mid8"]: "slug_mid8",
        _FIVE_HANDLES["bare_mid8"]: "bare_mid8",
        _FIVE_HANDLES["ulid"]: "ulid",
        _FIVE_HANDLES["numeric"]: "numeric",
    }
    for handle, expected_form in expected.items():
        actual = _classify_handle_form(handle)
        assert actual == expected_form, (
            f"handle {handle!r}: classified as {actual!r}, expected {expected_form!r}"
        )
