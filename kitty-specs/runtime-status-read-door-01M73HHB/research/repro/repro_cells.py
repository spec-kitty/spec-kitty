import subprocess, shutil, sys, tempfile, json
from pathlib import Path
from mission_runtime import MissionTopology as T
from tests.runtime._next_mission_scaffold import scaffold_coord_software_dev
from tests.runtime._next_mission_scaffold import *  # noqa
def git(*a, cwd): return subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True)
def run(cell):
    tmp = Path(tempfile.mkdtemp()); repo = tmp/"repo"; repo.mkdir()
    slug = f"coord-cell-{cell.lower()}"
    fd, cmd = scaffold_coord_software_dev(repo, slug, T.COORD, wps={"WP01":"planned","WP02":"for_review"})
    coord_root = cmd.parent.parent
    r = git("add","-A",cwd=coord_root); r = git("commit","-m","seed coord log",cwd=coord_root)
    slug = fd.name
    if cell == "EMPTY":
        shutil.rmtree(cmd)
    elif cell == "UNMATERIALIZED":
        git("worktree","remove","--force",str(coord_root),cwd=repo)
    from specify_cli.status.read_surface import resolve_status_read, materialize_status
    from specify_cli.status import compute_weighted_progress
    from mission_runtime import mission_context_for, MissionArtifactKind
    out = {"cell": cell}
    try:
        s = resolve_status_read(repo, slug); snap = materialize_status(s)
        out["door"] = (str(s.source), {k:v.get("lane") for k,v in snap.work_packages.items()}, round(compute_weighted_progress(snap).percentage,1))
    except Exception as e: out["door"] = repr(e)[:150]
    try:
        sd = mission_context_for(repo, slug, tolerate_unmaterialized_coord=True).artifact(MissionArtifactKind.STATUS_STATE).read_dir
        out["ctx_status_dir"] = (str(sd.relative_to(repo)), sd.exists(), (sd/"status.events.jsonl").exists())
    except Exception as e: out["ctx_status_dir"] = repr(e)[:150]
    from runtime.next.runtime_bridge import query_current_state
    from tests.runtime._next_mission_scaffold import analysis_is_current
    try:
        d = query_current_state("pedro", slug, repo, analysis_currency=analysis_is_current)
        out["query"] = (str(d.kind), d.mission_state, d.reason, d.wp_id, d.preview_step, d.progress)
    except Exception as e: out["query"] = repr(e)[:200]
    from runtime.next.runtime_bridge_decision_mapping import _resolve_wp_board_action
    try:
        b = _resolve_wp_board_action(mission_slug=slug, repo_root=repo)
        out["board"] = (b.board_step, b.action, b.wp_id, (b.blocked_reason or "")[:160])
    except Exception as e: out["board"] = repr(e)[:200]
    print(json.dumps(out, default=str, indent=1))
for c in sys.argv[1:]: run(c)
