import re,collections,sys
FIX=re.compile(r'fix|bug|regress|refus|guard|race|stale|leak|prune|teardown',re.I)
areas={'lanes':'src/specify_cli/lanes/','coordination':'src/specify_cli/coordination/','workspace':'src/specify_cli/workspace/','consolidation':'src/specify_cli/consolidation/','lane_tip_recorder':'src/specify_cli/policy/lane_tip_recorder.py','mission_runtime':'src/mission_runtime/','status':'src/specify_cli/status/','upgrade':'src/specify_cli/upgrade/'}
commits=[];cur=None
for l in open(sys.argv[1]):
    l=l.rstrip('\n')
    if l.startswith('@@'):
        h,s=l[2:].split('\t',1);cur=[h,s,[]];commits.append(cur)
    elif l and cur: cur[2].append(l)
N=len(commits);F=sum(1 for c in commits if FIX.search(c[1]))
print(f"total non-merge commits {N}, fix {F} ({F/N:.1%})")
src=[c for c in commits if any(p.startswith('src/') for p in c[2])]
fs=sum(1 for c in src if FIX.search(c[1]));print(f"commits touching src/ {len(src)}, fix {fs} ({fs/len(src):.1%})")
union=set()
for a,p in areas.items():
    cs=[c for c in commits if any(f.startswith(p) for f in c[2])]
    f=sum(1 for c in cs if FIX.search(c[1]))
    union|={c[0] for c in cs}
    print(f"{a:18} commits {len(cs):5} fix {f:5} share {f/max(1,len(cs)):.1%}")
lw=['lanes','coordination','workspace','consolidation','lane_tip_recorder','mission_runtime']
cs=[c for c in commits if any(f.startswith(areas[a]) for a in lw for f in c[2])]
f=sum(1 for c in cs if FIX.search(c[1]));print(f"LANE-MODEL union(lanes,coord,ws,consol,tip,mission_runtime) {len(cs)} fix {f} {f/len(cs):.1%}")
cs=[c for c in commits if c[0] in union];f=sum(1 for c in cs if FIX.search(c[1]));print(f"ALL8 union {len(cs)} fix {f} {f/len(cs):.1%}")
rest=[c for c in src if c[0] not in union];f=sum(1 for c in rest if FIX.search(c[1]));print(f"src commits outside 8 areas {len(rest)} fix {f} {f/len(rest):.1%}")
fc=collections.Counter();ff=collections.Counter()
for c in commits:
    for p in set(c[2]):
        if p.startswith(('src/','tests/')) or True:
            fc[p]+=1
            if FIX.search(c[1]): ff[p]+=1
def top(cn,filt):
    return [(p,n) for p,n in cn.most_common() if filt(p)][:15]
for lab,filt in [('all files',lambda p:True),('src only',lambda p:p.startswith('src/'))]:
    print('\nTOP by commits',lab);[print(f"  {n:4} fix {ff[p]:4} {p}") for p,n in top(fc,filt)]
    print('TOP by fix commits',lab);[print(f"  {n:4} of {fc[p]:4} {p}") for p,n in top(ff,filt)]
