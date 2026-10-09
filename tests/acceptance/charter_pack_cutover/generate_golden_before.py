"""Generate the NFR-001 golden "before" sets and the SC-004 ``cli_before.json`` (#3732, T003).

Run ONCE, at the mission base, with the pre-cutover code::

    uv run --frozen python -m tests.acceptance.charter_pack_cutover.generate_golden_before

After the cutover no code can read the legacy shapes, so "before" is measured now and
frozen together with this generator's digest, the measuring helper's digest
(``_effective_set.py``) and the base SHA (``_meta.json``). Tests never recompute it.

It refuses (exit 2, nothing written) unless the tree is pre-cutover:
``kernel.doctrine_root`` and ``specify_cli.doctrine`` import, and
``src/charter/activation/packs/default.yaml`` exists. It also refuses when ``src/``
or ``packs/`` carry uncommitted changes, so the recorded SHA is the code that ran.

Besides the golden data it freezes the trees the legacy builders copy
(``static/``): a real base synthesis (project layer + manifest + provenance), a
real project pack-skill projection, the shipped copies of three removed skills and
one calibration overlay.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from unittest import mock
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ._requirements import REPO_ROOT
from ._support import file_digest, read_json_output, run_cli
from .legacy_fixtures import (
    BUILDERS,
    FIXTURES_ROOT,
    NFR001_FIXTURES,
    PROJECT_SKILL_ID,
    PROJECT_SKILL_NAMESPACE,
    build_doctrine_command_fixture,
    finish,
    write_text,
)

GENERATOR_PATH = Path(__file__).resolve()
EFFECTIVE_SET_PATH = GENERATOR_PATH.parent / "_effective_set.py"
GOLDEN_DIRNAME = "golden_before"
META_NAME = "_meta.json"
CLI_BEFORE_NAME = "cli_before.json"

#: Skills FR-008 removes whose shipped copies the installed-skills fixture needs.
FROZEN_REMOVED_SKILLS = ("spk-doctrine-charter", "spk-doctrine-glossary", "spk-doctrine-show-me")
FROZEN_OVERLAY = ".kittify/doctrine/overlays/calibration-software-dev.yaml"
_FIXED_STAMP = "2026-10-06T00:00:00+00:00"
#: A fetched pack's commit SHA (commit timestamps make it differ per run).
_GIT_SHA = re.compile(r"\b[0-9a-f]{7,40}\b")


def is_pre_cutover_tree() -> tuple[bool, str]:
    """Whether this checkout still carries the pre-cutover code the golden data needs."""
    if importlib.util.find_spec("kernel.doctrine_root") is None:
        return False, "kernel.doctrine_root missing"
    if not (REPO_ROOT / "src" / "charter" / "activation" / "packs" / "default.yaml").exists():
        return False, "src/charter/activation/packs/default.yaml missing"
    if importlib.util.find_spec("specify_cli.doctrine") is None:
        return False, "specify_cli.doctrine missing"
    return True, "pre-cutover tree"


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], check=True, capture_output=True, text=True).stdout.strip()


@contextlib.contextmanager
def _isolated_home() -> Iterator[Path]:
    """Point HOME / XDG at a throwaway directory: in-process CLI runs write global state."""
    keys = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME")
    home = Path(tempfile.mkdtemp(prefix="charter-pack-cutover-home-"))
    overrides = {"HOME": str(home), **{key: str(home / key.lower()) for key in keys}}
    try:
        # patch.dict restores the whole mapping on exit, deleting keys that were unset.
        with mock.patch.dict(os.environ, overrides):
            yield home
    finally:
        shutil.rmtree(home, ignore_errors=True)


def _dump(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# Frozen static trees
# --------------------------------------------------------------------------------------


def _freeze_synthesized(static: Path, scratch: Path) -> None:
    from charter.activation.synthesizer import FixtureAdapter, SynthesisRequest, SynthesisTarget, synthesize

    repo = scratch / "synthesized"
    (repo / ".kittify" / "charter").mkdir(parents=True)
    (repo / ".kittify" / "doctrine").mkdir(parents=True)
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    request = SynthesisRequest(
        target=target,
        interview_snapshot={
            "mission_type": "software_dev",
            "language_scope": ["python"],
            "testing_philosophy": "test-driven development with high coverage",
            "neutrality_posture": "balanced",
            "selected_directives": ["DIRECTIVE_003"],
            "risk_appetite": "moderate",
        },
        doctrine_snapshot={
            "directives": {
                "DIRECTIVE_003": {"id": "DIRECTIVE_003", "title": "Decision Documentation", "body": "Document significant architectural decisions via ADRs."}
            },
            "tactics": {},
            "styleguides": {},
        },
        drg_snapshot={"nodes": [{"urn": "directive:DIRECTIVE_003", "kind": "directive"}], "edges": [], "schema_version": "1"},
        run_id="01KPE222CD1MMCYEGB3ZCY51VR",
        adapter_hints={"language": "python"},
    )
    synthesize(request, adapter=FixtureAdapter(fixture_root=REPO_ROOT / "tests" / "charter" / "fixtures" / "synthesizer"), repo_root=repo)
    shutil.copytree(repo / ".kittify", static / "synthesized" / ".kittify")


def _freeze_project_pack_skills(static: Path, scratch: Path) -> None:
    project = scratch / "project-pack-skills"
    skills = project / ".kittify" / "doctrine" / "skills"
    write_text(
        skills / f"{PROJECT_SKILL_ID}.skill.yaml",
        f'schema_version: "1.0"\nid: {PROJECT_SKILL_ID}\ntitle: Skill {PROJECT_SKILL_ID}\n'
        f"description: Pack skill {PROJECT_SKILL_ID}.\nform: prompt\nbody_path: {PROJECT_SKILL_ID}.skill.md\n",
    )
    write_text(skills / f"{PROJECT_SKILL_ID}.skill.md", f"Run {PROJECT_SKILL_ID}: $ARGUMENTS\n")
    finish(
        project,
        {
            "agents": {"available": ["claude"]},
            "charter_packs": {"project": {"skill_namespace": PROJECT_SKILL_NAMESPACE}},
            "mission_type_activations": ["software-dev"],
        },
    )
    result = run_cli(["charter", "activate", "skill", PROJECT_SKILL_ID], project)
    if result.exit_code != 0:
        raise RuntimeError(f"pack skill activation failed at base:\n{result.output}")
    manifest_path = project / ".kittify" / "skills-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["created_at"] = manifest["updated_at"] = _FIXED_STAMP
    for entry in manifest["entries"]:
        entry["installed_at"] = _FIXED_STAMP
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    target = static / "project_pack_skills"
    for rel in (".kittify/doctrine/skills", ".kittify/runtime/pack-skills", ".claude/skills"):
        shutil.copytree(project / rel, target / rel)
    shutil.copy2(manifest_path, target / ".kittify" / "skills-manifest.json")


def _freeze_removed_skills(static: Path) -> None:
    for name in FROZEN_REMOVED_SKILLS:
        source = REPO_ROOT / "src" / "charter" / "offering" / "skills" / name / "SKILL.md"
        target = static / "removed_skills" / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _freeze_overlays(static: Path) -> None:
    target = static / "overlays" / FROZEN_OVERLAY
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / FROZEN_OVERLAY, target)


def freeze_static_trees(static: Path, scratch: Path) -> None:
    if static.exists():
        shutil.rmtree(static)
    _freeze_synthesized(static, scratch)
    _freeze_project_pack_skills(static, scratch)
    _freeze_removed_skills(static)
    _freeze_overlays(static)


# --------------------------------------------------------------------------------------
# Golden "before" sets
# --------------------------------------------------------------------------------------


def charter_list_rows(project: Path) -> list[dict[str, Any]]:
    """``charter list --json`` activated rows (paths stripped, lists sorted)."""
    result = run_cli(["charter", "list", "--json"], project)
    if result.exit_code != 0:
        raise RuntimeError(f"charter list failed for {project.name}:\n{result.output}")
    payload = read_json_output(result)
    rows: list[dict[str, Any]] = []
    for row in payload["kinds"]:
        activated = row.get("activated")
        rows.append({"kind": row["kind"], "activated": sorted(activated) if isinstance(activated, list) else activated})
    return sorted(rows, key=lambda r: str(r["kind"]))


def generate_goldens(out_dir: Path, scratch: Path, base_sha: str) -> None:
    from ._effective_set import builtin_inventory, effective_set

    inventory = builtin_inventory()
    for name in NFR001_FIXTURES:
        project = BUILDERS[name](scratch / "golden" / name)
        _dump(
            out_dir / GOLDEN_DIRNAME / f"{name}.json",
            {"fixture": name, "base_sha": base_sha, "effective": effective_set(project, inventory), "charter_list": charter_list_rows(project)},
        )


def record_cli_before(out_dir: Path, scratch: Path, base_sha: str) -> None:
    from .test_cli_surface import DOCTRINE_LEAVES, json_key_set, key_lines, normalise

    leaves: dict[str, Any] = {}
    for leaf in DOCTRINE_LEAVES:
        project = build_doctrine_command_fixture(scratch / "cli" / leaf.key)
        result = run_cli(list(leaf.old), project)
        text = normalise(result.output, project)
        entry: dict[str, Any] = {"argv": list(leaf.old), "exit_code": result.exit_code, "stdout": _GIT_SHA.sub("<SHA>", normalise(result.stdout, project))}
        if leaf.json_keys:
            entry["json_keys"] = json_key_set(read_json_output(result))
        else:
            entry["key_lines"] = key_lines(text, leaf.key_patterns)
            if len(entry["key_lines"]) != len(leaf.key_patterns):
                raise RuntimeError(f"{leaf.key}: not every key pattern matched at base:\n{text}")
        leaves[leaf.key] = entry
    _dump(out_dir / CLI_BEFORE_NAME, {"base_sha": base_sha, "leaves": leaves})


def _refuse(reason: str) -> int:
    print(f"refusing: pre-cutover code required ({reason})", file=sys.stderr)
    return 2


def _uncommitted_code() -> str:
    return _git("status", "--porcelain", "--", "src", "packs")


def main(out_dir: Path = FIXTURES_ROOT) -> int:
    ok, reason = is_pre_cutover_tree()
    if not ok:
        return _refuse(reason)
    if _uncommitted_code():
        return _refuse("src/ or packs/ has uncommitted changes")
    from kernel.clock import now_utc

    from specify_cli import __version__

    base_sha = _git("rev-parse", "HEAD")
    with _isolated_home(), tempfile.TemporaryDirectory(prefix="charter-pack-cutover-golden-") as tmp:
        scratch = Path(tmp)
        freeze_static_trees(out_dir / "static", scratch)
        generate_goldens(out_dir, scratch, base_sha)
        record_cli_before(out_dir, scratch, base_sha)
    _dump(
        out_dir / GOLDEN_DIRNAME / META_NAME,
        {
            "base_sha": base_sha,
            "package_version": __version__,
            "python": sys.version.split()[0],
            "generated_at": now_utc().isoformat(),
            "generator_digest": file_digest(GENERATOR_PATH),
            "effective_set_digest": file_digest(EFFECTIVE_SET_PATH),
            "fixtures": sorted(NFR001_FIXTURES),
        },
    )
    print(f"golden before-sets written for {len(NFR001_FIXTURES)} fixtures at {base_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
