"""Bounded G0/G1/G5 and P6 preparation using the real public init/upgrade."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from tests.upgrade.preview_support.process import ProcessResult, child_environment, run_process
from tests.upgrade.preview_support.provenance import SourceIdentity, identify_source
from tests.upgrade.preview_support.snapshot import Snapshot, net_delta, snapshot


@dataclass(frozen=True)
class PreviewCase:
    """One project and one home attached only after canonical setup completes."""

    project: Path
    env: dict[str, str]
    identity: SourceIdentity
    setup: tuple[ProcessResult, ...]

    def observe(self) -> Snapshot:
        """Include the entire project, measured home, and temporary root."""
        return snapshot({"project": self.project, "home": Path(self.env["HOME"]), "temp": Path(self.env["TMPDIR"])})

    def run(self, *args: str) -> ProcessResult:
        """Invoke the verified ordinary console script, without an audit wrapper."""
        return run_process([self.identity.executable, *args], self.project, self.env)

    def retain(self, destination: Path, result: ProcessResult, before: Snapshot, after: Snapshot) -> None:
        """Persist complete raw observations outside measured roots before assertions."""
        for root in (self.project, Path(self.env["HOME"]), Path(self.env["TMPDIR"])):
            assert not destination.resolve().is_relative_to(root.resolve()), "Evidence would pollute measured roots"
        destination.mkdir(parents=True, exist_ok=True)
        receipt = {
            "identity": asdict(self.identity),
            "command": asdict(result),
            "environment": self.env,
            "setup": [asdict(item) for item in self.setup],
            "effects": [asdict(item) for item in net_delta(before, after)],
            "git_effects": [asdict(item) for item in net_delta(before, after) if item.root == "project" and (item.path == ".git" or item.path.startswith(".git/"))],
        }
        (destination / "command.json").write_text(json.dumps(receipt, indent=2) + "\n")
        for name, observed in (("before", before), ("after", after)):
            rows = [{"root": root, "path": path, **asdict(node)} for (root, path), node in sorted(observed.items())]
            (destination / f"{name}.json").write_text(json.dumps(rows, indent=2) + "\n")
        (destination / "stdout.txt").write_text(result.stdout)
        (destination / "stderr.txt").write_text(result.stderr)


def prepare_case(sandbox: Path, checkout: Path, *, global_state: str = "G5") -> PreviewCase:
    """Prepare real manifests under a setup home; keep G0 measured home absent."""
    assert global_state in {"G0", "G1", "G5"}
    project = sandbox / "project"
    project.mkdir(parents=True)
    setup_env = child_environment(sandbox / "setup")
    identity = identify_source(checkout / ".venv/bin/spec-kitty", checkout, setup_env)
    assert not identity.source_diff, "Baseline source is dirty"
    setup = []
    for args in (
        ["git", "init", "-q", "-b", "preview-fixture"],
        ["git", "config", "user.name", "Preview Fixture"],
        ["git", "config", "user.email", "preview@example.invalid"],
        ["git", "config", "commit.gpgsign", "false"],
        [identity.executable, "init", "--ai", "claude,codex,cursor", "--non-interactive"],
        [identity.executable, "agent", "config", "set", "auto_commit", "false"],
        [identity.executable, "upgrade", "--yes", "--no-worktrees"],
    ):
        result = run_process(args, project, setup_env)
        assert result.returncode == 0, f"Fixture setup failed: {args}\n{result.stdout}\n{result.stderr}"
        setup.append(result)
    env = child_environment(sandbox / "measured")
    home = Path(env["HOME"])
    assert not home.exists(), "Measured home prewarmed during setup"
    if global_state != "G0":
        shutil.copytree(Path(setup_env["HOME"]), home, symlinks=True)
    if global_state == "G1":
        for name in ("version.lock", "agent-skills.lock", "agent-commands.lock"):
            markers = sorted(home.rglob(name))
            assert markers, f"No genuine global marker: {name}"
            for marker in markers:
                assert marker.is_file() and not marker.is_symlink()
                marker.write_text("0.0.0\n")
    return PreviewCase(project, env, identity, tuple(setup))


def copy_case(case: PreviewCase, sandbox: Path) -> PreviewCase:
    """Clone a prepared baseline before either measurement; refuse linked fixtures.

    These canonical G/P baselines contain copies. Symlink experiments need an
    explicit target mapping; refusing them avoids shared writable destinations.
    """
    assert not any(node.kind == "symlink" for node in case.observe().values()), "Copy fixture needs explicit symlink mapping"
    project = sandbox / "project"
    shutil.copytree(case.project, project, symlinks=True)
    env = child_environment(sandbox / "measured")
    if Path(case.env["HOME"]).exists():
        shutil.copytree(Path(case.env["HOME"]), Path(env["HOME"]), symlinks=True)
    return PreviewCase(project, env, case.identity, case.setup)


def degrade_p6(case: PreviewCase) -> tuple[str, ...]:
    """Remove genuine installed family members and supporting manifests only."""
    removed = []
    for relative in (
        ".agents/skills",
        ".claude/agents",
        ".kittify/command-skills-manifest.json",
        ".kittify/skills-manifest.json",
        ".kittify/agent_profiles_manifest.json",
    ):
        path = case.project / relative
        if path.exists():
            removed.append(relative)
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    assert ".agents/skills" in removed and ".claude/agents" in removed
    assert ".kittify/command-skills-manifest.json" in removed
    return tuple(removed)
