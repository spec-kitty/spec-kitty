import json,sys,collections
sys.path.insert(0,sys.argv[1])
from classify import classify
pop={d['number']:d for d in json.load(open(sys.argv[2]))}
hand={}
for f in ['hand1.txt','hand2.txt','hand3.txt']:
    for l in open(sys.argv[1]+'/'+f):
        if l.strip(): n,c,m,s=l.strip().split('|'); hand[int(n)]=(c,m,s)
print('hand n',len(hand), 'missing', set(json.load(open(sys.argv[3])))-set(hand))
a=collections.Counter(); dis=[]
for n,(c,m,s) in hand.items():
    hc,hm,hs=classify(pop[n])
    lane_h=not c.startswith('NL'); lane_x=not hc.startswith('NL')
    a['binary']+=lane_h==lane_x
    a['code_coarse']+=(c.split(':')[0]==hc.split(':')[0])
    a['code_full']+=(c==hc)
    a['model']+=(m==hm); a['sev']+=(s==hs)
    if lane_h!=lane_x or c.split(':')[0]!=hc.split(':')[0]: dis.append((n,c,hc,pop[n]['title'][:90]))
print({k:f'{v}/{len(hand)}' for k,v in a.items()})
for x in dis: print(x)
# confusion lane
cm=collections.Counter(((not c.startswith('NL')),(not classify(pop[n])[0].startswith('NL'))) for n,(c,m,s) in hand.items())
print(cm)
import csv
with open(sys.argv[1]+'/hand.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['number','cause_code','model','severity'])
    for n,(c,m,s) in hand.items(): w.writerow([n,c,m,s])
