"""Repro for #6844: managed lane misclassified when primary is on a branch without its kitty-specs."""
import json, subprocess, sys, tempfile
from pathlib import Path

from specify_cli.coordination import register_lane_sparse_checkout
from specify_cli.git.sparse_checkout import scan_repo

SLUG = "mission-a-01J6XW9K"
MID8 = "01J6XW9K"
COORD = f"kitty/mission-{SLUG}"

def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True)
    if r.returncode != 0:
        print("FAILED:", cmd, r.stdout, r.stderr); sys.exit(1)
    return r

root = Path(tempfile.mkdtemp()) / "repo"
root.mkdir(parents=True)
run(["git", "init", "-q", "-b", "main", str(root)])
run(["git", "-C", str(root), "config", "user.email", "t@e.com"])
run(["git", "-C", str(root), "config", "user.name", "T"])
run(["git", "-C", str(root), "config", "commit.gpgsign", "false"])
(root / "README.md").write_text("hello\n")
(root / ".kittify").mkdir()
run(["git", "-C", str(root), "add", "-A"])
run(["git", "-C", str(root), "commit", "-m", "init"])
# branch B without mission A's kitty-specs
run(["git", "-C", str(root), "branch", "b-branch"])

# seed mission A on main
sd = root / "kitty-specs" / SLUG
sd.mkdir(parents=True)
(sd / "spec.md").write_text("# spec\n")
(sd / "status.events.jsonl").write_text("{}\n")
(sd / "status.json").write_text("{}\n")
(sd / "meta.json").write_text(json.dumps({"mission_slug": SLUG, "mission_id": MID8 + "ABCDEFGHJKMNPQRSTVW", "coordination_branch": COORD}))
run(["git", "-C", str(root), "add", "-A"])
run(["git", "-C", str(root), "commit", "-m", "mission A"])
run(["git", "-C", str(root), "branch", COORD])
ex = root / ".git" / "info" / "exclude"
ex.write_text(ex.read_text() + ".worktrees/\n")
lane = root / ".worktrees" / f"{SLUG}-lane-a"
run(["git", "-C", str(root), "worktree", "add", "-b", f"{COORD}-lane-a", str(lane), COORD])
register_lane_sparse_checkout(lane, SLUG, MID8)

print("== primary on main (has mission A's kitty-specs) ==")
rep = scan_repo(root)
print("  worktrees:", [(w.path.name, w.sparse_checkout_kind.value, w.is_blocking) for w in rep.worktrees])
print("  any_blocking:", rep.any_blocking)

print("== switch primary to b-branch (no mission A kitty-specs) ==")
run(["git", "-C", str(root), "checkout", "-q", "b-branch"])
print("  kitty-specs present:", (root / "kitty-specs").exists())
rep = scan_repo(root)
print("  worktrees:", [(w.path.name, w.sparse_checkout_kind.value, w.is_blocking) for w in rep.worktrees])
print("  any_blocking:", rep.any_blocking, " affected:", rep.affected_paths)
sys.exit(0 if rep.any_blocking else 2)
