import sys, json
from pathlib import Path
from specify_cli.status import get_all_wp_lanes, get_all_wp_snapshots, materialize_snapshot, compute_weighted_progress, reduce, read_event_stream, read_events
from specify_cli.status.read_surface import StatusReadSurface, StatusReadSource, materialize_status
from mission_runtime import MissionTopology
root = Path("kitty-specs")
n=0; diffs=[]
for log in sorted(root.glob("*/status.events.jsonl")):
    d = log.parent; n+=1
    try:
        A = {k: str(v) for k,v in get_all_wp_lanes(d).items()}
        S = get_all_wp_snapshots(d)
        M = materialize_snapshot(d)
        surf = StatusReadSurface(topology=MissionTopology.SINGLE_BRANCH, source=StatusReadSource.WRITE_CHECKOUT, mission_dir_name=d.name, path=d, repo_root=Path.cwd(), ref=None)
        Z = materialize_status(surf)
        T = reduce(read_events(d))
    except Exception as e:
        diffs.append((d.name, "EXC", repr(e)[:200])); continue
    lanes = {"lanes":A, "snap":{k:str(v.get("lane")) for k,v in S.items()}, "matsnap":{k:str(v.get("lane")) for k,v in M.work_packages.items()}, "door":{k:str(v.get("lane")) for k,v in Z.work_packages.items()}, "trans_only":{k:str(v.get("lane")) for k,v in T.work_packages.items()}}
    pct = {k: round(compute_weighted_progress(x).percentage,1) for k,x in (("matsnap",M),("door",Z),("trans_only",T))}
    base = lanes["matsnap"]
    for k,v in lanes.items():
        if v != base: diffs.append((d.name, "lanes", k, {w:(v.get(w), base.get(w)) for w in set(v)|set(base) if v.get(w)!=base.get(w)}))
    if len(set(pct.values()))>1: diffs.append((d.name,"pct",pct))
    # full wp dict compare door vs matsnap
    if dict(Z.work_packages) != dict(M.work_packages):
        ks=[w for w in set(Z.work_packages)|set(M.work_packages) if Z.work_packages.get(w)!=M.work_packages.get(w)]
        fields=set()
        for w in ks:
            a=Z.work_packages.get(w) or {}; b=M.work_packages.get(w) or {}
            fields |= {f for f in set(a)|set(b) if a.get(f)!=b.get(f)}
        diffs.append((d.name,"wpdict door!=matsnap", len(ks), sorted(fields)))
print("missions", n)
for x in diffs: print(x)
