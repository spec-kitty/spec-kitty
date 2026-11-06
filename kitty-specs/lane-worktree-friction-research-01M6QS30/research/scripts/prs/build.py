import json,csv,collections
rows={json.loads(l)['number']:json.loads(l) for l in open('search.jsonl')}
cls={int(a):(b,c) for a,b,c in (l.split() for l in open('cls.txt') if l.strip())}
assert all(n in rows for n in cls)
out='/home/user/spec-kitty/kitty-specs/lane-worktree-friction-research-01M6QS30/research/pr-classification.csv'
import os;os.makedirs(os.path.dirname(out),exist_ok=True)
agg=collections.defaultdict(lambda:[0,0]);fam=collections.defaultdict(lambda:[0,0]);mod=collections.defaultdict(lambda:[0,0])
T=[0,0]
with open(out,'w',newline='') as f:
    w=csv.writer(f);w.writerow(['number','merged','title','cause_code','model','additions','deletions'])
    for n,r in sorted(rows.items()):
        p=json.load(open(f'pr/{n}.json'));cc,m=cls.get(n,('NONLANE','none'))
        w.writerow([n,r['merged'][:10],r['title'],cc,m,p['additions'],p['deletions']])
        ch=p['additions']+p['deletions'];T[0]+=1;T[1]+=ch
        k=cc.split(':')[0];agg[k][0]+=1;agg[k][1]+=ch
        if cc.startswith('NL'):fam[cc][0]+=1;fam[cc][1]+=ch
        mod[m][0]+=1;mod[m][1]+=ch
print('TOTAL',T)
for k,(c,ch) in sorted(agg.items(),key=lambda x:-x[1][1]): print(f"{k:8} PRs {c:4} churn {ch:8} {ch/T[1]:.1%}")
lane=sum(v[1] for k,v in agg.items() if k!='NONLANE');lc=sum(v[0] for k,v in agg.items() if k!='NONLANE')
print('LANE total PRs',lc,f"{lc/T[0]:.1%}",'churn',lane,f"{lane/T[1]:.1%}")
print(dict(fam));print(dict(mod))
# median-ish: excluding top 5% biggest PRs
chs=sorted(((json.load(open(f'pr/{n}.json'))['additions']+json.load(open(f'pr/{n}.json'))['deletions']),n) for n in rows)
cap=chs[int(len(chs)*0.95)][0];print('p95 cap',cap)
tl=sum(min(c,cap) for c,n in chs);ll=sum(min(c,cap) for c,n in chs if n in cls);print('capped lane share',f"{ll/tl:.1%}")
import statistics;print('median churn lane',statistics.median([c for c,n in chs if n in cls]),'nonlane',statistics.median([c for c,n in chs if n not in cls]))
