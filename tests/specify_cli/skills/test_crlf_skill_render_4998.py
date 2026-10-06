"""Regression tests for #4998: CRLF frontmatter doubling.

On a source checkout with CRLF line endings, doctrine-skill install
prepended a second, bogus YAML frontmatter block ahead of the real one in
every installed ``SKILL.md`` (``doctor`` then reported ~275 drifts and
``upgrade``/``--fix`` could not repair them). Root cause: two frontmatter
regexes in ``skills/command_renderer.py`` (``_RE_FRONTMATTER`` /
``_RE_LEADING_FRONTMATTER``) match ``\\n`` only, so CRLF-terminated
frontmatter was never recognised as present.

Fix: :func:`kernel.text_decode.normalize_newlines` normalises decoded text to
LF right after decoding, both in ``ensure_skill_frontmatter`` (the
doctrine-skill install / verify / repair paths) and in the command-skill
``render()`` path.

Contracts pinned here:

* Doctrine skills installed from CRLF sources are byte-identical to
  LF-source installs, with exactly one frontmatter block.
* Command skills rendered from CRLF command templates are byte-identical to
  LF-template renders. The fixture is ``software-dev/accept/prompt.md`` --
  deliberately marker-FREE (no ``<!-- spdd:reasons-block:start -->``): a
  marker-carrying template already runs its raw text through
  ``apply_spdd_blocks_for_project``/``process_spdd_blocks``, which normalises
  CRLF to LF on its own, so the comparison would pass even without the
  ``render()`` normalisation. A guard assertion pins the fixture choice.
* An install corrupted by the pre-fix behaviour, whose files still match the
  manifest-recorded (corrupted) hash, is restored by every repair path:
  ``spec-kitty upgrade`` (via ``upgrade.assessment.prepare_upgrade_repairs``
  / ``apply_upgrade_repairs`` on every invocation, including the "already up
  to date" path), ``doctor tool-surfaces --kind doctrine-skill --fix``,
  ``install_all_skills`` (the one-shot skill-pack migration path), and, for
  command skills, ``doctor tool-surfaces --kind command-skill --fix``.
  ``doctor skills --fix`` does NOT yet converge a self-consistent command
  skill drift (strict ``xfail``, #5281): ``command_installer.verify()`` only
  compares the on-disk hash to the manifest-recorded one.
* A corrupted file the user edited *since* install (on-disk hash !=
  manifest hash) is classified ``consent_required`` and surfaces as
  ``skipped`` (never ``repaired``) -- never silently overwritten.
* ``.gitattributes`` pins both source trees to ``eol=lf``; the cross-cutting
  parser guard lives in
  ``tests/architectural/test_merge_reconciliation_class_guard.py``.
"""

from __future__ import annotations

import contextlib
import json
import re
import stat
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kernel.clock import now_utc_iso
from specify_cli import app as root_app
from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.core.config import SKILL_CLASS_SHARED
from specify_cli.core.paths import locate_project_root
from specify_cli.skills import manifest_store
from specify_cli.skills.command_renderer import render
from specify_cli.skills.installer import install_all_skills
from specify_cli.skills.manifest import (
    ManagedFileEntry,
    ManagedSkillManifest,
    compute_content_hash,
    load_manifest,
    save_manifest,
)
from specify_cli.skills.paths import get_primary_project_skill_root
from specify_cli.skills.registry import SkillRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / "pyproject.toml").exists():
    _REPO_ROOT = _REPO_ROOT.parent

_DOCTRINE_SKILLS_ROOT = _REPO_ROOT / "src" / "charter" / "offering" / "skills"
_MISSION_STEPS_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"

#: Command-template fixture: deliberately marker-free (see module docstring)
#: so the comparison exercises ``render()``'s normalisation, not SPDD's own.
_COMMAND_TEMPLATE = _MISSION_STEPS_ROOT / "accept" / "prompt.md"
_SPDD_REASONS_MARKER = "<!-- spdd:reasons-block:start -->"

#: A frontmatter delimiter line, CRLF- or LF-terminated.
_RE_LEADING_FRONTMATTER_BLOCK = re.compile(rb"^---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)
#: str-mode sibling of the above, for the fixture builder (which works on
#: decoded text, not bytes) to locate the CLOSING frontmatter delimiter.
_RE_LEADING_FRONTMATTER_BLOCK_TEXT = re.compile(r"^---\r?\n.*?\r?\n---\r?\n?", re.DOTALL)

# --------------------------------------------------------------------------
# Shared fixtures / helpers
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate HOME/XDG -- doctrine-skill install also writes a GLOBAL copy."""
    home = tmp_path / "home"
    home.mkdir()
    for key in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(key, str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / ".cache"))
    return home


def _assert_scoped_to_tmp_path(project: Path, tmp_path: Path, home: Path) -> None:
    """EXTRA SAFETY RULE: every resolved root this test touches must live
    under ``tmp_path`` -- never the real checkout at ``_REPO_ROOT``.
    """
    assert home.is_relative_to(tmp_path)
    assert project.is_relative_to(tmp_path)
    with contextlib.chdir(project):
        resolved = locate_project_root()
    assert resolved is not None
    assert resolved.resolve().is_relative_to(tmp_path.resolve()), f"locate_project_root() escaped the scratch project: {resolved} not under {tmp_path}"


def _all_doctrine_skill_names() -> list[str]:
    return sorted(p.name for p in _DOCTRINE_SKILLS_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").exists())


def _sample_skill_names(count: int = 3) -> list[str]:
    names = _all_doctrine_skill_names()
    assert len(names) >= count, "doctrine skills catalog shrank below the fixture's sample size"
    return names[:count]


def _copy_skill_tree(src_root: Path, dest_root: Path, names: list[str], *, crlf: bool) -> None:
    """Copy the named skills from *src_root* into *dest_root*.

    ``crlf=True`` rewrites every ``\\n`` to ``\\r\\n``; the last of *names*
    additionally gets a mid-file lone-``\\r`` line injected (mixed-line-ending
    variant) between its frontmatter and body, covering the "lone CR" half
    of :func:`kernel.text_decode.normalize_newlines`.
    """
    for index, name in enumerate(names):
        src_dir = src_root / name
        dest_dir = dest_root / name
        for source_file in src_dir.rglob("*"):
            if not source_file.is_file():
                continue
            rel = source_file.relative_to(src_dir)
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            text = source_file.read_text(encoding="utf-8")
            if crlf:
                text = text.replace("\n", "\r\n")
                if index == len(names) - 1 and rel.name == "SKILL.md":
                    # Inject one lone-CR line-ending (mixed variant) right
                    # after the frontmatter's CLOSING delimiter, in the body
                    # (matching this function's own docstring). A plain
                    # `.replace("---\r\n", ..., 1)` hits the FIRST "---\r\n"
                    # in the file, which is the OPENING delimiter (landing
                    # the marker inside the frontmatter, between "---" and
                    # "name:"). Matching the
                    # whole leading frontmatter block first and inserting
                    # right after it lands the marker in the body instead.
                    text = _RE_LEADING_FRONTMATTER_BLOCK_TEXT.sub(lambda m: m.group(0) + "<!-- lone-cr -->\r", text, count=1)
            target.write_bytes(text.encode("utf-8"))


def _crlf_registry(tmp_path: Path, names: list[str]) -> SkillRegistry:
    dest_root = tmp_path / "crlf_doctrine_skills"
    _copy_skill_tree(_DOCTRINE_SKILLS_ROOT, dest_root, names, crlf=True)
    return SkillRegistry(dest_root)


def _lf_registry(tmp_path: Path, names: list[str]) -> SkillRegistry:
    dest_root = tmp_path / "lf_doctrine_skills"
    _copy_skill_tree(_DOCTRINE_SKILLS_ROOT, dest_root, names, crlf=False)
    return SkillRegistry(dest_root)


def _single_frontmatter_block(content: bytes) -> bool:
    """True iff *content* has exactly one frontmatter block at its start.

    Restricted to the LEADING block region only: matches
    the first ``---``-delimited block (CRLF- or LF-terminated), then checks
    that what immediately follows is NOT itself another frontmatter block.
    A stray ``---`` horizontal rule elsewhere in the body prose never
    causes a false negative, unlike a whole-file marker count.
    """
    match = _RE_LEADING_FRONTMATTER_BLOCK.match(content)
    if match is None:
        return False
    rest = content[match.end() :]
    return _RE_LEADING_FRONTMATTER_BLOCK.match(rest) is None


def _make_project(tmp_path: Path, *, agents: list[str], suffix: str = "") -> Path:
    project = tmp_path / f"project{suffix}"
    project.mkdir()
    kittify = project / ".kittify"
    kittify.mkdir()
    agent_lines = "\n".join(f"    - {agent}" for agent in agents)
    (kittify / "config.yaml").write_text(
        f"vcs:\n  type: git\nagents:\n  available:\n{agent_lines}\n",
        encoding="utf-8",
    )
    return project


# --------------------------------------------------------------------------
# Doctrine-skill install parity (CRLF source == LF source, single
# frontmatter block). Uses install_all_skills() -- the installer function
# the CLI's upgrade/repair paths call.
# --------------------------------------------------------------------------


def test_crlf_doctrine_skill_install_matches_lf_source(tmp_path: Path) -> None:
    names = _sample_skill_names(3)

    lf_project = _make_project(tmp_path, agents=["claude"], suffix="_lf")
    crlf_project = _make_project(tmp_path, agents=["claude"], suffix="_crlf")
    _assert_scoped_to_tmp_path(lf_project, tmp_path, Path.home())
    _assert_scoped_to_tmp_path(crlf_project, tmp_path, Path.home())

    lf_registry = _lf_registry(tmp_path, names)
    crlf_registry = _crlf_registry(tmp_path, names)

    install_all_skills(lf_project, ["claude"], lf_registry)
    install_all_skills(crlf_project, ["claude"], crlf_registry)

    # The last sampled name carries the injected mixed-line-ending (lone-CR)
    # variant (see ``_copy_skill_tree``): its CRLF install legitimately
    # differs in *content* (one extra marker line) from the untouched LF
    # source, so it is checked for correct normalisation separately rather
    # than for exact byte-identity with the (marker-free) LF install.
    mixed_variant_name = names[-1]

    for name in names:
        lf_skill_md = lf_project / ".claude" / "skills" / name / "SKILL.md"
        crlf_skill_md = crlf_project / ".claude" / "skills" / name / "SKILL.md"
        assert lf_skill_md.is_file(), f"missing LF install for {name}"
        assert crlf_skill_md.is_file(), f"missing CRLF install for {name}"

        lf_content = lf_skill_md.read_bytes()
        crlf_content = crlf_skill_md.read_bytes()

        assert _single_frontmatter_block(lf_content), f"{name}: LF install has a doubled/missing frontmatter block"
        assert _single_frontmatter_block(crlf_content), (
            f"{name}: CRLF install has a doubled frontmatter block (the #4998 symptom) -- first 200 bytes: {crlf_content[:200]!r}"
        )
        if name == mixed_variant_name:
            assert b"\r" not in crlf_content, f"{name}: lone-CR/CRLF line ending survived normalisation"
            assert b"<!-- lone-cr -->" in crlf_content, f"{name}: mixed-variant marker line went missing"
            continue
        assert crlf_content == lf_content, (
            f"{name}: CRLF-source install is not byte-identical to the LF-source install\nLF:   {lf_content[:200]!r}\nCRLF: {crlf_content[:200]!r}"
        )


def test_crlf_doctrine_skill_install_via_real_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Same install-parity guarantee, driven through the real
    ``spec-kitty doctor tool-surfaces --kind doctrine-skill --fix`` CLI
    entry point, not only the installer function.
    """
    names = _sample_skill_names(2)
    project = _make_project(tmp_path, agents=["codex"])
    home = Path.home()
    _assert_scoped_to_tmp_path(project, tmp_path, home)

    crlf_registry = _crlf_registry(tmp_path, names)
    monkeypatch.setattr(SkillRegistry, "from_package", classmethod(lambda cls: crlf_registry))

    with contextlib.chdir(project):
        result = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "doctrine-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True, payload

    # The last sampled name carries the injected mixed-line-ending (lone-CR)
    # variant (see ``_copy_skill_tree``): it legitimately differs in content
    # from the untouched LF package source (one extra marker line), so it is
    # checked for correct normalisation instead of byte-equality below.
    mixed_variant_name = names[-1]

    for name in names:
        installed = project / ".agents" / "skills" / name / "SKILL.md"
        assert installed.is_file(), f"missing CLI-driven install for {name}"
        content = installed.read_bytes()
        assert _single_frontmatter_block(content), f"{name}: real-CLI CRLF install has a doubled frontmatter block -- first 200 bytes: {content[:200]!r}"
        if name == mixed_variant_name:
            assert b"\r" not in content, f"{name}: lone-CR/CRLF line ending survived normalisation"
            assert b"<!-- lone-cr -->" in content, f"{name}: mixed-variant marker line went missing"
            continue
        # Byte-equality against the real LF package source:
        # `_single_frontmatter_block` alone has one known blind
        # spot (a doubled block separated by a blank line), so relying on it
        # in isolation is not conclusive proof of a correct repair.
        lf_source_bytes = (_DOCTRINE_SKILLS_ROOT / name / "SKILL.md").read_bytes()
        assert content == lf_source_bytes, (
            f"{name}: real-CLI CRLF install is not byte-equal to the LF package source\ngot:      {content[:200]!r}\nexpected: {lf_source_bytes[:200]!r}"
        )

    # A second --fix run over an already-correct install is a clean no-op.
    with contextlib.chdir(project):
        result2 = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "doctrine-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    assert result2.exit_code == 0, result2.output
    payload2 = json.loads(result2.output)
    assert payload2["findings"] == [], payload2


# --------------------------------------------------------------------------
# Command-skill render parity (CRLF template == LF template).
# --------------------------------------------------------------------------


def test_crlf_command_template_render_matches_lf_source(tmp_path: Path) -> None:
    assert _COMMAND_TEMPLATE.is_file(), f"fixture command template missing: {_COMMAND_TEMPLATE}"
    lf_text = _COMMAND_TEMPLATE.read_text(encoding="utf-8")
    assert "\r" not in lf_text, "fixture template must be a genuine LF source for this comparison to be meaningful"
    # Guard: a marker-carrying template already gets CRLF normalised by
    # apply_spdd_blocks_for_project/process_spdd_blocks before render()'s own
    # normalisation runs, which would make this comparison pass even without
    # it and prove nothing. Pin the fixture choice so a
    # later edit that adds SPDD markers to this template cannot silently
    # make the test vacuous again.
    assert _SPDD_REASONS_MARKER not in lf_text, (
        f"{_COMMAND_TEMPLATE.name} gained SPDD reasons-block markers -- switch the command-template "
        "fixture to a different marker-free software-dev step, or the CRLF/LF comparison "
        "below is vacuous (SPDD's own normalisation would mask render()'s)"
    )

    # The skill name/command is derived from the parent directory name for a
    # ``prompt.md`` file (``command_renderer.render``'s "New doctrine layout"
    # branch), so the CRLF fixture must keep the SAME parent dir name
    # (``accept``) as the real template for the two renders to be
    # comparable on anything but line endings.
    crlf_path = tmp_path / _COMMAND_TEMPLATE.parent.name / _COMMAND_TEMPLATE.name
    crlf_path.parent.mkdir(parents=True, exist_ok=True)
    crlf_path.write_bytes(lf_text.replace("\n", "\r\n").encode("utf-8"))

    lf_rendered = render(_COMMAND_TEMPLATE, "codex", "test-version", repo_root=None)
    crlf_rendered = render(crlf_path, "codex", "test-version", repo_root=None)

    assert "\r" not in crlf_rendered.body, "CRLF survived into the rendered body"
    assert crlf_rendered.body == lf_rendered.body, "CRLF-template body diverges from the LF-template render"
    assert crlf_rendered.frontmatter == lf_rendered.frontmatter, "CRLF-template frontmatter diverges from the LF-template render"
    assert crlf_rendered.frontmatter["description"] == lf_rendered.frontmatter["description"], (
        "CRLF-template description extraction diverges from the LF-template render "
        f"(crlf={crlf_rendered.frontmatter['description']!r}, lf={lf_rendered.frontmatter['description']!r})"
    )
    # source_hash is computed on the *normalised* bytes:
    # hashing normalised bytes makes CRLF/LF renders indistinguishable and
    # keeps existing LF hashes unchanged (normalising LF input is a no-op).
    # Kept as a SECONDARY assertion -- body/frontmatter above are the ones
    # that must not be vacuously true on base code.
    assert crlf_rendered.source_hash == lf_rendered.source_hash, (
        "source_hash must be computed on normalised text so CRLF/LF renders of the same template are indistinguishable"
    )


# --------------------------------------------------------------------------
# Repair convergence for a doubled-frontmatter install.
# --------------------------------------------------------------------------


def _bogus_doubled_frontmatter(crlf_content: str, skill_name: str) -> str:
    """Hand-build the pre-#4998-fix doubled-frontmatter shape.

    Deliberately independent of ``ensure_skill_frontmatter`` so this helper
    keeps reproducing the historical corrupted shape after the fix: the old ``_RE_LEADING_FRONTMATTER`` regex matched
    ``\\n`` only, so it always treated CRLF-terminated frontmatter as
    absent and prepended a synthetic block ahead of the untouched CRLF
    original -- exactly this shape.
    """
    bogus = f"---\nname: {skill_name}\ndescription: bogus pre-fix frontmatter\n---\n"
    return bogus + crlf_content


def _seed_corrupted_install(
    project: Path,
    *,
    agent: str,
    skill_name: str,
    crlf_registry: SkillRegistry,
    manifest_hash_matches_disk: bool,
) -> Path:
    """Write a project SKILL.md in the pre-fix doubled shape, plus a manifest
    recording either that exact (corrupted) hash (repairable) or a
    different, stale hash (simulates a user edit since install -- stays
    ``consent_required``). Hashes use the canonical
    ``specify_cli.skills.manifest.compute_content_hash`` (the same hasher
    the production installer/manifest code uses) rather than a local
    ``hashlib`` call.
    """
    skill = next(s for s in crlf_registry.discover_skills() if s.name == skill_name)
    # read_bytes().decode() (not read_text()): read_text() applies universal
    # newlines, silently turning the CRLF fixture bytes into LF before they
    # ever reach _bogus_doubled_frontmatter -- the seeded corruption would
    # then be "bogus LF block + LF original", not the historical "bogus LF
    # block + CRLF original".
    crlf_source = skill.skill_md.read_bytes().decode("utf-8")
    corrupted = _bogus_doubled_frontmatter(crlf_source, skill_name).encode("utf-8")
    assert not _single_frontmatter_block(corrupted), "fixture helper must itself reproduce the doubled shape"

    installed_path = f".agents/skills/{skill_name}/SKILL.md"
    dest = project / installed_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(corrupted)
    on_disk_hash = compute_content_hash(dest)

    if manifest_hash_matches_disk:
        recorded_hash = on_disk_hash
    else:
        # A hash that differs from the real on-disk bytes, computed the
        # canonical way from a throwaway scratch file (never written to
        # `dest`, which must stay exactly the corrupted-at-install content).
        stale_probe = project / ".stale_hash_probe"
        stale_probe.write_bytes(corrupted + b"user edit")
        recorded_hash = compute_content_hash(stale_probe)
        stale_probe.unlink()

    manifest = ManagedSkillManifest(
        version=1,
        created_at=now_utc_iso(),
        updated_at=now_utc_iso(),
        spec_kitty_version="test",
        entries=[
            ManagedFileEntry(
                skill_name=skill_name,
                source_file="SKILL.md",
                installed_path=installed_path,
                installation_class=SKILL_CLASS_SHARED,
                agent_key=agent,
                content_hash=recorded_hash,
                installed_at=now_utc_iso(),
                delivery_mode="copy",
            )
        ],
    )
    save_manifest(manifest, project)
    return dest


def test_doctrine_skill_fix_converges_when_manifest_hash_matches_corrupted_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctrine-skill leg, via the real
    ``spec-kitty doctor tool-surfaces --kind doctrine-skill --fix`` CLI.
    """
    names = _sample_skill_names(1)
    skill_name = names[0]
    project = _make_project(tmp_path, agents=["codex"])
    _assert_scoped_to_tmp_path(project, tmp_path, Path.home())

    crlf_registry = _crlf_registry(tmp_path, names)
    # Keep the monkeypatched CRLF registry active DURING the repair run --
    # with LF package sources the repair converges even without the fix,
    # making the test vacuous otherwise.
    monkeypatch.setattr(SkillRegistry, "from_package", classmethod(lambda cls: crlf_registry))

    dest = _seed_corrupted_install(
        project,
        agent="codex",
        skill_name=skill_name,
        crlf_registry=crlf_registry,
        manifest_hash_matches_disk=True,
    )

    with contextlib.chdir(project):
        result = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "doctrine-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True, payload
    assert skill_name in " ".join(payload["repair"]["repaired"]), payload["repair"]

    repaired_content = dest.read_bytes()
    assert _single_frontmatter_block(repaired_content), f"repair left a doubled frontmatter block -- first 300 bytes: {repaired_content[:300]!r}"
    expected_skill = next(s for s in crlf_registry.discover_skills() if s.name == skill_name)
    normalized_source = expected_skill.skill_md.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    # The repaired body is the CRLF source normalised to LF and re-wrapped
    # with the SAME frontmatter the source already carried (a real skill
    # source already has its own frontmatter, so `ensure_skill_frontmatter`
    # must now recognise it post-normalisation and leave it byte-for-byte
    # in place rather than prepending a synthetic block).
    assert repaired_content == normalized_source.encode("utf-8"), (
        f"repaired content does not match the normalised CRLF source\ngot:      {repaired_content[:300]!r}\nexpected: {normalized_source.encode('utf-8')[:300]!r}"
    )

    # A second --fix run is a clean no-op.
    with contextlib.chdir(project):
        result2 = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "doctrine-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    assert result2.exit_code == 0, result2.output
    payload2 = json.loads(result2.output)
    assert payload2["findings"] == [], payload2


@pytest.mark.integration
@pytest.mark.slow
def test_doctrine_skill_repair_converges_via_real_upgrade_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctrine-skill leg, via the real ``spec-kitty init`` +
    ``spec-kitty upgrade --yes`` CLI on a REAL project (not the hand-built
    ``_make_project`` fixture other tests in this module use).

    A real ``spec-kitty init``-built project is used because the hand-built
    ``_make_project`` fixture does not carry the full installed surface a real
    ``upgrade`` plans against. On a real project,
    ``spec-kitty upgrade --yes`` repairs doctrine skills through
    ``upgrade.assessment.prepare_upgrade_repairs``/``apply_upgrade_repairs``
    (the ``ManagedSkillsProvider``, ``kinds=(DOCTRINE_SKILL,)``) on EVERY
    invocation -- including the "Project is already up to date!" path where
    no version migration runs at all (``_finalizer_step_surface_repair`` in
    ``cli/commands/upgrade.py``). It
    never calls ``install_all_skills`` (that function is exercised
    separately below, for the one-shot migration path it DOES own).

    This test is slower than the rest of the module (~50s: a real
    ``spec-kitty init`` plus a full-catalogue CRLF registry copy, so the
    monkeypatched ``SkillRegistry.from_package`` never retires skills the
    real init installed but a partial CRLF registry would lack) --
    ``integration``/``slow``-marked rather than inheriting the module's
    ``fast`` mark.

    Pre-fix, the seeded corruption stays doubled (byte-inequal to the LF
    source) after BOTH upgrade runs; fixed, it converges after the first and
    the second is a no-op.
    """
    project = tmp_path / "project"
    project.mkdir()
    # Scoping check moves to AFTER `init` (not before, unlike this module's
    # other tests): `locate_project_root()` needs a `.kittify/` to resolve,
    # which only exists once `init` has run -- before that, `project` is
    # just an empty directory and the resolver correctly returns None.
    assert Path.home().is_relative_to(tmp_path)
    assert project.is_relative_to(tmp_path)

    with contextlib.chdir(project):
        init_result = _runner.invoke(root_app, ["init", "--ai", "codex", "--non-interactive"], catch_exceptions=False)
    assert init_result.exit_code == 0, init_result.output
    _assert_scoped_to_tmp_path(project, tmp_path, Path.home())

    # Pick one of the doctrine skills init actually installed.
    installed_skill_dirs = sorted((project / ".agents" / "skills").iterdir())
    assert installed_skill_dirs, "spec-kitty init installed no doctrine skills to corrupt"
    skill_name = installed_skill_dirs[0].name
    skill_md = project / ".agents" / "skills" / skill_name / "SKILL.md"
    assert skill_md.is_file()

    # Full-catalogue CRLF registry: `prepare_upgrade_repairs`'s
    # `assess_skill_installation` retires (deletes) any already-installed
    # skill absent from the registry it is given, so a partial registry
    # would corrupt the project as a side effect instead of leaving every
    # OTHER skill untouched, as a real CRLF checkout would.
    crlf_registry = _crlf_registry(tmp_path, _all_doctrine_skill_names())
    crlf_skill = next(s for s in crlf_registry.discover_skills() if s.name == skill_name)
    crlf_source = crlf_skill.skill_md.read_bytes().decode("utf-8")
    corrupted = _bogus_doubled_frontmatter(crlf_source, skill_name).encode("utf-8")
    assert not _single_frontmatter_block(corrupted)
    # Managed skill assets install read-only (0o444). Root ignores that, so
    # the seed must restore owner-write itself or it fails on a non-root runner.
    skill_md.chmod(skill_md.stat().st_mode | stat.S_IWUSR)
    skill_md.write_bytes(corrupted)

    # Rewrite that one manifest entry's recorded hash to match the
    # corrupted-at-install bytes, so the repair-convergence precondition
    # (manifest hash == on-disk hash) holds.
    manifest = load_manifest(project, strict=True)
    assert manifest is not None
    rel_path = skill_md.relative_to(project).as_posix()
    manifest.entries = [replace(entry, content_hash=compute_content_hash(skill_md)) if entry.installed_path == rel_path else entry for entry in manifest.entries]
    assert any(entry.installed_path == rel_path for entry in manifest.entries), "seeded skill is not manifest-tracked"
    save_manifest(manifest, project)

    monkeypatch.setattr(SkillRegistry, "from_package", classmethod(lambda cls: crlf_registry))

    with contextlib.chdir(project):
        upgrade_result = _runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    assert upgrade_result.exit_code == 0, upgrade_result.output

    repaired_content = skill_md.read_bytes()
    assert _single_frontmatter_block(repaired_content), f"repair left a doubled frontmatter block -- first 300 bytes: {repaired_content[:300]!r}"
    lf_source_bytes = (_DOCTRINE_SKILLS_ROOT / skill_name / "SKILL.md").read_bytes()
    assert repaired_content == lf_source_bytes, (
        f"repaired content is not byte-equal to the LF package source\ngot:      {repaired_content[:300]!r}\nexpected: {lf_source_bytes[:300]!r}"
    )

    # A second `upgrade --yes` over the now-correct install is a no-op.
    with contextlib.chdir(project):
        second_upgrade_result = _runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    assert second_upgrade_result.exit_code == 0, second_upgrade_result.output
    assert skill_md.read_bytes() == repaired_content


def test_doctrine_skill_repair_converges_via_install_all_skills(tmp_path: Path) -> None:
    """Doctrine-skill leg, via ``install_all_skills`` -- the ONE-SHOT
    skill-pack migration path (``m_3_2_0rc35_spk_skill_pack`` and its
    siblings under ``upgrade/migrations/``), a DIFFERENT code path from the
    steady-state ``spec-kitty upgrade`` repair covered by
    ``test_doctrine_skill_repair_converges_via_real_upgrade_cli`` above: that command
    repairs doctrine skills through
    ``upgrade.assessment.prepare_upgrade_repairs``/``apply_upgrade_repairs``
    (the ``ManagedSkillsProvider``), which never calls
    ``install_all_skills``. This test is kept as a separate, narrower proof
    that the one-shot migration function converges the same corruption. No
    monkeypatch of ``SkillRegistry.from_package`` is needed: the CRLF
    registry is passed to ``install_all_skills`` directly, exactly as a
    migration passes its own resolved registry.
    """
    names = _sample_skill_names(1)
    skill_name = names[0]
    agent = "claude"
    project = _make_project(tmp_path, agents=[agent])
    _assert_scoped_to_tmp_path(project, tmp_path, Path.home())

    crlf_registry = _crlf_registry(tmp_path, names)

    root = get_primary_project_skill_root(agent)
    assert root is not None
    installed_path = f"{root}{skill_name}/SKILL.md"
    dest = project / installed_path
    dest.parent.mkdir(parents=True, exist_ok=True)

    skill = next(s for s in crlf_registry.discover_skills() if s.name == skill_name)
    # read_bytes().decode(), not read_text() -- see _seed_corrupted_install's
    # comment: read_text() would silently
    # normalise the CRLF fixture to LF before corruption, seeding "bogus LF
    # block + LF original" instead of the historical "bogus LF block + CRLF
    # original".
    crlf_source = skill.skill_md.read_bytes().decode("utf-8")
    corrupted = _bogus_doubled_frontmatter(crlf_source, skill_name).encode("utf-8")
    assert not _single_frontmatter_block(corrupted)
    dest.write_bytes(corrupted)

    manifest = ManagedSkillManifest(
        version=1,
        created_at=now_utc_iso(),
        updated_at=now_utc_iso(),
        spec_kitty_version="test",
        entries=[
            ManagedFileEntry(
                skill_name=skill_name,
                source_file="SKILL.md",
                installed_path=installed_path,
                installation_class=SKILL_CLASS_SHARED,
                agent_key=agent,
                content_hash=compute_content_hash(dest),
                installed_at=now_utc_iso(),
                delivery_mode="copy",
            )
        ],
    )
    save_manifest(manifest, project)

    # `install_all_skills` returns a manifest; the caller (here, standing
    # in for the upgrade migration) retains save ownership.
    updated_manifest = install_all_skills(project, [agent], crlf_registry, archived_paths=[])
    save_manifest(updated_manifest, project)

    repaired_content = dest.read_bytes()
    assert _single_frontmatter_block(repaired_content), f"repair left a doubled frontmatter block -- first 300 bytes: {repaired_content[:300]!r}"
    normalized_source = skill.skill_md.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    assert repaired_content == normalized_source.encode("utf-8")

    # Convergence: a second install_all_skills call over the now-correct
    # install is a byte-for-byte no-op.
    install_all_skills(project, [agent], crlf_registry, archived_paths=[])
    assert dest.read_bytes() == repaired_content


def _seed_self_consistent_command_skill_drift(tmp_path: Path) -> tuple[Path, Path, str]:
    """Install a CRLF-corrupted ``spec-kitty.accept`` command skill whose
    manifest records the corrupted hash (a self-consistent drift).

    Returns ``(project, installed SKILL.md path, correct SKILL.md text)``.
    """
    project = _make_project(tmp_path, agents=["codex"])
    _assert_scoped_to_tmp_path(project, tmp_path, Path.home())

    rendered = render(_COMMAND_TEMPLATE, "codex", "test-version", repo_root=None)
    correct_skill_md = rendered.to_skill_md()
    corrupted = correct_skill_md.replace("\n", "\r\n").encode("utf-8")
    assert b"\r" in corrupted

    installed_path = ".agents/skills/spec-kitty.accept/SKILL.md"
    dest = project / installed_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(corrupted)

    manifest = manifest_store.SkillsManifest(
        entries=[
            manifest_store.ManifestEntry(
                path=installed_path,
                content_hash=manifest_store.fingerprint_file(dest),
                agents=("codex",),
                installed_at=now_utc_iso(),
                spec_kitty_version="test",
            )
        ]
    )
    manifest_store.save(project, manifest)
    return project, dest, correct_skill_md


def test_command_skill_repair_converges_via_tool_surfaces_fix(tmp_path: Path) -> None:
    """Command-skill leg, via the real
    ``spec-kitty doctor tool-surfaces --kind command-skill --fix`` CLI.

    The corrupted fixture is a representative pre-fix-corrupted command
    skill (current correct render with CRLF re-injected into the body) --
    not a byte-exact replay of the historical bug, which also altered the
    extracted description. The point is only that a
    self-consistent (manifest-matching) content drift is detected and
    repaired: ``command_skills.py``'s provider always re-renders every
    command fresh via ``command_installer.prepare_commands`` and diffs
    against disk (unlike ``command_installer.verify()`` -- see
    ``test_doctor_skills_fix_converges_self_consistent_drift``
    below (marked ``xfail``, issue #5281) and the module docstring for the
    contrasting negative case).
    """
    project, dest, correct_skill_md = _seed_self_consistent_command_skill_drift(tmp_path)

    with contextlib.chdir(project):
        result = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "command-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True, payload

    repaired_content = dest.read_bytes()
    assert b"\r" not in repaired_content
    assert repaired_content.decode("utf-8") == correct_skill_md

    # Second run is a clean no-op.
    with contextlib.chdir(project):
        result2 = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "command-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    assert result2.exit_code == 0, result2.output
    payload2 = json.loads(result2.output)
    assert payload2["repair"]["repaired"] == [], payload2["repair"]
    assert payload2["findings"] == [], payload2


@pytest.mark.xfail(
    strict=True,
    reason="doctor skills --fix does not re-derive expected hashes; see #5281",
)
def test_doctor_skills_fix_converges_self_consistent_drift(tmp_path: Path) -> None:
    """DESIRED behaviour (currently a known, filed gap -- issue #5281):
    ``spec-kitty doctor skills --fix`` should converge a self-consistent
    (manifest-matching) corrupted command-skill install, the same way
    ``doctor tool-surfaces --kind command-skill --fix`` already does (see
    ``test_command_skill_repair_converges_via_tool_surfaces_fix``
    above). It currently does not, because ``command_installer.verify()``
    (command_installer.py:1101-1146) only compares the on-disk SHA-256 to
    the manifest-RECORDED hash -- it never re-derives an expected hash from
    the canonical template the way the doctrine-skill verifier does. A
    corruption whose manifest was written at the same (corrupted) install
    time is therefore invisible to ``verify()``, and
    ``_repair_command_skill_state`` (``_command_surface_doctor.py``) only
    acts on ``report.gaps or report.stale or uninstalled_agents or
    vibe_config_missing`` -- none of which a self-consistent drift sets.
    This gap pre-dates and is unrelated to the CRLF fix.
    ``@pytest.mark.xfail(strict=True)`` marks
    this a KNOWN failure rather than asserting the defect as expected
    behaviour: when #5281 is fixed, this test flips to XPASS and the
    strict marker forces the marker's removal.
    """
    project, dest, correct_skill_md = _seed_self_consistent_command_skill_drift(tmp_path)

    with contextlib.chdir(project):
        result = _runner.invoke(doctor_app, ["skills", "--fix", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True, payload

    repaired_content = dest.read_bytes()
    assert b"\r" not in repaired_content
    assert repaired_content.decode("utf-8") == correct_skill_md

    # A second run is a clean no-op once repaired.
    with contextlib.chdir(project):
        result2 = _runner.invoke(doctor_app, ["skills", "--fix", "--json"], catch_exceptions=False)
    assert result2.exit_code == 0, result2.output
    assert dest.read_bytes() == repaired_content


def test_drifted_user_edit_stays_consent_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    names = _sample_skill_names(1)
    skill_name = names[0]
    agent = "codex"
    project = _make_project(tmp_path, agents=[agent])
    _assert_scoped_to_tmp_path(project, tmp_path, Path.home())

    crlf_registry = _crlf_registry(tmp_path, names)
    monkeypatch.setattr(SkillRegistry, "from_package", classmethod(lambda cls: crlf_registry))

    dest = _seed_corrupted_install(
        project,
        agent=agent,
        skill_name=skill_name,
        crlf_registry=crlf_registry,
        manifest_hash_matches_disk=False,
    )
    before_bytes = dest.read_bytes()

    with contextlib.chdir(project):
        result = _runner.invoke(
            doctor_app,
            ["tool-surfaces", "--kind", "doctrine-skill", "--fix", "--json"],
            catch_exceptions=False,
        )
    payload = json.loads(result.output)

    # File must be left completely untouched -- never silently overwritten.
    assert dest.read_bytes() == before_bytes, "consent-required file was silently overwritten"

    # The contract is the specific `consent_required` classification, not
    # merely "some failure happened": the installer's disposition machinery
    # records a hash-mismatched path as `consent_required`
    # (installer.py:895), which surfaces in the `doctor tool-surfaces` JSON
    # as this exact surface id landing in `repair.skipped` -- never in
    # `repaired` or `failed`.
    surface_id = f"{agent}.doctrine_skill.{skill_name}.SKILL.md"
    assert payload["repair"]["skipped"] == [surface_id], payload["repair"]
    assert surface_id not in payload["repair"]["repaired"], payload["repair"]
    assert surface_id not in payload["repair"]["failed"], payload["repair"]


# --------------------------------------------------------------------------
# ``.gitattributes`` pins both source trees to eol=lf.
# --------------------------------------------------------------------------


def test_gitattributes_pins_source_trees_to_lf() -> None:
    doctrine_sample = "src/charter/offering/skills/spec-kitty/SKILL.md"
    command_sample = "packs/built-in/missions/mission-steps/software-dev/specify/prompt.md"
    assert (_REPO_ROOT / doctrine_sample).is_file(), doctrine_sample
    assert (_REPO_ROOT / command_sample).is_file(), command_sample

    result = subprocess.run(
        ["git", "check-attr", "eol", "--", doctrine_sample, command_sample],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    assert lines == {
        f"{doctrine_sample}: eol: lf",
        f"{command_sample}: eol: lf",
    }, result.stdout
