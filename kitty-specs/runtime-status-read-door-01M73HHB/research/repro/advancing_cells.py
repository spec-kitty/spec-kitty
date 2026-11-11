"""Run the real CLI `spec-kitty next` (advancing and query) on the #7507 cells."""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
from mission_runtime import MissionTopology as T
from tests.runtime._next_mission_scaffold import scaffold_coord_software_dev

CLI = str(Path(sys.argv[1]))

def git(*a, cwd):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True)

def next_json(repo, slug, advancing):
    args = [CLI, "next", "--agent", "probe", "--mission", slug, "--json"]
    if advancing:
        args += ["--result", "success"]
    p = subprocess.run(args, cwd=repo, capture_output=True, text=True, env={**os.environ, "SPEC_KITTY_NON_INTERACTIVE": "1"})
    try:
        d = json.loads(p.stdout)
    except Exception:
        return {"exit": p.returncode, "raw": (p.stdout + p.stderr)[-300:]}
    return {"exit": p.returncode, "kind": d.get("kind"), "state": d.get("mission_state"), "wp": d.get("wp_id"),
            "action": d.get("action"), "reason": (d.get("reason") or "")[:110], "weighted": (d.get("progress") or {}).get("weighted_percentage")}

for cell in sys.argv[2:]:
    for advancing in (False, True):
        repo = Path(tempfile.mkdtemp()) / "repo"; repo.mkdir()
        fd, cmd = scaffold_coord_software_dev(repo, f"cell-{cell.lower()}", T.COORD, wps={"WP01": "planned", "WP02": "for_review"})
        coord_root = cmd.parent.parent
        git("add", "-A", cwd=coord_root); git("commit", "-qm", "seed", cwd=coord_root)
        if cell == "EMPTY":
            shutil.rmtree(cmd)
        elif cell == "UNMATERIALIZED":
            git("worktree", "remove", "--force", str(coord_root), cwd=repo)
        res = next_json(repo, fd.name, advancing)
        after = "materialized" if (cmd / "status.events.jsonl").exists() else ("absent-worktree" if not coord_root.exists() else "empty")
        print(cell, "advancing" if advancing else "query", res, "coord_after:", after)
