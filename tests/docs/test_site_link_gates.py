"""Acceptance tests for the docsite link-gate wrapper (#6932; ADR 2026-10-31-1 D-11; priced debt #7489).

``scripts/docs/site_link_gates.py`` runs a doc-kitty link gate (``dockitty-check-links``
or ``dockitty-assert-no-broken-links``), parses every problem it reports and fails
on any problem that ``site/link-debt.json`` does not list. The list may hold only
problems whose source page is immutable history (``_dockitty_contract.is_immutable``):
an entry from an editable page fails, whether or not the problem still occurs. An
entry that no longer occurs is reported and does not fail (no ratchet).

The fixtures are the gates' real output shapes; each mutant plants one problem.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

ADR = "adr/3.x/2026-01-01-1-old-decision.md"
GUIDE = "guides/live.md"

CHECK_LINKS_OUT = (
    "check-links: DK_PUBLISH_DRAFTS=off (from: env file; site root: .; mode: production)\n"
    "excluded folders: archive, reports (from astro.config.mjs)\n"
    f"✖ ../docs/{ADR}: link leaves the docs tree, so on a built site it is a 404"
    " — link to a page inside the docs tree, or use an absolute URL → ../../../src/x.py\n"
    "\n1 link problem(s) in 1 file(s); 3 file(s) scanned, 9 reference(s) checked.\n"
)

BUILT_LINKS_OUT = (
    "assert-no-broken-links: FAILED — 1 broken internal link(s) or external image(s):\n"
    "  ✖ adr/3.x/2026-01-01-1-old-decision/index.html → ../../../src/x.py (resolved: /src/x.py): no matching page or file in dist\n"
)


def _gates() -> ModuleType:
    return importlib.import_module("scripts.docs.site_link_gates")


def _write(root: Path, rel: str, text: str = "---\ntitle: t\ndoc_status: active\n---\n") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    _write(root, ADR)
    _write(root, GUIDE)
    _write(root, "index.md")
    return root


def _entry(gate: str, source: str, target: str = "../../../src/x.py") -> dict[str, str]:
    return {"gate": gate, "source": source, "target": target, "reason": "immutable body"}


def _debt(tmp_path: Path, *entries: dict[str, str]) -> Path:
    path = tmp_path / "link-debt.json"
    path.write_text(json.dumps({"$comment": "Priced debt (Standing Order #5)", "entries": list(entries)}), encoding="utf-8")
    return path


def _verdict(gate: str, output: str, docs: Path, debt: Path) -> object:
    module = _gates()
    problems = module.parse(gate, output, docs)
    return module.evaluate(problems, module.load_debt(debt), docs)


# --- parsing the gates' real output -----------------------------------------------------------


def test_check_links_problems_name_the_source_page_and_target(docs: Path) -> None:
    module = _gates()

    (problem,) = module.parse("check-links", CHECK_LINKS_OUT, docs)

    assert (problem.gate, problem.source, problem.target) == ("check-links", ADR, "../../../src/x.py")


def test_built_link_problems_map_the_built_page_back_to_its_source(docs: Path) -> None:
    module = _gates()

    (problem,) = module.parse("built-links", BUILT_LINKS_OUT, docs)

    assert (problem.gate, problem.source, problem.target) == ("built-links", ADR, "../../../src/x.py")


def test_an_unparseable_problem_line_is_kept_as_a_problem(docs: Path) -> None:
    """A ✖ line in a shape the wrapper does not know must not vanish."""
    problems = _gates().parse("check-links", "✖ something new happened\n", docs)

    assert len(problems) == 1


# --- the verdict -------------------------------------------------------------------------------


def test_listed_problems_from_immutable_sources_pass(tmp_path: Path, docs: Path) -> None:
    debt = _debt(tmp_path, _entry("check-links", ADR), _entry("built-links", ADR))

    for gate, output in (("check-links", CHECK_LINKS_OUT), ("built-links", BUILT_LINKS_OUT)):
        verdict = _verdict(gate, output, docs, debt)
        assert verdict.failures == [], verdict.failures


def test_an_unlisted_problem_fails(tmp_path: Path, docs: Path) -> None:
    verdict = _verdict("check-links", CHECK_LINKS_OUT, docs, _debt(tmp_path))

    assert len(verdict.failures) == 1
    assert ADR in verdict.failures[0]


@pytest.mark.parametrize(
    ("source", "text"),
    [
        pytest.param(GUIDE, None, id="editable-section"),
        pytest.param("plans/live-hub.md", "---\ntitle: t\ndoc_status: draft\nkind: Hub\n---\n", id="live-hub-under-plans"),
        pytest.param("plans/live-plan.md", "---\ntitle: t\ndoc_status: active\nkind: Planning\n---\n", id="active-plan"),
        pytest.param("plans/lower-hub.md", "---\ntitle: t\ndoc_status: superseded\nkind: hub\n---\n", id="hub-kind-any-case"),
        pytest.param("plans/no-frontmatter.md", "# no frontmatter\n", id="no-frontmatter"),
        pytest.param("plans/no-kind.md", "---\ntitle: t\ndoc_status: superseded\n---\n", id="no-kind"),
        pytest.param("plans/no-status.md", "---\ntitle: t\nkind: Planning\n---\n", id="no-doc-status"),
    ],
)
def test_a_listed_problem_from_an_editable_source_fails(tmp_path: Path, docs: Path, source: str, text: str | None) -> None:
    if text is not None:
        _write(docs, source, text)
    output = CHECK_LINKS_OUT.replace(ADR, source)
    debt = _debt(tmp_path, _entry("check-links", source))

    verdict = _verdict("check-links", output, docs, debt)

    assert any(source in failure and "not immutable" in failure for failure in verdict.failures), verdict.failures


def test_a_superseded_plan_stays_immutable_history(tmp_path: Path, docs: Path) -> None:
    source = "plans/old-plan.md"
    _write(docs, source, "---\ntitle: t\ndoc_status: superseded\nkind: Planning\n---\n")
    debt = _debt(tmp_path, _entry("check-links", source))

    verdict = _verdict("check-links", CHECK_LINKS_OUT.replace(ADR, source), docs, debt)

    assert verdict.failures == [], verdict.failures


def test_an_entry_listed_for_the_other_gate_does_not_cover_a_problem(tmp_path: Path, docs: Path) -> None:
    verdict = _verdict("check-links", CHECK_LINKS_OUT, docs, _debt(tmp_path, _entry("built-links", ADR)))

    assert len(verdict.failures) == 1


def test_a_stale_entry_is_reported_not_fatal(tmp_path: Path, docs: Path) -> None:
    debt = _debt(tmp_path, _entry("check-links", ADR), _entry("check-links", ADR, target="gone.md"))

    verdict = _verdict("check-links", CHECK_LINKS_OUT, docs, debt)

    assert verdict.failures == []
    assert len(verdict.stale) == 1 and "gone.md" in verdict.stale[0]


# --- the command -------------------------------------------------------------------------------


def _fake_gate(tmp_path: Path, output: str, code: int) -> list[str]:
    script = tmp_path / "fake_gate.py"
    script.write_text(f"import sys\nsys.stdout.write({output!r})\nsys.exit({code})\n", encoding="utf-8")
    return [sys.executable, str(script)]


def test_the_command_fails_on_an_unlisted_problem(tmp_path: Path, docs: Path) -> None:
    argv = ["check-links", "--docs", str(docs), "--debt", str(_debt(tmp_path)), "--", *_fake_gate(tmp_path, CHECK_LINKS_OUT, 1)]

    assert _gates().main(argv) == 1


def test_the_command_passes_when_every_problem_is_listed(tmp_path: Path, docs: Path) -> None:
    debt = _debt(tmp_path, _entry("check-links", ADR))
    argv = ["check-links", "--docs", str(docs), "--debt", str(debt), "--", *_fake_gate(tmp_path, CHECK_LINKS_OUT, 1)]

    assert _gates().main(argv) == 0


def test_a_failing_gate_with_no_parseable_problem_fails(tmp_path: Path, docs: Path) -> None:
    """A gate that exits non-zero for another reason (a bad flag, a crash) is never green."""
    argv = ["check-links", "--docs", str(docs), "--debt", str(_debt(tmp_path)), "--", *_fake_gate(tmp_path, "usage error\n", 2)]

    assert _gates().main(argv) == 1


# --- a failing gate is never hidden by listed problems (review cycle 1, finding 1) -------------


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(
            "\n[dk-routes] 1 route collision(s): /guides/x/ is served by guides/x.md and guides/x/index.md\n",
            id="route-collision",
        ),
        pytest.param("check-links: error something broke\n", id="forged-check-links-line"),
    ],
)
def test_an_unrecognised_line_beside_a_listed_problem_fails(tmp_path: Path, docs: Path, extra: str) -> None:
    """``dockitty-check-links`` can exit 1 on output with no ``✖`` (a ``[dk-routes]`` collision); only its two informational ``check-links:`` lines are accepted."""
    debt = _debt(tmp_path, _entry("check-links", ADR))
    argv = ["check-links", "--docs", str(docs), "--debt", str(debt), "--", *_fake_gate(tmp_path, CHECK_LINKS_OUT + extra, 1)]

    assert _gates().main(argv) == 1


def test_a_summary_count_the_parsed_problems_do_not_match_fails(tmp_path: Path, docs: Path) -> None:
    """The gate says two problems, the wrapper parsed one: the other is in a shape it cannot read."""
    output = CHECK_LINKS_OUT.replace("1 link problem(s)", "2 link problem(s)")
    debt = _debt(tmp_path, _entry("check-links", ADR))
    argv = ["check-links", "--docs", str(docs), "--debt", str(debt), "--", *_fake_gate(tmp_path, output, 1)]

    assert _gates().main(argv) == 1


def test_a_built_gate_failure_without_its_summary_fails(tmp_path: Path, docs: Path) -> None:
    output = BUILT_LINKS_OUT.replace("assert-no-broken-links: FAILED — 1 broken internal link(s) or external image(s):\n", "")
    debt = _debt(tmp_path, _entry("built-links", ADR))
    argv = ["built-links", "--docs", str(docs), "--debt", str(debt), "--", *_fake_gate(tmp_path, output, 1)]

    assert _gates().main(argv) == 1


def test_a_listed_built_problem_with_its_summary_passes(tmp_path: Path, docs: Path) -> None:
    debt = _debt(tmp_path, _entry("built-links", ADR))
    argv = ["built-links", "--docs", str(docs), "--debt", str(debt), "--", *_fake_gate(tmp_path, BUILT_LINKS_OUT, 1)]

    assert _gates().main(argv) == 0
