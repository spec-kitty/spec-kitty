import re,sys,json,pathlib,collections
T=pathlib.Path(sys.argv[1]); out=[]
DATE=re.compile(r'20\d\d-\d\d-\d\d')
BOIL=re.compile(r'^(-\s*)?(Tooling (touched|this mission)|Append|Seeded|Format:|Context|Friction notes|One entry|\(Append|Mission tooling|Filed:|Worth filing|Log every|>\s)',re.I)
for p in open(T/'tf.txt').read().split():
    lines=re.sub(r'<!--.*?-->',lambda m:'\n'*m.group(0).count('\n'),open(p,encoding='utf-8').read(),flags=re.S).splitlines()
    start=0
    for i,l in enumerate(lines):
        if re.match(r'^#+\s*Entries',l) or l.strip()=='---': start=i+1; break
    ents=[];cur=None
    for i,l in enumerate(lines[start:],start+1):
        s=l.strip()
        if l.startswith('Example:'): continue
        new = re.match(r'^(- |\* |\d+\. )',l) or re.match(r'^\**\[?20\d\d-\d\d-\d\d',s) or re.match(r'^#{2,4}\s',l)
        if not s:
            if cur: ents.append(cur); cur=None
            continue
        if new or cur is None:
            if cur: ents.append(cur)
            cur=[i,s]
        else: cur[1]+=' '+s
    if cur: ents.append(cur)
    try: md=json.load(open(pathlib.Path(p).parents[1]/'meta.json')).get('created_at','')[:10]
    except Exception: md=''
    for ln,e in ents:
        if re.match(r'^#{1,4}\s',e) or re.match(r'^(-\s*)?None( yet)?\b',e) or len(e)<25 or BOIL.match(e): continue
        m=DATE.search(e[:60]); d=m.group(0) if m else md
        out.append(dict(path=p,line=ln,date=d,dsrc='entry' if m else 'meta',text=e))
w=[e for e in out if '2026-08-06'<=e['date']<='2026-11-06']
json.dump(w,open(T/'win.json','w'))
print('all',len(out),'window',len(w),'files',len({e['path'] for e in w}),'meta-dated',sum(e['dsrc']=='meta' for e in w))
print(sorted(collections.Counter(e['date'][:7] for e in w).items()))
