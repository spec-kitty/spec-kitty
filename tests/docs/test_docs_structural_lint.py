"""Regression + config-SSOT tests for the structural docs lint (FR-007/011).

The retired anti-sprawl ratchet checked index *existence* and an absolute
basename-uniqueness count. This lint replaces it with four independently
testable, config-driven checks. Per the WP02 contract
(``kitty-specs/docs-structural-sanity-01KY53KJ/contracts/docs-structural-lint.md``)
and the WP02 task prompt's explicit **timing boundary**:

* the 7 ``docs/architecture/audits/2026-05-*.md`` files and the 3
  ``docs/plans/notes/`` shadow basenames are LIVE ``point_in_time_placement``
  / ``shadow_tree_basename`` violations **by design** until WP03/WP04
  relocate/fold them — so this suite does **not** assert zero-TOTAL
  violations over the real, current ``docs/`` tree (that gate is WP05's,
  once the moves have landed). Instead it proves:

  (a) each of the 4 rule classes is caught 100% (a red-first regression
      fixture reintroducing one instance of each class);
  (b) a synthetic **post-move-shaped** fixture — mirroring the tree AFTER
      WP03/WP04 land — is zero-violation (the NFR-003 calibration proof);
  (c) discriminating **live cohort-clean** assertions on the cohorts that
      ARE already clean on the real tree today (``adr/**`` era-dated files,
      ``plans/{research,investigations}/**``, nav basenames, the 3
      frontmatter-less ADR READMEs);
  (d) the lint's runtime policy agrees with the styleguide's
      ``structural_lint_config:`` block (config-SSOT, C-005).
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from ruamel.yaml import YAML

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]


#: The structural lint ships as the ``common-docs-structural-lint`` doctrine
#: asset — its single canonical copy. FR-008 (proof by first user): this
#: repository's own consumer resolves it through the WP04 resolution surface
#: (``CharterOfferingService.assets``) by its stable identifier, instead of reaching
#: through a hard-coded ``_REPO_ROOT`` path. In the dev checkout this lands on
#: ``src/charter/offering/assets/built-in/…``; from a clean installation it lands on
#: packaged data — the same addressing the WP05 operator surface uses.
def _resolve_lint_asset_path() -> Path:
    """Resolve the shipped structural-lint asset via ``CharterOfferingService.assets``."""
    from charter.offering.service import CharterOfferingService

    return CharterOfferingService().assets.resolve_path("common-docs-structural-lint")


_LINT_ASSET_PATH = _resolve_lint_asset_path()

#: In THIS repo the styleguide carrying the ``structural_lint_config:`` block
#: is the maintainer-only internal-pack styleguide; the built-in common-docs
#: styleguide carries only a repository-agnostic default. The asset itself does
#: not hard-code this path — it is supplied explicitly (``--styleguide`` /
#: ``SPEC_KITTY_STYLEGUIDE``), which is what makes it consumable elsewhere.
STYLEGUIDE_PATH = _REPO_ROOT / "packs/internal/styleguides/spec-kitty-docs-lint-config.styleguide.yaml"


_LINT_ASSET_MODULE_NAME = "docs_structural_lint_asset"

#: Populated by the autouse ``_lint_module`` fixture below, once per module.
ConfigError: type[Any]
LintConfig: type[Any]
PointInTimeMarker: type[Any]
check_frontmatter_contract: Callable[..., Any]
check_index_completeness: Callable[..., Any]
check_point_in_time_placement: Callable[..., Any]
check_shadow_tree_basename: Callable[..., Any]
check_sanctioned_section_membership: Callable[..., Any]
check_one_index_per_dir: Callable[..., Any]
load_config: Callable[..., Any]
main: Callable[..., Any]
run: Callable[..., Any]
run_extended: Callable[..., Any]
_resolve_styleguide: Callable[..., Any]


@pytest.fixture(scope="module", autouse=True)
def _lint_module() -> Iterator[ModuleType]:
    """Load the structural-lint asset once for this module's tests.

    The module defines ``@dataclass(slots=True)`` types, and dataclasses
    resolves their string annotations via ``sys.modules[cls.__module__]`` —
    which must already be present before ``exec_module`` runs. A module-scoped
    ``pytest.MonkeyPatch.context()`` — not the function-scoped ``monkeypatch``
    fixture, which a module-scoped fixture cannot depend on — keeps that
    registration and undoes it once every test in this module has run.
    """
    global ConfigError, LintConfig, PointInTimeMarker
    global check_frontmatter_contract, check_index_completeness, check_point_in_time_placement
    global check_shadow_tree_basename, check_sanctioned_section_membership, check_one_index_per_dir
    global load_config, main, run, run_extended, _resolve_styleguide
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_LINT_ASSET_MODULE_NAME, _LINT_ASSET_PATH)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            raise RuntimeError(f"cannot load lint asset from {_LINT_ASSET_PATH}")
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _LINT_ASSET_MODULE_NAME, module)
        spec.loader.exec_module(module)
        ConfigError = module.ConfigError
        LintConfig = module.LintConfig
        PointInTimeMarker = module.PointInTimeMarker
        check_frontmatter_contract = module.check_frontmatter_contract
        check_index_completeness = module.check_index_completeness
        check_point_in_time_placement = module.check_point_in_time_placement
        check_shadow_tree_basename = module.check_shadow_tree_basename
        check_sanctioned_section_membership = module.check_sanctioned_section_membership
        check_one_index_per_dir = module.check_one_index_per_dir
        load_config = module.load_config
        main = module.main
        run = module.run
        run_extended = module.run_extended
        _resolve_styleguide = module._resolve_styleguide
        yield module


# --- Shared fixture helpers --------------------------------------------------


def _write(path: Path, *, frontmatter: dict[str, Any] | None = None, body: str = "# Body\n") -> None:
    """Write a docs page, optionally with a YAML frontmatter block."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if frontmatter is not None:
        lines.append("---")
        lines.extend(f"{key}: {json.dumps(value)}" for key, value in frontmatter.items())
        lines.append("---")
    lines.append(body)
    path.write_text("\n".join(lines), encoding="utf-8")


def _fixture_config() -> Any:
    """A deterministic config mirroring the real styleguide block's shape.

    Decoupled from the real, evolving styleguide (per WP02 task guidance)
    so the 4-class detection fixture stays stable regardless of future
    config edits — the config-SSOT agreement itself is proven separately
    against the real block below.
    """
    return LintConfig(
        curated_complete_sections=("architecture",),
        concern_bucket_to_section={
            "how_to": "development/",
            "point_in_time": "plans/engineering-notes/",
        },
        point_in_time_patterns=(r"^\d{4}-\d{2}",),
        point_in_time_markers=(
            PointInTimeMarker(frontmatter_field="doc_status", frontmatter_value="point_in_time"),
            PointInTimeMarker(frontmatter_field="doc_status", frontmatter_value="closeout"),
        ),
        point_in_time_allowlist=(
            "adr/**",
            "plans/research/**",
            "plans/investigations/**",
            "plans/**",
        ),
        frontmatter_required_fields=("doc_status", "updated"),
        frontmatter_in_scope_exclusions=("**/README.md",),
        shadow_tree_nav_exemptions=(
            "index.md",
            "README.md",
            "toc.yml",
            "README-*.x.md",
            "00-SYNTHESIS.md",
        ),
        redirect_stub_description_prefix="Redirect stub:",
        guides_boundary="docs/guides/ is not a relocation target under this mission.",
    )


_ACTIVE_FRONTMATTER = {"doc_status": "active", "updated": "2026-07-01"}


def _build_post_move_fixture(tmp_path: Path) -> Path:
    """A synthetic tree mirroring the shape AFTER WP03/WP04 land: zero-violation."""
    docs = tmp_path / "docs"

    # architecture/ — curated-complete; index.md enumerates every (sub-)page.
    _write(
        docs / "architecture" / "index.md",
        frontmatter=_ACTIVE_FRONTMATTER,
        body=("# Architecture\n\n- [Git workflow](git-workflow.md)\n- [Crime scene overview](assessments/code-as-a-crime-scene-overview.md)\n"),
    )
    _write(docs / "architecture" / "git-workflow.md", frontmatter=_ACTIVE_FRONTMATTER)
    _write(
        docs / "architecture" / "assessments" / "code-as-a-crime-scene-overview.md",
        frontmatter=_ACTIVE_FRONTMATTER,
    )

    # adr/ — era-dated, allowlisted; README.md landing pages carry no frontmatter.
    _write(
        docs / "adr" / "3.x" / "2026-01-01-example-decision.md",
        frontmatter=_ACTIVE_FRONTMATTER,
    )
    _write(docs / "adr" / "3.x" / "README.md", body="# 3.x ADRs\n")

    # plans/engineering-notes/architecture-audits/ — the audits' POST-MOVE home.
    _write(
        docs / "plans" / "engineering-notes" / "architecture-audits" / "2026-05-11-findings-vs-issues-update.md",
        frontmatter=_ACTIVE_FRONTMATTER,
    )

    # plans/research/ + plans/investigations/ — allowlisted STAY subtrees.
    _write(
        docs / "plans" / "research" / "2026-03-01-spike-notes.md",
        frontmatter=_ACTIVE_FRONTMATTER,
    )
    _write(
        docs / "plans" / "investigations" / "2026-02-01-incident-notes.md",
        frontmatter=_ACTIVE_FRONTMATTER,
    )

    return docs


# =============================================================================
# (a) Red-first regression fixture: one instance of each of the 4 classes.
# =============================================================================


def test_index_completeness_catches_missing_page(tmp_path: Path) -> None:
    """A curated-complete section's index.md omitting a sibling page is caught."""
    docs = tmp_path / "docs"
    _write(
        docs / "architecture" / "index.md",
        body="# Architecture\n\n- [Runtime loop](runtime-loop.md)\n",
    )
    _write(docs / "architecture" / "runtime-loop.md", frontmatter=_ACTIVE_FRONTMATTER)
    _write(docs / "architecture" / "git-workflow.md", frontmatter=_ACTIVE_FRONTMATTER)

    violations = check_index_completeness(docs, tmp_path, _fixture_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "index_completeness"
    assert violations[0].path == "docs/architecture/git-workflow.md"
    assert "architecture/index.md" in violations[0].message


def test_point_in_time_placement_catches_misplaced_file(tmp_path: Path) -> None:
    """A self-declared point-in-time file outside plans/** is caught.

    Named ``report-2026-05.md`` — it deliberately does NOT match the dated
    ``^\\d{4}-\\d{2}`` basename pattern (mirrors the real ``883-*`` dossiers,
    per the WP02 task note), proving the marker path independently of the
    pattern path.
    """
    docs = tmp_path / "docs"
    misplaced = docs / "development" / "report-2026-05.md"
    _write(misplaced, frontmatter={"doc_status": "point_in_time", "updated": "2026-05-01"})

    violations = check_point_in_time_placement([misplaced], docs, tmp_path, _fixture_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "point_in_time_placement"
    assert violations[0].path == "docs/development/report-2026-05.md"
    assert "plans/**" in violations[0].message


def test_point_in_time_placement_catches_dated_basename(tmp_path: Path) -> None:
    """A dated basename outside plans/** is caught via the pattern path."""
    docs = tmp_path / "docs"
    misplaced = docs / "guides" / "2026-05-11-onboarding-notes.md"
    _write(misplaced, frontmatter=_ACTIVE_FRONTMATTER)

    violations = check_point_in_time_placement([misplaced], docs, tmp_path, _fixture_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "point_in_time_placement"


def test_shadow_tree_basename_catches_cross_section_duplicate(tmp_path: Path) -> None:
    """The same non-nav basename under two section subtrees is caught."""
    docs = tmp_path / "docs"
    canonical = docs / "architecture" / "feature-detection.md"
    shadow = docs / "plans" / "notes" / "feature-detection.md"
    _write(canonical, frontmatter=_ACTIVE_FRONTMATTER)
    _write(shadow, frontmatter=_ACTIVE_FRONTMATTER)

    md_files = sorted(docs.rglob("*.md"))
    violations = check_shadow_tree_basename(md_files, docs, tmp_path, _fixture_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "shadow_tree_basename"
    assert "feature-detection.md" in violations[0].message
    assert "docs/architecture/feature-detection.md" in violations[0].message
    assert "docs/plans/notes/feature-detection.md" in violations[0].message


def test_shadow_tree_basename_exempts_redirect_stub(tmp_path: Path) -> None:
    """A redirect stub sharing the moved file's basename is NOT flagged (WP05 B).

    ``docs/retrospective-learning-loop.md`` is a legitimate old-path redirect
    stub for the canonical ``docs/architecture/retrospective-learning-loop.md``;
    its frontmatter ``description`` begins with the config-declared
    ``redirect_stub_description_prefix``. The cross-section basename it shares
    with its canonical twin must not trip shadow_tree_basename.
    """
    docs = tmp_path / "docs"
    canonical = docs / "architecture" / "retrospective-learning-loop.md"
    stub = docs / "retrospective-learning-loop.md"
    _write(canonical, frontmatter=_ACTIVE_FRONTMATTER)
    _write(
        stub,
        frontmatter={
            "doc_status": "active",
            "updated": "2026-04-29",
            "description": "Redirect stub: this page moved to architecture/...",
        },
    )

    md_files = sorted(docs.rglob("*.md"))
    violations = check_shadow_tree_basename(md_files, docs, tmp_path, _fixture_config())

    assert violations == []


def test_shadow_tree_basename_still_flags_non_stub_duplicate(tmp_path: Path) -> None:
    """The stub exemption is signal-driven: a non-stub duplicate still trips.

    Proves the exemption keys off the ``description`` prefix, not merely off
    the docs-root location — a same-basename twin whose description is NOT the
    redirect-stub prefix is still a genuine shadow.
    """
    docs = tmp_path / "docs"
    canonical = docs / "architecture" / "twin.md"
    not_a_stub = docs / "twin.md"
    _write(canonical, frontmatter=_ACTIVE_FRONTMATTER)
    _write(
        not_a_stub,
        frontmatter={**_ACTIVE_FRONTMATTER, "description": "A genuine second copy."},
    )

    md_files = sorted(docs.rglob("*.md"))
    violations = check_shadow_tree_basename(md_files, docs, tmp_path, _fixture_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "shadow_tree_basename"
    assert "twin.md" in violations[0].message


def test_frontmatter_contract_exempts_adr_bodies_via_config(tmp_path: Path) -> None:
    """DIRECTIVE_042 MADR exemption: adr/** bodies are out-of-scope (WP05 A).

    ADR bodies carry MADR ``status``/``date``, not ``doc_status``/``updated``;
    with ``adr/**`` in ``frontmatter_in_scope_exclusions`` the contract check
    skips them. The check reads the config (not a hard-coded ``adr/**``): the
    control below (exclusions WITHOUT ``adr/**``) proves it would otherwise flag.
    """
    docs = tmp_path / "docs"
    adr = docs / "adr" / "3.x" / "2026-07-01-some-decision.md"
    _write(adr, frontmatter={"status": "Accepted", "date": "2026-07-01"})

    without_adr = _fixture_config()
    assert without_adr.frontmatter_in_scope_exclusions == ("**/README.md",)
    flagged = check_frontmatter_contract([adr], docs, tmp_path, without_adr)
    # control: an unexcluded ADR is flagged (assert the rule, not just the count)
    assert [v.rule_id for v in flagged] == ["frontmatter_contract"]

    with_adr = dataclasses.replace(
        without_adr,
        frontmatter_in_scope_exclusions=("**/README.md", "adr/**"),
    )
    assert check_frontmatter_contract([adr], docs, tmp_path, with_adr) == []


# =============================================================================
# T004 invariants: nested non_content_dir matching + one_index exemptions.
# =============================================================================


def _t004_config() -> Any:
    """Config exercising the T004 structural invariants with a NESTED (two-segment)
    non-content dir entry — the WP04-reviewer bug fixture."""
    return dataclasses.replace(
        _fixture_config(),
        sanctioned_content_sections=("index", "architecture", "guides"),
        non_content_dirs=("assets/", "templates/spec-kitty/"),
        curated_complete_sections=("architecture",),
        one_index_per_dir=True,
    )


def test_sanctioned_section_membership_honours_nested_non_content_dir(tmp_path: Path) -> None:
    """A page under a TWO-SEGMENT ``non_content_dirs`` entry is exempt (bug fix).

    The prior top-level-only comparison mapped ``templates/spec-kitty/public/x.md``
    to the top segment ``templates`` — which is not in the list — so the whole
    nested scaffolding zone was wrongly flagged. Prefix matching honours it.
    """
    docs = tmp_path / "docs"
    nested = docs / "templates" / "spec-kitty" / "public" / "layout.md"
    _write(nested, frontmatter=_ACTIVE_FRONTMATTER)

    violations = check_sanctioned_section_membership([nested], docs, tmp_path, _t004_config())

    assert violations == [], f"a page under the nested non_content_dir templates/spec-kitty/ must be exempt, got: {[v.path for v in violations]}"


def test_sanctioned_section_membership_flags_unlisted_and_shallow_nested(tmp_path: Path) -> None:
    """Control: the nested exemption is scoped — it does not blanket the parent.

    ``templates/index.md`` (under ``templates/`` but NOT ``templates/spec-kitty/``)
    and an unsanctioned ``bogus/`` section are still flagged, proving the prefix
    match is exact and not a substring/top-level free pass.
    """
    docs = tmp_path / "docs"
    shallow = docs / "templates" / "index.md"  # not under templates/spec-kitty/
    bogus = docs / "bogus" / "page.md"  # unsanctioned section
    _write(shallow, frontmatter=_ACTIVE_FRONTMATTER)
    _write(bogus, frontmatter=_ACTIVE_FRONTMATTER)

    flagged = {v.path for v in check_sanctioned_section_membership([shallow, bogus], docs, tmp_path, _t004_config())}

    assert flagged == {"docs/templates/index.md", "docs/bogus/page.md"}


def test_one_index_per_dir_exempts_redirect_stub_and_curated_readme(tmp_path: Path) -> None:
    """``index.md`` + a redirect-stub README, or + a curated-section README, is clean.

    A normal (non-stub, non-curated) index+README pair is still flagged so the
    check keeps its teeth.
    """
    docs = tmp_path / "docs"
    config = _t004_config()

    # adr era dir: index.md + a redirect-stub README.md (FR-022) — exempt.
    _write(docs / "adr" / "1.x" / "index.md", frontmatter=_ACTIVE_FRONTMATTER)
    _write(
        docs / "adr" / "1.x" / "README.md",
        frontmatter={"description": "Redirect stub: moved to adr/1.x/index.md", **_ACTIVE_FRONTMATTER},
    )
    # curated-complete section: index.md + prose README.md — exempt.
    _write(docs / "architecture" / "index.md", frontmatter=_ACTIVE_FRONTMATTER)
    _write(docs / "architecture" / "README.md", frontmatter=_ACTIVE_FRONTMATTER)
    # ordinary dir: index.md + a plain README.md — STILL flagged (teeth).
    _write(docs / "guides" / "index.md", frontmatter=_ACTIVE_FRONTMATTER)
    _write(docs / "guides" / "README.md", frontmatter=_ACTIVE_FRONTMATTER)

    md_files = sorted(docs.rglob("*.md"))
    flagged = {v.path for v in check_one_index_per_dir(md_files, docs, tmp_path, config)}

    assert flagged == {"docs/guides/README.md"}, flagged


def test_frontmatter_contract_catches_missing_field(tmp_path: Path) -> None:
    """An in-scope page missing a required frontmatter field is caught."""
    docs = tmp_path / "docs"
    page = docs / "guides" / "onboarding.md"
    _write(page, frontmatter={"doc_status": "active"})  # missing 'updated'

    violations = check_frontmatter_contract([page], docs, tmp_path, _fixture_config())

    assert len(violations) == 1
    assert violations[0].rule_id == "frontmatter_contract"
    assert "updated" in violations[0].message


def test_frontmatter_contract_exempts_section_readme(tmp_path: Path) -> None:
    """A section README.md landing page is out-of-scope even with no frontmatter."""
    docs = tmp_path / "docs"
    readme = docs / "guides" / "README.md"
    _write(readme, body="# Guides\n")  # no frontmatter block at all

    violations = check_frontmatter_contract([readme], docs, tmp_path, _fixture_config())

    assert violations == []


# =============================================================================
# (b) Post-move-shaped fixture: zero-violation proof (NFR-003).
# =============================================================================


def test_post_move_shaped_fixture_is_zero_violation(tmp_path: Path) -> None:
    """A tree shaped like the post-WP03/WP04 tree reports zero violations."""
    docs = _build_post_move_fixture(tmp_path)

    report = run(docs_root=docs, repo_root=tmp_path, config=_fixture_config())

    assert report.violations == []
    assert report.checked > 0


def test_main_json_output_matches_contract_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--json`` emits ``{violations, checked}`` and exits 0 on a clean fixture."""
    docs = _build_post_move_fixture(tmp_path)

    exit_code = main(
        [
            str(docs),
            "--repo-root",
            str(tmp_path),
            "--styleguide",
            str(STYLEGUIDE_PATH),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["violations"] == []
    assert payload["checked"] > 0


# =============================================================================
# (c) Live cohort-clean assertions on the real docs/ tree (discriminating).
# =============================================================================
#
# NOTE: no assertion here demands zero-TOTAL over the real tree — the 7
# docs/architecture/audits/2026-05-*.md files and the 3 docs/plans/notes/
# shadow basenames are LIVE violations by design until WP03/WP04 land
# (WP05 runs the real post-move zero-violation gate). These assertions are
# narrowly scoped to the cohorts that ARE already clean today.


def test_live_adr_era_dated_files_do_not_trip_point_in_time() -> None:
    """The 132 era-dated adr/** files are allowlisted, not point-in-time violations."""
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"
    adr_files = [p for p in sorted(docs_root.rglob("*.md")) if p.relative_to(docs_root).as_posix().startswith("adr/")]
    assert len(adr_files) >= 100  # guards against a silently-empty cohort

    violations = check_point_in_time_placement(adr_files, docs_root, _REPO_ROOT, config)

    assert violations == []


def test_live_plans_research_and_investigations_pass_clean() -> None:
    """The plans/{research,investigations}/** STAY subtrees are allowlisted."""
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"
    cohort = [p for p in sorted(docs_root.rglob("*.md")) if p.relative_to(docs_root).as_posix().startswith(("plans/research/", "plans/investigations/"))]
    assert cohort  # guards against a silently-empty cohort

    violations = check_point_in_time_placement(cohort, docs_root, _REPO_ROOT, config)

    assert violations == []


def test_live_nav_basenames_do_not_trip_shadow_tree() -> None:
    """The index.md / README.md nav basenames never trip shadow_tree.

    Non-vacuity floors are keyed on index.md (the README->index standardization
    target) and the migration-invariant combined cohort, not a draining README
    floor. See research.md D2 for the original 38/38 baseline.
    """
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"
    md_files = sorted(docs_root.rglob("*.md"))
    index_count = sum(1 for p in md_files if p.name == "index.md")
    readme_count = sum(1 for p in md_files if p.name == "README.md")
    # These floors exist only for NON-VACUITY: the substantive guard below
    # (no shadow_tree violations) is meaningless unless the corpus actually
    # contains nav basenames to check. The original 38/38 split (research.md D2)
    # is being deliberately drained by the README.md -> index.md landing-file
    # standardization (#3324 standardized docs/plans), so index.md is now the
    # dominant, growing nav basename and a README-specific floor is the wrong
    # ratchet — it would trip on the very migration it is meant to allow.
    # Key the floor on index.md (the standardization target) and on the
    # migration-invariant combined cohort, both set below today's actuals
    # (index_count=57, combined=84 as of #3324).
    assert index_count >= 40, index_count
    assert index_count + readme_count >= 70, (index_count, readme_count)

    violations = check_shadow_tree_basename(md_files, docs_root, _REPO_ROOT, config)

    flagged_basenames = {Path(v.path).name for v in violations}
    assert "index.md" not in flagged_basenames
    assert "README.md" not in flagged_basenames


def test_live_adr_readmes_do_not_trip_frontmatter_contract() -> None:
    """The 3 frontmatter-less docs/adr/{1.x,2.x,3.x}/README.md are allowlisted (#2227)."""
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"
    adr_readmes = [docs_root / "adr" / era / "README.md" for era in ("1.x", "2.x", "3.x")]
    for readme in adr_readmes:
        assert readme.is_file()

    violations = check_frontmatter_contract(adr_readmes, docs_root, _REPO_ROOT, config)

    assert violations == []


def test_live_adr_bodies_do_not_trip_frontmatter_contract() -> None:
    """DIRECTIVE_042 (WP05 A): the era-dated adr/** MADR bodies are exempt.

    ADR bodies use MADR ``status``/``date`` (not ``doc_status``/``updated``);
    ``adr/**`` in ``frontmatter_in_scope_exclusions`` keeps the whole cohort —
    not just the README landing pages — out of scope on the live tree.
    """
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"
    adr_bodies = [p for p in sorted((docs_root / "adr").rglob("*.md")) if p.name != "README.md"]
    assert len(adr_bodies) >= 100  # guards against a silently-empty cohort

    violations = check_frontmatter_contract(adr_bodies, docs_root, _REPO_ROOT, config)

    assert violations == []


def test_live_redirect_stub_not_flagged_as_shadow_basename() -> None:
    """WP05 B: the docs-root retrospective-learning-loop redirect stub is exempt.

    ``docs/retrospective-learning-loop.md`` (a redirect stub) and its canonical
    twin ``docs/architecture/retrospective-learning-loop.md`` share a basename
    across sections by design; the config-declared redirect-stub signal keeps
    the pair off shadow_tree_basename on the live tree.
    """
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"
    stub = docs_root / "retrospective-learning-loop.md"
    assert stub.is_file()  # guards against the stub being deleted

    md_files = sorted(docs_root.rglob("*.md"))
    violations = check_shadow_tree_basename(md_files, docs_root, _REPO_ROOT, config)

    flagged = {v.path for v in violations}
    assert "docs/retrospective-learning-loop.md" not in flagged
    assert "docs/architecture/retrospective-learning-loop.md" not in flagged


def test_live_real_tree_is_zero_violation_post_move() -> None:
    """WP05 DoD: the LIVE post-move tree reports zero structural violations.

    This is the gate WP02 deferred to WP05: once WP03/WP04 have landed the
    moves/folds and WP05 has reconciled the config exemptions (ADR MADR
    frontmatter, redirect stub) + backfilled the one real gap, the full lint
    over the real ``docs/`` tree is clean.
    """
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"

    report = run(docs_root=docs_root, repo_root=_REPO_ROOT, config=config)

    assert report.violations == [], "\n".join(f"{v.rule_id} {v.path}: {v.message}" for v in report.violations)
    assert report.checked > 0


def test_live_real_tree_is_zero_violation_under_extended_run() -> None:
    """The terminal-verification runner (``run_extended``) is also clean.

    ``run()`` (the standing per-PR gate) does not wire in
    ``check_sanctioned_section_membership`` / ``check_one_index_per_dir`` — so
    a new top-level ``docs/`` section can be invisible to every PR gate while
    still breaking terminal verification (planning#583, first tripped by
    ``docs/convergence/``). This asserts the extended runner independently.

    NOTE: ``docs/convergence/`` has zero files on this tree as of writing
    (PR #548/issue #401, which lands the first page under it, is still
    open) — so on its own this assertion cannot fail on a regression to the
    ``convergence`` config entry; it is only real teeth against every OTHER
    sanctioned section. See
    ``test_sanctioned_section_membership_covers_convergence_via_real_config``
    below for a fixture-backed proof that exercises this fix specifically,
    independent of whether #548 has merged.
    """
    config = load_config(STYLEGUIDE_PATH)
    docs_root = _REPO_ROOT / "docs"

    report = run_extended(docs_root=docs_root, repo_root=_REPO_ROOT, config=config)

    assert report.violations == [], "\n".join(f"{v.rule_id} {v.path}: {v.message}" for v in report.violations)


def test_sanctioned_section_membership_covers_convergence_via_real_config(
    tmp_path: Path,
) -> None:
    """planning#583 fix, exercised NOW — not gated on #548/#401 landing content.

    ``docs/convergence/`` has no files on this tree yet, so
    ``test_live_real_tree_is_zero_violation_under_extended_run`` cannot exercise
    ``check_sanctioned_section_membership`` against a real ``convergence`` page
    (squad finding on PR #622: that test is a no-op guard today). This builds an
    independent ``docs/convergence/*.md`` fixture and runs it through the
    REAL shipped styleguide config, reproducing the issue's own 0/1 measurement
    on THIS tree: 0 violations with ``convergence`` sanctioned (the shipped
    state), 1 if it is removed (the pre-fix state).
    """
    config = load_config(STYLEGUIDE_PATH)
    assert "convergence" in config.sanctioned_content_sections

    docs = tmp_path / "docs"
    page = docs / "convergence" / "mission-runtime.md"
    _write(page, frontmatter=_ACTIVE_FRONTMATTER)
    md_files = [page]

    after = check_sanctioned_section_membership(md_files, docs, tmp_path, config)
    assert after == [], f"docs/convergence/ must be sanctioned per the shipped styleguide config, got: {[(v.rule_id, v.path) for v in after]}"

    pre_fix_config = dataclasses.replace(
        config,
        sanctioned_content_sections=tuple(section for section in config.sanctioned_content_sections if section != "convergence"),
    )
    before = check_sanctioned_section_membership(md_files, docs, tmp_path, pre_fix_config)
    assert [v.rule_id for v in before] == ["sanctioned_section_membership"], (
        f"control: without convergence in sanctioned_content_sections the same page must be flagged (the issue's pre-fix 0->1), got: {before}"
    )


# =============================================================================
# (d) Config-SSOT: the lint's runtime policy agrees with the styleguide block.
# =============================================================================


def test_load_config_matches_styleguide_block() -> None:
    """``load_config()`` returns exactly the values in the styleguide's block."""
    yaml = YAML(typ="safe")
    with STYLEGUIDE_PATH.open("r", encoding="utf-8") as handle:
        raw = yaml.load(handle)
    block = raw["structural_lint_config"]

    config = load_config(STYLEGUIDE_PATH)

    assert config.curated_complete_sections == tuple(block["curated_complete_sections"])
    assert config.point_in_time_patterns == tuple(block["point_in_time_patterns"])
    assert config.point_in_time_allowlist == tuple(block["point_in_time_allowlist"])
    assert config.frontmatter_required_fields == tuple(block["frontmatter_required_fields"])
    assert config.frontmatter_in_scope_exclusions == tuple(block["frontmatter_in_scope_exclusions"])
    assert config.shadow_tree_nav_exemptions == tuple(block["shadow_tree_nav_exemptions"])
    assert config.redirect_stub_description_prefix == block["redirect_stub_description_prefix"]
    assert config.concern_bucket_to_section == dict(block["concern_bucket_to_section"])
    assert [(marker.frontmatter_field, marker.frontmatter_value) for marker in config.point_in_time_markers] == [
        (m["frontmatter_field"], m["frontmatter_value"]) for m in block["point_in_time_markers"]
    ]


def test_load_config_fails_loud_on_missing_block(tmp_path: Path) -> None:
    """A styleguide with no structural_lint_config: block is a hard error."""
    stub = tmp_path / "stub.styleguide.yaml"
    stub.write_text("id: stub\ntitle: Stub\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="structural_lint_config"):
        load_config(styleguide_path=stub)


def test_config_error_messages_carry_no_mission_labels(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The lint ships to consumers: its operator-facing errors must not cite mission FR labels."""
    monkeypatch.delenv("SPEC_KITTY_STYLEGUIDE", raising=False)
    with pytest.raises(ConfigError) as unconfigured:
        _resolve_styleguide(None)
    with pytest.raises(ConfigError) as missing:
        load_config(styleguide_path=tmp_path / "absent.yaml")

    for exc in (unconfigured, missing):
        assert "FR-" not in str(exc.value), str(exc.value)


def test_load_config_rejects_malformed_block(tmp_path: Path) -> None:
    """A structural_lint_config: block missing a required key is a hard error."""
    stub = tmp_path / "stub.styleguide.yaml"
    stub.write_text(
        "id: stub\ntitle: Stub\nstructural_lint_config:\n  curated_complete_sections: []\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="point_in_time_patterns"):
        load_config(styleguide_path=stub)


def test_load_config_resolves_absolute_path_regardless_of_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An absolute styleguide path resolves the same regardless of the CWD."""
    subdir = tmp_path / "somewhere" / "else"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)

    config = load_config(STYLEGUIDE_PATH)

    assert "architecture" in config.curated_complete_sections


def test_resolve_styleguide_prefers_cli_arg(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--styleguide`` wins over the environment variable."""
    monkeypatch.setenv("SPEC_KITTY_STYLEGUIDE", "/from/env.yaml")

    assert _resolve_styleguide("/from/arg.yaml") == Path("/from/arg.yaml")


def test_resolve_styleguide_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no CLI arg, the ``SPEC_KITTY_STYLEGUIDE`` env var is used."""
    monkeypatch.setenv("SPEC_KITTY_STYLEGUIDE", "/from/env.yaml")

    assert _resolve_styleguide(None) == Path("/from/env.yaml")


def test_resolve_styleguide_errors_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No CLI arg and no env var is a hard, loud ConfigError naming both knobs."""
    monkeypatch.delenv("SPEC_KITTY_STYLEGUIDE", raising=False)

    with pytest.raises(ConfigError, match="--styleguide"):
        _resolve_styleguide(None)


def test_main_exits_2_when_styleguide_unconfigured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``main`` returns exit code 2 when no styleguide can be resolved."""
    monkeypatch.delenv("SPEC_KITTY_STYLEGUIDE", raising=False)
    docs = _build_post_move_fixture(tmp_path)

    exit_code = main([str(docs), "--repo-root", str(tmp_path)])

    assert exit_code == 2
    assert "--styleguide" in capsys.readouterr().err


def test_index_completeness_reads_config_not_a_constant(tmp_path: Path) -> None:
    """Mutating curated_complete_sections changes behaviour — proves config-reading.

    If ``check_index_completeness`` hard-coded ``"architecture"`` instead of
    reading ``config.curated_complete_sections``, this would fail to detect
    the newly-added ``guides`` section's incomplete index.
    """
    docs = tmp_path / "docs"
    _write(docs / "guides" / "index.md", body="# Guides\n")
    _write(docs / "guides" / "onboarding.md", frontmatter=_ACTIVE_FRONTMATTER)

    base_config = _fixture_config()
    assert check_index_completeness(docs, tmp_path, base_config) == []

    mutated_config = dataclasses.replace(
        base_config,
        curated_complete_sections=(*base_config.curated_complete_sections, "guides"),
    )
    violations = check_index_completeness(docs, tmp_path, mutated_config)

    assert len(violations) == 1
    assert violations[0].rule_id == "index_completeness"
    assert violations[0].path == "docs/guides/onboarding.md"


def test_schema_properties_match_lintconfig_fields() -> None:
    """The styleguide schema's ``structural_lint_config`` properties must match
    the lint's :class:`LintConfig` dataclass fields exactly.

    Regression guard: ``redirect_stub_description_prefix`` was added to the
    styleguide config block and the lint loader but not to the schema, whose
    ``additionalProperties: false`` then reddened ``test_artifact_compliance``.
    The config shape lives in three places (schema, dataclass, YAML data); this
    keeps schema↔dataclass from silently drifting when a future exemption key is
    added.
    """
    yaml = YAML(typ="safe")
    schema_path = _REPO_ROOT / "src/charter/offering/schemas/styleguide.schema.yaml"
    with schema_path.open(encoding="utf-8") as handle:
        schema = yaml.load(handle)
    props = set(schema["definitions"]["structural_lint_config"]["properties"])
    fields = {field.name for field in dataclasses.fields(LintConfig)}
    assert props == fields, f"schema/LintConfig drift — only-in-schema={props - fields}, only-in-dataclass={fields - props}"


def test_shipped_lint_asset_resolved_via_doctrine_service() -> None:
    """FR-008 — the shipped-asset consumer resolves via the resolution surface.

    WP05's proof-by-first-user: this repository's own consumer of the shipped
    ``common-docs-structural-lint`` asset must resolve it through
    :class:`charter.offering.service.CharterOfferingService` ``.assets`` (the WP04 resolver),
    not by reaching through a hard-coded ``_REPO_ROOT`` path. Guards against
    reintroducing the retired reach-through so the fix cannot silently regress.
    """
    from charter.offering.service import CharterOfferingService

    source = Path(__file__).read_text(encoding="utf-8")
    # Built by concatenation so this guard does not match its own source text.
    forbidden = "src/charter/offering/assets/" + "built-in/docs_structural_lint.py"
    assert forbidden not in source, (
        "structural-lint test must not hard-code the shipped asset's repo path; resolve it by id through CharterOfferingService.assets.resolve_path (FR-008)."
    )

    resolved = CharterOfferingService().assets.resolve_path("common-docs-structural-lint")
    assert resolved == _LINT_ASSET_PATH, "the lint asset consumed by this suite must be the one the resolver returns for 'common-docs-structural-lint' (FR-008)."
    assert _LINT_ASSET_PATH.is_file()
