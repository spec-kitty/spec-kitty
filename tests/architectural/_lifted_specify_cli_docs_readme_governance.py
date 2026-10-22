"""Single home of the README Governance-layer section checks (#5015).

Both ``tests/specify_cli/docs/test_readme_governance.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_specify_cli_docs_readme_governance.py`` import these tests, so the per-PR gate
runs exactly what the source suite runs and the two cannot drift apart.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"


def test_readme_has_governance_layer_section() -> None:
    content = README.read_text()
    assert "## Governance layer" in content, "README.md must contain a '## Governance layer' subsection (WP03 / FR-005)."


def _governance_section() -> str:
    content = README.read_text()
    gov_idx = content.index("## Governance layer")
    # Next top-level section or EOF
    next_h2 = content.find("\n## ", gov_idx + 1)
    return content[gov_idx : next_h2 if next_h2 != -1 else len(content)]


def test_governance_section_links_to_trail_model() -> None:
    # The Common Docs convergence (54108a7c9) moved the trail model under
    # docs/architecture/; assert the README links the canonical path AND that it
    # resolves, so a future move can't silently re-break this the same way.
    section = _governance_section()
    rel = "docs/architecture/trail-model.md"
    assert rel in section, f"Governance layer subsection must link to {rel}."
    assert (REPO_ROOT / rel).is_file(), f"{rel} linked from README must exist."


def test_governance_section_links_to_host_surface_parity() -> None:
    section = _governance_section()
    rel = "docs/architecture/host-surface-parity.md"
    assert rel in section, f"Governance layer subsection must link to {rel}."
    assert (REPO_ROOT / rel).is_file(), f"{rel} linked from README must exist."


def test_governance_section_mentions_dispatch_only() -> None:
    content = README.read_text()
    gov_idx = content.index("## Governance layer")
    next_h2 = content.find("\n## ", gov_idx + 1)
    section = content[gov_idx : next_h2 if next_h2 != -1 else len(content)]
    assert 'spec-kitty dispatch "<request>"' in section
    for removed in ("advise", "ask", "do"):
        assert f"spec-kitty {removed}" not in section


def test_runtime_next_skill_references_resolve() -> None:
    skill = REPO_ROOT / "src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md"
    content = skill.read_text()
    links = re.findall(r"\]\(([^)#]+\.md)\)", content)
    for link in links:
        if link.startswith("/") or link.startswith("http"):
            continue
        target = (skill.parent / link).resolve()
        assert target.exists(), f"Broken link in runtime-next/SKILL.md: {link}"


def test_runtime_next_skill_documents_omitted_result_as_query_mode() -> None:
    skill = REPO_ROOT / "src/charter/offering/skills/spec-kitty-runtime-next/SKILL.md"
    content = skill.read_text()

    assert "Defaults to `success` if omitted." not in content
    assert ("If omitted, `spec-kitty next` returns current state without advancing (query mode).") in content
