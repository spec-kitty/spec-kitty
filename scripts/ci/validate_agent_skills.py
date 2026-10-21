"""Validate every generated and shipped Agent Skill with the reference validator (#6475).

FR-015 / SC-001 of mission ``command-skill-names-and-antigravity-01M5DBWT``: a
non-conformant ``SKILL.md`` fails the PR. The script

1. runs ``spec-kitty init --ai codex,claude --non-interactive`` in a scratch
   project with an isolated ``HOME`` and collects every skill folder it wrote,
   in the project and in the home directory;
2. projects the shipped skills (``src/charter/offering/skills/*``) for the
   shared root through :func:`specify_cli.skills.skill_frontmatter.project_skill_bytes`
   into a scratch directory;
3. validates each **shared-root** folder with the reference validator
   ``skills-ref==0.1.1`` (PyPI, anthropics/agentskills; run through ``uvx``,
   never a project dependency, research R-4) *and* with the in-repo mirror
   :func:`~specify_cli.skills.skill_frontmatter.validate_skill_frontmatter`,
   and fails when either reports a violation or the two disagree;
4. validates each **native-root** folder (``.claude/skills`` and the other
   :data:`~specify_cli.skills.skill_frontmatter.NATIVE_SKILL_ROOTS`) with the
   in-repo checker in native mode only, since those roots keep the Claude-style
   keys by design (FR-013) and the reference validator would refuse them.

Exit codes: ``0`` every skill valid, ``1`` a violation or a disagreement,
``2`` the environment could not be prepared (``init`` failed, ``uvx`` missing,
the reference run failed). The functions are pure where they can be so the unit
tests (``tests/ci/test_validate_agent_skills.py``) need no network.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from specify_cli.skills.skill_frontmatter import (
    SKILL_FILENAME,
    is_shared_root,
    project_skill_bytes,
    validate_skill_frontmatter,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: The reference validator, pinned (research R-4, DIRECTIVE_051 supply-chain note).
REFERENCE_SPEC = "skills-ref==0.1.1"

#: Runs ``skills_ref.validate`` (the function behind ``agentskills validate``) over every
#: folder passed as an argument in ONE process and prints ``{folder: [errors]}`` as JSON.
#: Keep it in step with skills-ref's CLI (``skills_ref.cli.validate_cmd`` in 0.1.1): the CLI
#: takes one folder per process, which would cost one interpreter start per skill.
_REFERENCE_PROGRAM = "import json, pathlib, sys\nfrom skills_ref import validate\nprint(json.dumps({d: list(validate(pathlib.Path(d))) for d in sys.argv[1:]}))\n"

#: The agents a fresh ``init`` is run for: one shared-root agent and one native-root agent.
INIT_AGENTS = "codex,claude"

DEFAULT_SHIPPED_ROOT = _REPO_ROOT / "src" / "charter" / "offering" / "skills"

_SKILLS_DIRNAME = "skills"
_EXIT_OK, _EXIT_VIOLATION, _EXIT_ENVIRONMENT = 0, 1, 2

#: ``(argv) -> (returncode, stdout, stderr)``; injectable so the unit tests run offline.
CommandRunner = Callable[[Sequence[str]], tuple[int, str, str]]


class EnvironmentPreparationError(RuntimeError):
    """The scratch project or the reference validator could not be prepared or run."""


@dataclass(frozen=True)
class SkillTarget:
    """One skill folder to validate; ``shared`` selects the rules (spec-only vs native allowance)."""

    label: str
    skill_dir: Path
    shared: bool


@dataclass(frozen=True)
class SkillVerdict:
    """The two validators' findings for one :class:`SkillTarget` (``reference`` is None for native)."""

    target: SkillTarget
    in_repo: tuple[str, ...]
    reference: tuple[str, ...] | None

    @property
    def disagreement(self) -> bool:
        return self.reference is not None and bool(self.in_repo) != bool(self.reference)

    @property
    def failed(self) -> bool:
        return bool(self.in_repo) or bool(self.reference) or self.disagreement


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def discover_skill_dirs(base: Path, label: str) -> list[SkillTarget]:
    """Every ``<root>/<skill>/SKILL.md`` under *base* whose root folder is named ``skills``.

    The root is taken relative to *base* (the project or the home directory), which is
    the form :func:`is_shared_root` classifies.
    """
    targets = []
    for skill_md in sorted(base.rglob(SKILL_FILENAME)):
        skill_dir = skill_md.parent
        if skill_dir.parent.name != _SKILLS_DIRNAME:
            continue
        root_rel = skill_dir.parent.relative_to(base).as_posix()
        targets.append(SkillTarget(f"{label}:{root_rel}/{skill_dir.name}", skill_dir, is_shared_root(root_rel)))
    return targets


def project_shipped_skills(source_root: Path, dest: Path) -> list[SkillTarget]:
    """Write each shipped skill's shared-root projection to ``dest/<skill>/SKILL.md``."""
    targets = []
    for source_md in sorted(source_root.glob(f"*/{SKILL_FILENAME}")):
        name = source_md.parent.name
        skill_dir = dest / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / SKILL_FILENAME).write_bytes(project_skill_bytes(source_md.read_bytes(), shared=True, skill_name=name))
        targets.append(SkillTarget(f"shipped:{name}", skill_dir, shared=True))
    return targets


def isolated_env(home: Path, base: Mapping[str, str]) -> dict[str, str]:
    """*base* with the home and XDG directories pointed into *home* (cache dirs kept)."""
    env = dict(base)
    env["HOME"] = str(home)
    for var, rel in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"), ("XDG_STATE_HOME", ".local/state")):
        env[var] = str(home / rel)
    return env


def init_command(executable: str = sys.executable) -> list[str]:
    """The ``spec-kitty init`` invocation for the scratch project (run from inside it)."""
    return [executable, "-m", "specify_cli", "init", ".", "--ai", INIT_AGENTS, "--non-interactive"]


def generate_project(workdir: Path, run: CommandRunner | None = None) -> tuple[Path, Path]:
    """Create ``workdir/project`` with a fresh ``init``; return ``(project, home)``."""
    project, home = workdir / "project", workdir / "home"
    project.mkdir(parents=True)
    home.mkdir(parents=True)
    env = isolated_env(home, os.environ)
    runner = run or _subprocess_runner(cwd=project, env=env)
    for argv in (["git", "init", "-q"], init_command()):
        code, _stdout, stderr = runner(argv)
        if code != 0:
            raise EnvironmentPreparationError(f"`{' '.join(argv)}` exited {code}: {stderr.strip()}")
    return project, home


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def reference_command(skill_dirs: Iterable[Path], uvx: str = "uvx") -> list[str]:
    """The single ``uvx`` call that runs the reference validator over *skill_dirs*."""
    return [uvx, "--from", REFERENCE_SPEC, "python", "-I", "-c", _REFERENCE_PROGRAM, *(str(path) for path in skill_dirs)]


def parse_reference_output(stdout: str, skill_dirs: Sequence[Path]) -> dict[Path, tuple[str, ...]]:
    """Map each folder to its reference errors; refuse output that does not cover every folder."""
    try:
        raw = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else None
    except json.JSONDecodeError as exc:
        raise EnvironmentPreparationError(f"reference validator printed no JSON result: {exc}") from exc
    if not isinstance(raw, dict):
        raise EnvironmentPreparationError("reference validator printed no JSON mapping")
    missing = [str(path) for path in skill_dirs if str(path) not in raw]
    if missing:
        raise EnvironmentPreparationError(f"reference validator skipped {len(missing)} folder(s), e.g. {missing[0]}")
    return {path: tuple(str(error) for error in raw[str(path)]) for path in skill_dirs}


def run_reference(skill_dirs: Sequence[Path], run: CommandRunner) -> dict[Path, tuple[str, ...]]:
    """Validate *skill_dirs* with ``skills-ref`` through *run* (no call when there are none)."""
    if not skill_dirs:
        return {}
    code, stdout, stderr = run(reference_command(skill_dirs))
    if code != 0:
        raise EnvironmentPreparationError(f"reference validator exited {code}: {stderr.strip()}")
    return parse_reference_output(stdout, skill_dirs)


def evaluate(targets: Sequence[SkillTarget], run: CommandRunner) -> list[SkillVerdict]:
    """Validate every target: shared ones with both validators, native ones in-repo (native mode)."""
    shared_dirs = [target.skill_dir for target in targets if target.shared]
    reference = run_reference(shared_dirs, run)
    return [
        SkillVerdict(
            target=target,
            in_repo=tuple(validate_skill_frontmatter(target.skill_dir, native=not target.shared)),
            reference=reference[target.skill_dir] if target.shared else None,
        )
        for target in targets
    ]


# ---------------------------------------------------------------------------
# Reporting and entry point
# ---------------------------------------------------------------------------


def _verdict_lines(verdict: SkillVerdict) -> list[str]:
    lines = [f"FAIL {verdict.target.label}"]
    if verdict.disagreement:
        lines.append("  validators disagree (in-repo mirror vs skills-ref): fix skill_frontmatter.validate_skill_frontmatter")
    lines.extend(f"  in-repo: {error}" for error in verdict.in_repo)
    lines.extend(f"  skills-ref: {error}" for error in verdict.reference or ())
    return lines


def render_report(verdicts: Sequence[SkillVerdict]) -> str:
    """A per-skill failure list followed by one summary line."""
    failed = [verdict for verdict in verdicts if verdict.failed]
    shared = sum(1 for verdict in verdicts if verdict.target.shared)
    lines = [line for verdict in failed for line in _verdict_lines(verdict)]
    lines.append(f"Agent Skills validation ({REFERENCE_SPEC}): validated={len(verdicts)} shared={shared} native={len(verdicts) - shared} failed={len(failed)}")
    return "\n".join(lines)


def _subprocess_runner(cwd: Path | None = None, env: Mapping[str, str] | None = None) -> CommandRunner:
    def run(argv: Sequence[str]) -> tuple[int, str, str]:
        completed = subprocess.run(list(argv), cwd=cwd, env=None if env is None else dict(env), capture_output=True, text=True, check=False)
        return completed.returncode, completed.stdout, completed.stderr

    return run


def collect_targets(workdir: Path, shipped_root: Path) -> list[SkillTarget]:
    """Generated (project + home) and shipped targets, in that order."""
    project, home = generate_project(workdir)
    generated = discover_skill_dirs(project, "project") + discover_skill_dirs(home, "home")
    if not generated:
        raise EnvironmentPreparationError("`spec-kitty init` wrote no skill folder")
    if not any(target.shared for target in generated):
        raise EnvironmentPreparationError("`spec-kitty init` wrote no shared-root skill folder, so the reference validator would check none")
    shipped = project_shipped_skills(shipped_root, workdir / "shipped")
    if not shipped:
        raise EnvironmentPreparationError(f"no shipped skill found under {shipped_root}")
    return generated + shipped


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--shipped-root", type=Path, default=DEFAULT_SHIPPED_ROOT, help="folder of shipped skill sources")
    args = parser.parse_args(argv)
    if shutil.which("uvx") is None:
        print("uvx is not on PATH; it runs the reference validator", file=sys.stderr)
        return _EXIT_ENVIRONMENT
    with tempfile.TemporaryDirectory(prefix="agent-skills-") as scratch:
        try:
            verdicts = evaluate(collect_targets(Path(scratch), args.shipped_root), _subprocess_runner())
        except EnvironmentPreparationError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return _EXIT_ENVIRONMENT
    print(render_report(verdicts))
    return _EXIT_VIOLATION if any(verdict.failed for verdict in verdicts) else _EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
