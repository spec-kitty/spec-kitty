import json, os, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, os.environ.get("SPEC_KITTY_ROOT", "."))  # repository root checkout

MISSION = "001-repro-6632"
from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from tests._support.status_seed import seed_status_event
from typer.testing import CliRunner
from specify_cli.cli.commands.agent import tasks as tasks_module
from specify_cli.cli.commands.agent.tasks import app as tasks_app

tmp = Path(tempfile.mkdtemp())
repo = tmp / "repo"; repo.mkdir()
def git(*a):
    subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)

git("init", "-b", "main")
git("config", "user.email", "r@example.invalid"); git("config", "user.name", "R")
git("config", "commit.gpgsign", "false")
git("commit", "--allow-empty", "-m", "base")
(repo / ".kittify").mkdir()
(repo / ".kittify" / "config.yaml").write_text("auto_commit: true\nprotection:\n  protected_branches: []\n", encoding="utf-8")
feature_dir = repo / "kitty-specs" / MISSION
tasks_dir = feature_dir / "tasks"; tasks_dir.mkdir(parents=True)
planning_sha = subprocess.run(["git","rev-parse","HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
write_lanes_json(feature_dir, LanesManifest(version=1, mission_slug=MISSION, mission_id=f"mission-{MISSION}",
    mission_branch=f"kitty/mission-{MISSION}", target_branch="main",
    lanes=[ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=("src/**",), predicted_surfaces=("core",), depends_on_lanes=(), parallel_group=0)],
    computed_at="2026-01-01T00:00:00Z", computed_from="test", planning_commit_sha=planning_sha))
(feature_dir/"meta.json").write_text(json.dumps({"mission_id":"01"+("A"*24),"mid8":"01AAAAAA","mission_slug":MISSION,"mission_type":"software-dev","status_phase":"1"}, indent=2))
(feature_dir/"tasks.md").write_text("# Tasks\n", encoding="utf-8")
write_frontmatter(tasks_dir/"WP01-core.md", {"work_package_id":"WP01","title":"Core","owned_files":["src/**"],"agent":"reviewer","subtasks":[],"tracker_refs":[],"dependencies":[]}, "# WP01\n\n## Activity Log\n")
git("add", "."); git("commit", "-m", "seed")
from tests.lane_test_utils import commit_lane_implementation
commit_lane_implementation(repo, feature_dir)

def hop(i, frm, to, rr=None):
    seed_status_event(feature_dir, StatusEvent(event_id=f"seed-{i}", mission_slug=MISSION, wp_id="WP01", from_lane=frm, to_lane=to, at=f"2026-01-01T00:00:{i:02d}+00:00", actor="fixture", force=True, execution_mode="worktree", review_result=rr))

for i,(a,b) in enumerate([(Lane.GENESIS,Lane.PLANNED),(Lane.PLANNED,Lane.CLAIMED),(Lane.CLAIMED,Lane.IN_PROGRESS),(Lane.IN_PROGRESS,Lane.FOR_REVIEW),(Lane.FOR_REVIEW,Lane.IN_REVIEW)], start=1):
    hop(i,a,b)

import os
os.chdir(repo)
tasks_module.locate_project_root = lambda: repo
tasks_module.get_mission_type = lambda *_a, **_k: "software-dev"

feedback = tasks_dir / "WP01-core" / "review-feedback-1.md"
feedback.parent.mkdir(parents=True, exist_ok=True)
feedback.write_text("**Issue 1**: fix the off-by-one.\n", encoding="utf-8")

r = CliRunner().invoke(tasks_app, ["move-task","WP01","--to","planned","--review-feedback-file",str(feedback),"--mission",MISSION,"--agent","reviewer"])
print("REJECT exit:", r.exit_code)
print(r.output[-3000:])
print("git status kitty-specs:")
print(subprocess.run(["git","status","--porcelain","kitty-specs/"], cwd=repo, capture_output=True, text=True).stdout)

# implementer fixes + commits on lane branch, then returns to for_review
for i,(a,b) in enumerate([(Lane.PLANNED,Lane.CLAIMED),(Lane.CLAIMED,Lane.IN_PROGRESS)], start=10):
    hop(i,a,b)
r2 = CliRunner().invoke(tasks_app, ["move-task","WP01","--to","for_review","--mission",MISSION,"--agent","reviewer"])
print("FOR_REVIEW exit:", r2.exit_code)
print(r2.output[-3000:])
print("REPO:", repo)
