"""`#3111` acceptance — consent laundering through `decision widen` (SC-001, SC-002, SC-003, SC-011, SC-024).

What the defect actually is
---------------------------

``spec-kitty agent decision widen`` resolved the project root from the
**operator's location** while ``decision_id`` is an **operator-supplied
argument**. **The failure is consent LAUNDERING, not unconsented egress**: the
gate at ``saas_client/client.py:157`` runs *before* ``url = ...`` at ``:162``, so
a **non-consenting** checkout already transmits nothing. Standing in *consenting*
project A and widening a decision owned by B sent **B's identifier to A's team,
under A's token**, and every gate answered truthfully — about the wrong project.

**The before-state was OBSERVED, not assumed.** At ``bb2020fea``, from a
consenting A whose ledgers do not list the id, with A's root on
``SPECIFY_REPO_ROOT`` and B's ledger listing it, the transport recorded::

    POST https://saas.example.invalid/a/acme-team-a/collaboration/decision-points/01KZWDENBBBBBBBBBBBBBBBBBB/widen
    {"invited_user_ids": [101]}

— B's ``decision_id`` in the request path, addressed to **A's** ``team_slug``,
under **A's** token. That is what establishes that the absence asserted below
would otherwise have happened. Two controls ran in the same harness: a
**non-consenting** A produced **zero** requests at ``bb2020fea`` too (so a count
of zero proves nothing on its own — assert the **bytes**), and A widening its own
decision produced exactly one (so the harness can send).

Why this module lives in ``tests/specify_cli/saas_client/``
------------------------------------------------------------

Deliberately **inside** the fixture-carrying directory. ``transmitted_text`` is
defined here and is **imported, never re-implemented** — a private copy of the
byte extractor is the single easiest way to make this mission's load-bearing
assertion assert nothing.

**The fabricated-consent trap is gone with its consent gate.** At the time of
writing the closure rested on a conjunction:

.. code-block:: text

    src/specify_cli/saas_client/client.py   from_env: return cls(..., project_root=root,)  <- KEYWORD ALWAYS PASSED
    tests/specify_cli/saas_client/conftest.py  autouse guard injecting only when the kwarg is ABSENT
    tests/sync/tracker/conftest.py             (mirror image, same shape)

Issue #5 deleted the per-project consent gate the guards fed, so both conftest
guards retired with it. The producer half still binds and is still pinned:
``from_env`` passes ``project_root=`` as a keyword even when the value is
``None``, and ``cmd_widen`` reaches the client exclusively through ``from_env``
(``cli/commands/decision.py``) — see
:func:`test_from_env_still_threads_its_repo_root`. The ownership gate keys on
the acting root (``SPECIFY_REPO_ROOT``), which is unaffected.

Route coverage — TWO routes, not four
-------------------------------------

SC-001 requires exactly the operator-supplied ``--mission-slug`` route and **one**
root-shaped route (``SPECIFY_REPO_ROOT``). The three root-shaped routes — cwd,
``SPECIFY_REPO_ROOT``, and the ``or Path.cwd()`` fallback — **converge in
``locate_project_root`` and hold by construction**; three parameterisations of one
code path are one piece of evidence, not three. The slug route is genuinely
different code: new with FR-003, slug-shaped rather than root-shaped.

**STANDING BOUND, and it is what the reduction rests on: if a future change makes
any root-shaped route stop converging at ``locate_project_root``, this reduction
is wrong and SC-001 goes back to four routes.**
"""

from __future__ import annotations

import ast
import json
from kernel.clock import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.saas_client import client as _client_mod
from specify_cli.zeitgeist_client import repo_identity

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Recording transport + fixtures (formerly imported from
# ``test_client_consent_gate_3030``, which retired with the per-project consent
# gate in issue #5 — these helpers outlive it because they observe the transport,
# not the gate)
# ---------------------------------------------------------------------------


class _RecordingResponse:
    status_code = 200
    is_success = True
    text = "{}"

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class RecordingHttp:
    """An ``httpx.Client`` stand-in that records instead of sending."""

    def __init__(self, sink: list[dict[str, Any]]) -> None:
        self._sink = sink
        self._project_slug = "project-a"

    def get(self, url: str, *, timeout: float | None = None) -> _RecordingResponse:
        del timeout
        self._sink.append({"method": "GET", "url": url, "json": None})
        return _RecordingResponse(
            {
                "admitted": True,
                "team": {"id": "42", "slug": TEAM_A},
                "repo_slug": f"acme-holdings/{self._project_slug}",
            }
        )

    def post(self, url: str, *, json: Any = None, headers: dict[str, str] | None = None, timeout: float | None = None) -> _RecordingResponse:
        del headers, timeout
        self._sink.append({"method": "POST", "url": url, "json": json})
        return _RecordingResponse()


def transmitted_text(sink: list[dict[str, Any]]) -> str:
    """Every byte the transport was asked to send — URLs included.

    Defined exactly once and imported by nothing else any more, but still the ONE
    byte extractor every assertion below uses.
    """
    return json.dumps(sink, default=str, sort_keys=True)


def write_project_config(repo_root: Path, *, sync_enabled: bool | None = None) -> None:
    """Write a ``.kittify/config.yaml`` describing the checkout under test.

    ``sync.enabled`` is recorded verbatim when given. It no longer gates anything
    on this path — the hosted-sync consent chain retired with the sync transport —
    but the file stays part of the arrangement because ``from_env`` reads auth
    context relative to a real project root.
    """
    del sync_enabled
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "project:",
        "  uuid: 2b7f6a10-3c4d-4e5f-8a9b-2b7f6a103c4d",
        f"  slug: {repo_root.name}",
        "  node_id: node12345678",
        f"  repo_slug: acme-holdings/{repo_root.name}",
        "  build_id: 8a4a7da6-a97c-4bb4-893a-b31664abfee4",
    ]
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


#: Well-formed 26-character Crockford-base32 ULIDs. Both clauses of SC-001 are
#: load-bearing: without "well-formed", a bare regex satisfies the criterion with
#: no ownership logic at all; without "present in B's ledger and absent from every
#: mission under A", the arrangement does not reproduce the defect.
DECISION_ID_OWNED_BY_B = "01KZWDENBBBBBBBBBBBBBBBBBB"
DECISION_ID_OWNED_BY_A = "01KZWDENAAAAAAAAAAAAAAAAAA"
MALFORMED_DECISION_ID = "01KWIDETEST00000000001"  # 22 chars, contains `I`

A_MISSION = "mission-owned-by-a"
B_MISSION = "mission-owned-by-b"
TEAM_A = "acme-team-a"
TOKEN_A = "token-belonging-to-A"
SAAS_URL = "https://saas.example.invalid"

_REPO_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# Fixture — both checkouts on disk, A's root on SPECIFY_REPO_ROOT
# ---------------------------------------------------------------------------


def _write_ledger(repo_root: Path, slug: str, *decision_ids: str) -> Path:
    decisions = repo_root / "kitty-specs" / slug / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    mission_id = "01KZMISSION0000000000000ZA"
    payload = {
        "version": 1,
        "mission_id": mission_id,
        "entries": [
            {
                "decision_id": d,
                "origin_flow": "plan",
                "step_id": "step-1",
                "input_key": "key",
                "question": "q?",
                "status": "open",
                "created_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
                "mission_id": mission_id,
                "mission_slug": slug,
            }
            for d in decision_ids
        ],
    }
    (decisions / "index.json").write_text(json.dumps(payload), encoding="utf-8")
    return decisions.parent


class Harness:
    """The two checkouts, the recording transport, and the clients actually built."""

    def __init__(self, a_root: Path, b_root: Path) -> None:
        self.a_root = a_root
        self.b_root = b_root
        self.sink: list[dict[str, Any]] = []
        self.clients: list[Any] = []

    def widen(self, decision_id: str, *extra: str) -> Any:
        """Run the REAL invocation (C-008): ``spec-kitty agent decision widen``.

        There is no top-level ``decision`` typer and ``cmd_widen`` is ``hidden``,
        so the command is reached through the ``agent`` app. The test never
        constructs a client — ``cmd_widen`` does — which is exactly why A's root
        is conveyed through ``SPECIFY_REPO_ROOT`` rather than through a kwarg.
        """
        from specify_cli.cli.commands.agent import app as agent_app

        return CliRunner().invoke(
            agent_app,
            ["decision", "widen", decision_id, "--invited", "101", *extra],
            catch_exceptions=False,
        )


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    """SC-024: **both** checkouts' ``.kittify/config.yaml`` written **on disk**.

    Consent is arranged by the files the real consent chain reads, never by a
    fixture that stubs the answer.
    """
    home = tmp_path / "home"
    a_root = tmp_path / "project-a"
    b_root = tmp_path / "project-b"
    for path in (home, a_root, b_root):
        path.mkdir()

    # Durable consent/admission is machine-scoped. Establish the isolated
    # machine before recording the two projects' genuine positive authority.
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".spec-kitty"))

    # Item 1 — both checkouts consenting, on disk. B consents too, so a refusal is
    # never attributable to B's consent: the only thing that differs is ownership.
    write_project_config(a_root, sync_enabled=True)
    write_project_config(b_root, sync_enabled=True)

    _write_ledger(a_root, A_MISSION, DECISION_ID_OWNED_BY_A)
    _write_ledger(b_root, B_MISSION, DECISION_ID_OWNED_BY_B)

    # Item 2 — A's root conveyed through SPECIFY_REPO_ROOT, the highest-priority
    # tier of ``locate_project_root``. This SUPERSEDES the accepted spec's clause
    # at ``spec.md:1553`, quoted here so nobody "restores" it:
    #
    #     "…writes **both** checkouts' `.kittify/config.yaml` on disk, **passes
    #     both roots explicitly rather than relying on a kwarg default**, and
    #     contains an **in-file positive control**…"
    #
    # The bolded middle clause is not executable under C-008's mandatory real
    # invocation: the test never constructs a client, so there is no kwarg for it
    # to pass. An implementer reconciling the two would construct a client inline,
    # abandoning the real entry point and the FR-003 slug route with it. The spec
    # carries a POST-ACCEPTANCE CORRECTION immediately below SC-024 saying exactly
    # this. The other two clauses of SC-024 are unchanged and still bind (items 1
    # and 3), and the hazard the superseded clause reached for is covered by the
    # ``client._project_root == A_ROOT`` assertion, not by any kwarg.
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(a_root))
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", SAAS_URL)
    monkeypatch.setenv("SPEC_KITTY_SAAS_TOKEN", TOKEN_A)
    monkeypatch.setenv("SPEC_KITTY_TEAM_SLUG", TEAM_A)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    monkeypatch.chdir(a_root)
    monkeypatch.setattr(
        repo_identity,
        "origin_url",
        lambda cwd, deadline: "https://github.com/acme-holdings/project-a.git",
    )

    h = Harness(a_root, b_root)

    # Record at the transport boundary the package documents for tests, and keep
    # every client the command actually built so the compensating assertion can
    # read its ``_project_root``. This layers ON TOP of whatever the directory's
    # autouse fixture installed, so the guard's behaviour is preserved rather
    # than bypassed.
    current_init = _client_mod.SaasClient.__init__

    def _init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs["_http"] = RecordingHttp(h.sink)
        current_init(self, *args, **kwargs)
        h.clients.append(self)

    monkeypatch.setattr(_client_mod.SaasClient, "__init__", _init)
    return h


# ---------------------------------------------------------------------------
# SC-001 / SC-011 — the two divergence routes
# ---------------------------------------------------------------------------


def test_sc001_route_specify_repo_root_refuses_and_transmits_no_bytes(
    harness: Harness,
) -> None:
    """Route 1 (root-shaped): consenting A, ULID present in B's ledger, absent from A's.

    **The byte assertion comes FIRST; the count is corroboration only.** A count
    of zero is also what an unrelated upstream short-circuit produces — and a
    non-consenting checkout already produced zero at ``bb2020fea``.
    """
    result = harness.widen(DECISION_ID_OWNED_BY_B)

    assert DECISION_ID_OWNED_BY_B not in transmitted_text(harness.sink), f"B's decision_id reached the transport from A's checkout: {harness.sink!r}"
    assert harness.sink == []
    assert result.exit_code == 1
    assert str(harness.a_root) in result.output, "the refusal must name the acting root"
    assert "git pull" in result.output, "the refusal must name the operator action"


def test_sc001_route_mission_slug_refuses_and_transmits_no_bytes(
    harness: Harness,
) -> None:
    """Route 2 (slug-shaped): genuinely different code, new with FR-003.

    **DECLARED BEHAVIOUR CHANGE.** At ``bb2020fea`` a ``--mission-slug`` that
    disagrees with the record succeeded, because the flag was silently ignored on
    the live path. Making it stop is the *point* of FR-003. Under the
    within-checkout search the slug is a **narrowing hint over the acting
    checkout's own missions**, never an instruction to look elsewhere — so a slug
    naming a mission A does not contain is an ownership failure, not a
    redirection.
    """
    result = harness.widen(DECISION_ID_OWNED_BY_B, "--mission-slug", B_MISSION)

    assert DECISION_ID_OWNED_BY_B not in transmitted_text(harness.sink)
    assert harness.sink == []
    assert result.exit_code == 1


def test_fr003_slug_differential_within_one_checkout_flips_the_outcome(
    harness: Harness,
) -> None:
    """FR-003's mandated differential, and the ONLY form of it that can fail.

    FR-003 (``spec.md:446``): *"holding ``decision_id``, cwd and ``--invited``
    fixed, changing ``--mission-slug`` from the owning mission to a non-owning
    mission **of the same checkout** must flip the outcome from one request to
    zero."*

    **The pre-existing slug test cannot see this, and that was measured.** It passes
    ``--mission-slug B_MISSION`` — a mission the acting checkout does **not**
    contain — so ``resolve_decision_ownership`` answers ``owned=False`` with the
    slug *and* without it. Rewriting ``decision.py``'s
    ``mission_slug=mission_slug`` to ``mission_slug=None`` — FR-003's exact
    regression — left **70 tests green**. The unit-level differential exercises the
    resolver, not the CLI threading, so it does not close it either.

    Both halves live in one test on purpose: the refusal half alone is satisfiable
    by a gate that refuses everything, and the transmit half alone is satisfiable by
    one that refuses nothing. Only the *flip* is evidence, and only when both slugs
    name missions this checkout really has.
    """
    # A second mission under A that does NOT list the decision. Same checkout, so
    # the only thing distinguishing the two invocations is the slug itself.
    _write_ledger(harness.a_root, "mission-other-of-a", DECISION_ID_OWNED_BY_B)

    # Half 1 — the OWNING slug transmits. Without this the flip is unprovable.
    owning = harness.widen(DECISION_ID_OWNED_BY_A, "--mission-slug", A_MISSION)
    assert owning.exit_code == 0, owning.output
    assert sum(record["method"] == "POST" for record in harness.sink) == 1, (
        f"the owning slug must still transmit exactly one collaboration request; if it refuses, the differential below proves nothing: {harness.sink!r}"
    )
    assert DECISION_ID_OWNED_BY_A in transmitted_text(harness.sink)

    harness.sink.clear()

    # Half 2 — a NON-OWNING slug in the SAME checkout refuses. This is the half
    # that reds if the CLI stops threading the flag: without the slug the search
    # finds the decision under A_MISSION and sends.
    non_owning = harness.widen(DECISION_ID_OWNED_BY_A, "--mission-slug", "mission-other-of-a")
    assert harness.sink == [], (
        "FR-003 REGRESSION: a non-owning --mission-slug in the acting checkout did "
        "not narrow the search, so the decision was found under another of A's "
        "missions and transmitted. This is the flag being ignored on the live path — "
        f"the exact behaviour FR-003 exists to stop: {harness.sink!r}"
    )
    assert non_owning.exit_code == 1, non_owning.output


def test_sc011_no_request_line_addressed_to_as_team_carries_bs_decision_id(
    harness: Harness,
) -> None:
    """SC-011, stated in its own terms rather than folded into a count.

    The consent-laundering defect is *"a well-formed ULID owned by B, transmitted
    to A's team under A's token"*, and it was previously covered by request
    **count** alone.
    """
    harness.widen(DECISION_ID_OWNED_BY_B)

    addressed_to_a = [rec for rec in harness.sink if TEAM_A in str(rec.get("url", ""))]
    assert addressed_to_a == []
    assert not any(DECISION_ID_OWNED_BY_B in str(rec) for rec in harness.sink), f"a request line carried B's identifier: {harness.sink!r}"


# ---------------------------------------------------------------------------
# SC-002 — the positive control, in this module and from the SAME fixture
# ---------------------------------------------------------------------------


def test_sc002_positive_control_owning_checkout_still_transmits_exactly_one_request(
    harness: Harness,
) -> None:
    """SC-001's positive control AND its **auth** control, built from the same fixture.

    Co-listing would let an implementer satisfy each from a different
    arrangement. It is also the only thing in the spec that reds on the third
    short-circuit no clause of SC-001 closes: an **unauthenticated** fixture also
    sends zero requests at ``bb2020fea`` (``saas_client/auth.py`` →
    ``errors.py`` → caught in ``cmd_widen``). **A green SC-001 alone is not
    evidence that the fix works; the pair is.**

    This also carries **item 9, the compensating runtime assertion** for the
    two-file fabricated-consent conjunction: the client the command actually
    built must carry **A's on-disk root**, not a root a conftest arranged.
    """
    result = harness.widen(DECISION_ID_OWNED_BY_A)

    assert result.exit_code == 0, result.output
    assert len(harness.sink) == 2, f"expected one admission lookup and one collaboration request, got {harness.sink!r}"
    assert harness.sink[0]["method"] == "GET"
    assert "/api/v1/sync/repo-admission/" in harness.sink[0]["url"]

    request = next(record for record in harness.sink if record["method"] == "POST")
    assert request["method"] == "POST"
    assert request["url"] == (f"{SAAS_URL}/a/{TEAM_A}/collaboration/decision-points/{DECISION_ID_OWNED_BY_A}/widen"), "same endpoint as before the fix"
    assert request["json"] == {"invited_user_ids": [101]}, "same payload as before the fix"

    # Item 9 (mandatory). This reds the moment either side of the fabricated-consent
    # falsifier changes — which neither the byte assertion nor the refusal does,
    # because both discriminate on SPECIFY_REPO_ROOT rather than on project_root.
    assert len(harness.clients) == 1
    assert harness.clients[0]._project_root == harness.a_root, (
        "the client the command built must carry A's ON-DISK root; a different "
        "root here means consent was resolved for a project the operator is not "
        "standing in — including one an autouse fixture fabricated"
    )


def test_sc002_clause_c_unreadable_ledger_must_not_veto_a_hit_elsewhere(harness: Harness, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-002 clause (c), the MUST-NOT-VETO half. Its REFUSE half lives in
    ``tests/specify_cli/decisions/test_ownership_3111.py`` and neither discharges
    the other.

    **Why this is not optional.** An implementation that refuses on *any*
    unreadable index passes **every other criterion in this spec** while breaking
    widen invocations that succeed today because of one corrupt ``index.json`` in
    an unrelated mission — measured: **49 ledgers across 333 mission dirs** in
    this repository. It is also **the one fall-through variant SC-001 does not
    catch**, because no request carrying B's identifier is involved. Without this
    test the risk is invisible.

    **THIS TEST WAS VACUOUS AND THE VACUITY WAS INVISIBLE FROM ITS OWN TEXT.**
    It named the corrupt mission ``mission-x-corrupt`` and asserted, in prose,
    that "mission x sorts before mission y, so the corrupt ledger is genuinely
    traversed before the hit". That claim was false: the ``harness`` fixture
    already writes ``mission-owned-by-a``, which *contains the id this test
    widens*, and ``mission-owned-by-a`` < ``mission-x-corrupt``. The search hit it
    on the first iteration and broke before ever opening the corrupt ledger.
    Measured: ``missions_searched=('mission-owned-by-a',)``,
    ``unreadable_ledgers=()``.

    The consequence: installing the exact wrong implementation R12 names — veto
    on *any* unreadable ledger — left **all eight tests in this module green**.
    The one criterion the spec flags as the invisible risk could not fail, and
    this is also one of MUT-3's two mandated controls, so half that control set
    was a vacuous green.

    Two changes make it real, and the second is what stops it regressing:

    * the corrupt mission is named to sort **before every mission that can
      answer**, including the fixture's own; and
    * the traversal is **anchored by measurement, not by a sort-order claim in a
      docstring** — a ``load_index`` spy asserts the corrupt mission really was
      opened. A future rename can no longer silently re-vacuate this test; it
      reds instead.
    """
    from specify_cli.decisions import store

    recorded: list[Path] = []
    real_load_index = store.load_index

    def _spy(mission_dir: Path):  # type: ignore[no-untyped-def]
        recorded.append(mission_dir)
        return real_load_index(mission_dir)

    monkeypatch.setattr(store, "load_index", _spy)

    # Sorts before the fixture's own `mission-owned-by-a`, which carries the id
    # under test. Without that, the search short-circuits before reaching this.
    corrupt = _write_ledger(harness.a_root, "mission-000-corrupt", DECISION_ID_OWNED_BY_B)
    (corrupt / "decisions" / "index.json").write_text("{not json", encoding="utf-8")
    _write_ledger(harness.a_root, "mission-y-owner", DECISION_ID_OWNED_BY_A)

    result = harness.widen(DECISION_ID_OWNED_BY_A)

    assert any(p.name == "mission-000-corrupt" for p in recorded), (
        "ANTI-VACUITY: the corrupt ledger was never traversed, so this test "
        "proves nothing about not-vetoing. A mission that sorts earlier and "
        "answers the query short-circuits the search. Recorded traversal: "
        f"{[p.name for p in recorded]}"
    )

    assert result.exit_code == 0, result.output
    requests = [record for record in harness.sink if record["method"] == "POST"]
    assert len(requests) == 1, f"an unreadable ledger in a mission that is NOT the answer vetoed a positive hit elsewhere: {result.output}"
    assert requests[0]["url"].endswith(f"/decision-points/{DECISION_ID_OWNED_BY_A}/widen")
    assert requests[0]["json"] == {"invited_user_ids": [101]}


# ---------------------------------------------------------------------------
# SC-003 — the shape check, asserted against the REQUEST
# ---------------------------------------------------------------------------


def test_sc003_malformed_decision_id_never_appears_in_a_constructed_request_line(
    harness: Harness,
) -> None:
    """Asserted against the request, never the response — a 404 is not evidence of
    non-disclosure.

    ``01KWIDETEST00000000001`` is 22 characters and contains ``I``. It is also the
    literal the pre-existing ``test_decision_widen_subcommand.py`` fixture used
    before this work package corrected it — **by correcting the fixture, not by
    loosening the check.**
    """
    result = harness.widen(MALFORMED_DECISION_ID)

    assert MALFORMED_DECISION_ID not in transmitted_text(harness.sink)
    assert harness.sink == []
    assert result.exit_code == 1
    assert "ULID" in result.output


# ---------------------------------------------------------------------------
# Q5 — --dry-run warns, it does not refuse
# ---------------------------------------------------------------------------


def test_dry_run_surfaces_the_ownership_verdict_without_transmitting(
    harness: Harness,
) -> None:
    """Dry-run transmits nothing, so it is not an egress path and must not refuse.

    But it **must** surface the verdict, or dry-run becomes a way to get the id
    formatted for copy-paste into a real invocation without ever seeing the
    mismatch.
    """
    result = harness.widen(DECISION_ID_OWNED_BY_B, "--dry-run")

    assert result.exit_code == 0
    assert harness.sink == []
    payload = json.loads(result.output)
    assert payload["ownership"]["owned"] is False
    assert payload["ownership"]["warning"] is not None
    assert str(harness.a_root) in payload["ownership"]["acting_root"]


# ---------------------------------------------------------------------------
# The two-file falsifier for the fabricated-consent trap
# ---------------------------------------------------------------------------


#: The construction whose kwargs decide whether the trap is armed. ``from_env``
#: is a ``classmethod``, so in-tree it reads ``cls(...)``; a refactor to the
#: explicit class name must be watched too or the check is trivially evaded.
_CLIENT_CTORS = frozenset({"cls", "SaasClient"})


def _client_constructions(source: str) -> list[ast.Call]:
    """Every ``cls(...)`` / ``SaasClient(...)`` call inside ``from_env``.

    Returns the calls rather than a verdict so the caller can both count them (the
    anti-vacuity half) and check them (the property half).
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name != "from_env":
            continue
        return [call for call in ast.walk(node) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in _CLIENT_CTORS]
    return []


def _from_env_always_passes_project_root(source: str) -> bool:
    """True when **every** client construction in ``from_env`` passes ``project_root=``.

    **LOW-4: this check used to be narrower than the sentence above it.** It asked
    whether *some* call in ``from_env`` passed the kwarg — so a ``from_env``
    refactored to::

        if root is not None:
            return cls(..., project_root=root)
        return cls(...)

    satisfied it while reopening the fabricated-consent trap on exactly the
    ``None`` branch the docstring named, which is the only branch where the
    autouse guards' ``if "project_root" not in kwargs`` can fire. A falsifier that
    passes on the code it exists to reject is not a weak falsifier, it is a
    decoration.

    Two conditions, and the first is what stops the tightening from being vacuous
    in the other direction: there must be **at least one** such construction (a
    ``from_env`` that builds no client at all must not read as compliant), and
    **all** of them must pass the keyword. Controlled against synthetic good and
    bad sources in
    :func:`test_the_producer_side_falsifier_rejects_the_branched_form`.
    """
    constructions = _client_constructions(source)
    if not constructions:
        return False
    return all(any(kw.arg == "project_root" for kw in call.keywords) for call in constructions)


def test_from_env_still_threads_its_repo_root(harness: Harness) -> None:
    """The surviving half of the old fabricated-consent falsifier.

    The consumer side of that falsifier watched two conftest autouse guards that
    injected a consenting project when ``project_root=`` was absent — machinery
    that retired with the per-project consent gate (issue #5), along with
    ``tests/sync/tracker/conftest.py``. What survives here is the producer side:
    ``from_env`` passes its root as ``project_root=`` unconditionally, so no
    construction site can silently build an unattributed client.
    """
    client_py = _REPO_ROOT / "src" / "specify_cli" / "saas_client" / "client.py"
    assert client_py.is_file(), f"falsifier target missing: {client_py}"

    assert _from_env_always_passes_project_root(client_py.read_text(encoding="utf-8")), (
        f"{client_py}: from_env stopped passing project_root= unconditionally, so a "
        f"caller that omits its repo_root now builds an unattributed client instead "
        f"of a refusing one."
    )


#: Synthetic ``from_env`` bodies, each a KNOWN ANSWER for the producer-side
#: check. Controlling a falsifier against these is not busywork: the check reads
#: the real ``client.py``, which is currently compliant, so on its own it is a
#: green that cannot distinguish a working check from ``return True``.
_GOOD_FLAT = """
class SaasClient:
    @classmethod
    def from_env(cls, repo_root=None):
        root = Path(str(repo_root)) if repo_root is not None else None
        ctx = load_auth_context(repo_root=root)
        return cls(base_url=ctx.saas_url, token=ctx.token, project_root=root)
"""

#: THE FORM THE OLD CHECK ACCEPTED. `project_root=` is passed on one branch, so
#: "some call passes it" holds — while the `None` branch, the only one the autouse
#: guards can fire on, omits it.
_BAD_BRANCHED = """
class SaasClient:
    @classmethod
    def from_env(cls, repo_root=None):
        root = Path(str(repo_root)) if repo_root is not None else None
        ctx = load_auth_context(repo_root=root)
        if root is not None:
            return cls(base_url=ctx.saas_url, token=ctx.token, project_root=root)
        return cls(base_url=ctx.saas_url, token=ctx.token)
"""

#: The assign-then-return spelling of the same hole — the returned object is not
#: syntactically the call, so a check that only inspected ``return`` statements
#: would miss it.
_BAD_ASSIGNED = """
class SaasClient:
    @classmethod
    def from_env(cls, repo_root=None):
        ctx = load_auth_context(repo_root=None)
        client = cls(base_url=ctx.saas_url, token=ctx.token)
        return client
"""

#: Anti-vacuity for the "at least one construction" clause: a ``from_env`` that
#: builds no client must not read as compliant just because nothing violated the
#: rule. ``all([])`` is ``True``, which is precisely how this class of check dies.
_BAD_NO_CONSTRUCTION = """
class SaasClient:
    @classmethod
    def from_env(cls, repo_root=None):
        raise NotImplementedError
"""


def test_the_producer_side_falsifier_rejects_the_branched_form() -> None:
    """LOW-4 — the check is controlled against known answers, in both directions.

    The producer-side check's docstring claimed ``from_env`` passes
    ``project_root=`` **unconditionally**; the check only required *some* call in
    ``from_env`` to pass it. ``_BAD_BRANCHED`` below is the gap made concrete: it
    **passed the old check** and reopens the fabricated-consent trap on exactly
    the ``None`` branch the docstring names.

    This test is the reason the tightening is not itself a decoration. The
    falsifier reads the real ``client.py``, which is compliant today — so a green
    there is equally consistent with a working check and with one that always
    returns ``True``. Only a known-bad input can tell those apart.
    """
    sources = {
        "flat (in-tree form)": (_GOOD_FLAT, True),
        "branched return": (_BAD_BRANCHED, False),
        "assigned then returned": (_BAD_ASSIGNED, False),
        "no construction at all": (_BAD_NO_CONSTRUCTION, False),
    }

    for label, (source, expected) in sources.items():
        assert _from_env_always_passes_project_root(source) is expected, (
            f"producer-side check gave the wrong answer for the {label!r} form: "
            f"expected {expected}, and for the branched form specifically a True "
            f"here is the LOW-4 defect restored — the check would accept a "
            f"from_env whose None branch omits project_root=, which is the only "
            f"branch the autouse guards can fire on"
        )

    # Print the input count alongside the verdict: "all checks passed" over an
    # empty or truncated input set is the failure mode this line exists to expose.
    assert len(sources) == 4, f"expected 4 controlled sources, got {len(sources)}"


def test_symlinked_specs_root_does_not_launder_consent_end_to_end(harness: Harness, tmp_path: Path) -> None:
    """HIGH-2 at the transport, asserting the BYTES.

    The unit-level pin lives in ``test_ownership_3111.py``. This is the half that
    matters: before the fix, pointing A's ``kitty-specs/`` at B's produced

        exit_code=0  requests=1  DID_B in transmitted = True
        POST .../a/acme-team-a/collaboration/decision-points/<B's id>/widen

    — ``#3111``'s request line **verbatim**: B's identifier, A's ``team_slug``,
    A's token, from the code written to prevent exactly that. A count assertion
    would not have caught the regression that mattered, because the pre-fix
    behaviour was *one* request, not zero; only the bytes separate the two.
    """
    # Point A's specs root at B's. B genuinely owns DECISION_ID_OWNED_BY_B.
    a_specs = harness.a_root / "kitty-specs"
    if a_specs.is_symlink() or a_specs.exists():
        for child in sorted(a_specs.iterdir()):
            if child.is_dir():
                __import__("shutil").rmtree(child)
        a_specs.rmdir()
    a_specs.symlink_to(harness.b_root / "kitty-specs", target_is_directory=True)

    result = harness.widen(DECISION_ID_OWNED_BY_B)

    assert DECISION_ID_OWNED_BY_B not in transmitted_text(harness.sink), (
        "CONSENT LAUNDERING via a symlinked kitty-specs/: B's decision_id reached "
        "the transport from A's checkout, addressed to A's team under A's token — "
        f"the #3111 defect respelled. Recorded: {harness.sink!r}"
    )
    assert harness.sink == [], f"nothing may be transmitted at all: {harness.sink!r}"
    assert result.exit_code == 1, result.output


def test_symlinked_decisions_dir_does_not_launder_consent_end_to_end(harness: Harness, tmp_path: Path) -> None:
    """MEDIUM-4 at the transport, asserting the BYTES.

    The specs-root case is pinned above; this is the same laundering two levels
    deeper, where the mission directory is genuinely local and only the ledger
    beneath it is foreign. Before the fix: ``exit 0``, one request, B's
    ``decision_id`` in the URL under A's ``team_slug`` and token.
    """
    mine = harness.a_root / "kitty-specs" / "mission-mine"
    mine.mkdir(parents=True, exist_ok=True)
    (mine / "decisions").symlink_to(harness.b_root / "kitty-specs" / B_MISSION / "decisions", target_is_directory=True)

    result = harness.widen(DECISION_ID_OWNED_BY_B)

    assert DECISION_ID_OWNED_BY_B not in transmitted_text(harness.sink), (
        "CONSENT LAUNDERING via a symlinked <mission>/decisions/: B's decision_id "
        "reached the transport from A's checkout under A's token — #3111 respelled "
        f"at a depth the mission-directory containment check cannot see. {harness.sink!r}"
    )
    assert harness.sink == [], f"nothing may be transmitted: {harness.sink!r}"
    assert result.exit_code == 1, result.output
