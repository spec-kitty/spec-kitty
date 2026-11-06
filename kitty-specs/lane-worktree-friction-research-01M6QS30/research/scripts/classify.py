import json,re,sys,collections,pathlib
T=pathlib.Path(sys.argv[1]); w=json.load(open(T/'win.json'))
I=re.I
def R(p): return re.compile(p,I)
VENV=R(r'(lane |linked |scratch )?worktree[^.]{0,120}(\.venv|venv|packs/|packs tree|sync-packs|interpreter|PYTHONPATH|editable|imports? (the )?(root|primary|main)|BuiltInPackMissing)|(\.venv|venv|interpreter|PYTHONPATH|editable install|sync-packs|BuiltInPackMissing)[^.]{0,120}(lane|worktree)|\.pth\b')
RULES=[
 ('HT',R(r'lane[-_ ]tip|DESTROYED_LANE|LANE_WORK_TIP|hooksPath|post-(commit|rewrite) hook|tip recorder|recorder hook')),
 ('WL',VENV),
 ('UF',R(r'(upgrade|migration|migrate)\b[^.]{0,100}(worktrees|lane worktree)|(worktrees|lane worktree)[^.]{0,100}\b(upgrade|migrat)')),
 ('CG',R(r'LANE_MOVED_AFTER_APPROVAL|APPROVAL_STAMP|approval stamp|approved[- ]bound|approved claim|mixed[- ]lane|closed[- ]world|IMPLEMENTATION_MISSING|EVIDENCE_WINDOW|evidence window|reconciliation (refus|gate|fail)|squash reconciliation|APPROVED_CONTENT_MISSING|CANCELED_(CONTENT|REACHABLE)|UNEXPLAINED_BRANCH_MOVE|ORIGIN_LANE|attest-approved|attest-no-implementation|lane (has )?moved|stale[- ]lane')),
 ('SD',R(r'COORD_STATUS_SURFACE|status[^.]{0,80}(diverg|stale|out of sync|mismatch|disagree)[^.]{0,80}(worktree|coord|lane|primary|root)|(worktree|coord|lane)[^.]{0,80}status[^.]{0,60}(diverg|stale|out of sync|mismatch|disagree)|status (events?|files?)[^.]{0,80}(coord(ination)? worktree|lane worktree)|review-cycle[^.]{0,60}primary[^.]{0,80}coord')),
 ('CT',R(r'coord(ination)?[ _-]?(branch|worktree|topology|surface|ref|strand|base|seed|partition|kind|commit|log|bookkeeping|copy|copies|mission)|teardown|PROJECTION_|projection|CoordinationWorktree|lanes_with_coord|\bcoord\b')),
 ('WC',R(r'WRITE_CHECKOUT|single[_ -]branch|write checkout|dirty (working tree|checkout|tree)|index\.lock|wrong branch|owned[- ]checkout')),
 ('WL',R(r'worktree[^.]{0,100}(prune|stale|remov|clean|leftover|reus|exist|recreat|delet|orphan|creat|missing|left behind)|(prune|stale|remov|clean|leftover|recreat|delet|orphan)[^.]{0,60}worktree|\.worktrees/|lanes\.json|lane (alloc|creation|branch|merge(?!-base)|rebase|computation|graph)|allocate_lane|depends_on_lanes|dependency lane|planning commit|lane-planning|LANE_[A-Z]|auto-merge|sparse checkout|git stash[^.]{0,80}worktree|worktree[^.]{0,80}git stash')),
 ('HC',R(r'repo(sitory)?[- ]root (checkout)?|root checkout|primary checkout|main checkout|wrong (worktree|checkout)|which checkout|lane root|linked worktree|from (a|the) (lane )?worktree|in (a|the) lane( worktree)?|lane worktree|primary clone|from a lane')),
]
NLAREA=[('claim-base/for_review gate',R(r'claim base|wp-base|no implementation commit since claim')),('tests/CI',R(r'pytest|\btests?\b|\bCI\b|flak|nightly|xdist|baseline|red on')),('review process',R(r'review|reviewer|verdict|issue-matrix|approval')),('planning/tasks',R(r'finalize-tasks|wps\.yaml|tasks|specify|setup-plan|\bplan\b|spec-commit|decision|analy[sz]')),('charter/doctrine/packs',R(r'charter|doctrine|\bpacks?\b|DRG|directive|glossary|skill')),('gates/arch',R(r'gate|allowlist|architectural|ruff|mypy')),('host/env/install',R(r'load average|contention|timeout|timed out|PATH|install|\buv\b|container|host|cache|gpg|sign')),('docs',R(r'docs?\b|markdown'))]
DL=R(r'\blost\b(?! time)|\bloses? (work|data|edits|commits|the)|data[- ]loss(?! guard)|wiped|clobber|overwr(o|i)te|destroyed|reverted each other|revert(s|ed)? (each|the other|another)|silently discard|discarded (unrelated|work|edits)|swept')
NODL=R(r'no data loss')
WV=R(r'false (red|green|pass|positive|negative)|false(ly)? report|for the wrong reason|wrong (verdict|code|src)|silently pass|vacuous|import(s|ed)? (the )?(root|primary|main)[^.]{0,30}src|resolves the MAIN|not evidence|passable by a no-op|\binert\b|tests? (would )?pass(ed)? (against|for) ')
FO=R(r'--force\b|\bforced\b|SPEC_KITTY_SKIP|--skip-|bypass|by hand|hand[- ]edit|hand-written|manual(ly)?|git (reset|stash|update-ref|branch -D|worktree (remove|add)|checkout|rebase|merge|commit|cherry-pick|push)|raw git|--no-verify|symlink|re-?creat(ed|ing) (the )?(mission|scaffold|lane|worktree)|removed the scaffold|recreated|override')
rows=[]
for e in w:
    t=e['text']; cause='NL'
    for c,p in RULES:
        if p.search(t): cause=c; break
    area=''
    if cause=='NL':
        area='other'
        for a,p in NLAREA:
            if p.search(t): area=a; break
    if cause=='NL': model='none'
    elif re.search(r'single[_ -]branch|owned[- ]checkout',t,I): model='single_branch'
    elif cause in('CT',) or re.search(r'\bcoord',t,I): model='coord'
    elif re.search(r'worktree|checkout|\.venv|\.pth|lane root',t,I): model='worktree'
    else: model='lane-branch'
    if DL.search(t) and not NODL.search(t): sev='data-loss'
    elif WV.search(t): sev='wrong-verdict'
    elif FO.search(t): sev='forced-override'
    else: sev='wasted-time'
    body=re.sub(r'^[-*\s]*(\*\*)?\[?(20\d\d-\d\d-\d\d)\]?(\[[^\]]*\])*\s*(·[^·]*·\s*)?(20\d\d-\d\d-\d\d\s*(·[^·]*·)?)?\s*[—:–-]*\s*','',t)
    body=body.replace('**','').replace('`','')
    summ=' '.join(body.split()[:20])
    q=body[:150].replace('\n',' ')
    rows.append(dict(source_path=e['path'],date=e['date'],entry_summary=summ,cause_code=cause+(f' ({area})' if area else ''),model=model,severity=sev,quote_or_line_ref=f"{e['path']}:{e['line']} \"{q}\"",dsrc=e['dsrc']))
json.dump(rows,open(T/'rows.json','w'))
C=collections.Counter
print(len(rows)); print(C(r['cause_code'].split()[0] for r in rows).most_common())
print(C(r['model'] for r in rows).most_common()); print(C(r['severity'] for r in rows).most_common())
print(C(r['cause_code'] for r in rows if r['cause_code'].startswith('NL')).most_common())
lw=[r for r in rows if not r['cause_code'].startswith('NL')]
print('lane share',len(lw),len(lw)/len(rows)); print('lane sev',C(r['severity'] for r in lw).most_common()); print('NL sev',C(r['severity'] for r in rows if r['cause_code'].startswith('NL')).most_common())
# per-mission share
pm=collections.defaultdict(lambda:[0,0])
for r in rows: pm[r['source_path']][0]+=1; pm[r['source_path']][1]+= not r['cause_code'].startswith('NL')
print('files',len(pm),'files with >=1 lane entry',sum(1 for v in pm.values() if v[1]),'files majority lane',sum(1 for v in pm.values() if v[1]*2>v[0]))
