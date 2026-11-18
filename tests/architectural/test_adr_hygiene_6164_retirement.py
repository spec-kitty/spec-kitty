"""ADR-hygiene gate for the hosted surfaces retired by #6164 (#7683).

#6164 removed the hosted, sync and drain surfaces and their clients from open-core
(auth, hosted interaction, the SaaS clients, the hosted tracker providers, the drain
posture); the code is preserved in ``spec-kitty/event-router``. ADR ``2026-10-06-1``
records the removal (Amendment 2026-10-14). ADRs whose decision governed one of those
surfaces still read ``Accepted`` / ``active``, so the docs site showed them as live
decisions. This gate keeps the record honest, the same way
``test_adr_hygiene_convergence_retirement.py`` does for the Convergence:

* each retired-surface ADR is ``status: Superseded`` and ``doc_status: superseded`` and
  names its superseding record in ``superseded_by``;
* each superseding record lists it under ``supersedes`` and is itself ``Accepted``.

The dual-repository ADR (2.x ``2026-01-27-11``) is in the inventory because the issue
names it, but its decision (a private events repository pinned by commit) was replaced by
PyPI exact pinning (2.x ``2026-02-11-6``), not by #6164; it points there.

Frontmatter only: ADR bodies are immutable (ADR ``2026-10-31-1`` D-7).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]

_RETIREMENT_6164 = "docs/adr/4.x/2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md"
_PYPI_PINNING = "docs/adr/2.x/2026-02-11-6-pypi-exact-pinning-for-spec-kitty-events.md"

#: Retired-surface ADR -> the record that superseded it.
_SUPERSEDED: dict[str, str] = {
    "docs/adr/2.x/2026-01-27-12-two-branch-strategy-for-saas-transformation.md": _RETIREMENT_6164,
    "docs/adr/2.x/2026-02-27-3-saas-tracker-integration-via-existing-connectors-journey.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-04-04-1-tracker-binding-context-is-discovered-not-user-supplied.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-04-06-2-connector-auth-binding-separation.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-04-06-3-github-app-installation-authority.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-04-21-1-private-teamspace-and-repository-sharing-boundary.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-04-26-2-auth-transport-boundary.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-05-18-2-delete-specify-cli-auth-transport.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-08-04-1-egress-consent-boundary.md": _RETIREMENT_6164,
    "docs/adr/3.x/2026-09-26-3-hosted-interaction-opt-in.md": _RETIREMENT_6164,
    "docs/adr/2.x/2026-01-27-11-dual-repository-pattern.md": _PYPI_PINNING,
}


def _front_matter(text: str) -> dict[str, object]:
    """Parse a leading ``---`` YAML block; ``{}`` when there is none. Pure over its input."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    parsed = yaml.safe_load(text[3:end])
    return parsed if isinstance(parsed, dict) else {}


def _supersession_problem(fm: dict[str, object], superseded_by: str) -> str | None:
    """Why *fm* is not a valid supersession by *superseded_by*, or ``None``. Pure over its input."""
    if fm.get("status") != "Superseded":
        return f"status is {fm.get('status')!r}, not 'Superseded'"
    if fm.get("doc_status") != "superseded":
        return f"doc_status is {fm.get('doc_status')!r}, not 'superseded'"
    if fm.get("superseded_by") != superseded_by:
        return f"superseded_by is {fm.get('superseded_by')!r}, not {superseded_by!r}"
    return None


def _read_front_matter(rel: str) -> dict[str, object]:
    return _front_matter((_REPO_ROOT / rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize(("adr", "superseded_by"), sorted(_SUPERSEDED.items()))
def test_retired_surface_adr_is_superseded_and_names_its_successor(adr: str, superseded_by: str) -> None:
    problem = _supersession_problem(_read_front_matter(adr), superseded_by)

    assert problem is None, f"{adr}: {problem}"


@pytest.mark.parametrize("record", sorted(set(_SUPERSEDED.values())))
def test_superseding_record_is_accepted_and_lists_what_it_supersedes(record: str) -> None:
    fm = _read_front_matter(record)
    expected = sorted(adr for adr, by in _SUPERSEDED.items() if by == record)

    assert fm.get("status") == "Accepted", f"{record} must stay Accepted"
    supersedes = fm.get("supersedes")
    assert isinstance(supersedes, list), f"{record} must declare a `supersedes:` list"
    assert sorted(str(entry) for entry in supersedes) == expected


def test_supersession_check_is_non_vacuous() -> None:
    """Proof of teeth: a still-Accepted, still-active ADR, or a missing pointer, is refused."""
    assert _supersession_problem({"status": "Accepted", "doc_status": "active"}, _RETIREMENT_6164)
    assert _supersession_problem({"status": "Superseded", "doc_status": "active"}, _RETIREMENT_6164)
    assert _supersession_problem({"status": "Superseded", "doc_status": "superseded"}, _RETIREMENT_6164)
    assert (
        _supersession_problem(
            {"status": "Superseded", "doc_status": "superseded", "superseded_by": _RETIREMENT_6164},
            _RETIREMENT_6164,
        )
        is None
    )
    assert _front_matter("no front matter") == {}
