import json,re
rows={json.loads(l)['number']:json.loads(l) for l in open('search.jsonl')}
files=json.load(open('files.json'))
KW=re.compile(r'\blanes?\b|worktree|coord(ination)?\b|consolidat|status[- ]surface|lane[- ]tip|teardown|prune|write[- ]checkout|single_branch|single-branch|rollback|status\.events|lane_head|approval stamp|implement_support|mission branch|\bmerge\b',re.I)
LP=('src/specify_cli/lanes/','src/specify_cli/coordination/','src/specify_cli/workspace/','src/specify_cli/consolidation/','src/specify_cli/policy/lane_tip_recorder.py','src/mission_runtime/')
out=[]
for n,r in sorted(rows.items()):
    t=r['title'];fs=files.get(str(n)) or []
    tk=bool(KW.search(t)); bk=len(KW.findall(r['body'] or '')); fp=sum(1 for f in fs if f.startswith(LP))
    out.append((n,tk,bk,fp,len(fs)))
    if tk or fp: print(n,int(tk),bk,fp,'|',t[:140])
