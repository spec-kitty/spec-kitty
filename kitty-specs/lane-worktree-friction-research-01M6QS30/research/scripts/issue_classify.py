import json,re,sys
R=lambda p:re.compile(p,re.I)
def has(p,t): return bool(re.search(p,t,re.I))
CI=R(r'nightly( suite)? red|red on main|\bci\b|flak|test_|tests?/|pytest|fixture|sonar|ruff|mypy|coverage|shard|workflow file|\.github/')
CHARTER=R(r'charter|doctrine|\bdrg\b|directive|tactic|styleguide|agent[- ]profile|activation|org pack|\bpacks?\b|glossary|mission[- ]step[- ]contract')
HOSTED=R(r'\bsaas\b|hosted|team kitty|zeitgeist|live work|\bsync\b|dashboard|status[- ]api|read api|write api|offline queue|event-router')
UPG=R(r'\bupgrade\b|migration|migrate\b|\binit\b|skills?\b|tool-surfaces|command[- ]skill')
REVIEW=R(r'\breview\b|reject|verdict|arbiter')
DOCS=R(r'\bdocs?\b|readme|adr\b|documentation|agents\.md|claude\.md')
# lane/worktree code rules (ordered)
HT=R(r'lane[- _]tip|LANE_WORK_TIP|DESTROYED_LANE|post-commit|post-rewrite|\.git/hooks|pre-commit hook|hooksPath|recorder hook|\bhooks?\b.*(worktree|lane)')
CG=R(r'approval[- _]stamp|LANE_MOVED_AFTER_APPROVAL|APPROVAL_STAMP|mixed[- ](write-scope )?lane|canceled[- ](wp|content|work)|evidence[- _]window|EVIDENCE_WINDOW|IMPLEMENTATION_MISSING|REVIEW_NOT_INDEPENDENT|OWNERSHIP_UNRESOLVED|closed[- ]world|blob[- ]attribution|attest|reconciliation|terminus|approved[- ](claim|bound|content)|APPROVED_CONTENT|unattributable|owned[- ]file evidence|line attribution|dependency[- ]ref')
SD=R(r'status[- ]surface|COORD_STATUS_SURFACE|status(\.json|\.events\.jsonl)?.{0,60}(diverg|drift|stale|disagree)|(diverg|drift|stale|disagree).{0,60}status|lane[- ]worktree.{0,40}status|status.{0,40}(lane[- ]worktree|from the worktree|in the worktree|wrong (log|checkout|branch))|reads? .{0,30}(root|primary).{0,30}status|ORIGIN_STATUS_STALE|wrong log')
CT=R(r'\bcoord(ination)?\b|teardown|COORD_|strand heal|projection[- ]window|PROJECTION_TEARDOWN|rollback|roll back|--abort|--resume|UNEXPLAINED_BRANCH_MOVE|CAS\b|compare-and-swap|target tip')
UF=R(r'upgrade.{0,80}(worktree|lane)|(worktree|lane)s?.{0,80}upgrade|migration.{0,60}worktrees?|every worktree|all (of )?(the )?worktrees')
WC=R(r'WRITE_CHECKOUT|write checkout|dirty (primary|checkout|tree|worktree)|uncommitted.{0,40}(primary|root|checkout)|occupied|wrong[- ]branch|protected[- ]branch|PROTECTED_BRANCH|commit.{0,30}(to|onto|into) (main|the primary|protected)|single[_ -]branch|owned[- ]checkout|direct_repo|primary checkout')
HC=R(r'(agent|harness|subagent|llm).{0,80}(wrong|which).{0,30}(worktree|checkout|branch|path|directory)|cwd|working directory|from a (linked )?worktree|from (a|the) subdirectory|inside (a|another) (worktree|git checkout)|linked worktree|relative path|edits? (land|went) in|wrong (worktree|checkout|directory)|root checkout instead|instead of the (lane|worktree)')
DP=R(r'(disk|space|gigabyte|\bGB\b|slow|performance|latency|seconds|minutes|hang|timeout).{0,80}(worktree|lane)|(worktree|lane)s?.{0,80}(disk|space|slow|performance|hang)')
WL=R(r'(?<!DIRTY_)worktree|\.worktrees|prune|lanes\.json|MissingLanesError|lane (allocation|branch|creation|computation|manifest)|lane[- ]branch|kitty/mission-.*-lane|\bstale (lane|branch|workspace)|orphan(ed)? (lane|worktree|branch)|context cleanup|resolve_workspace|workspace (resolution|path)|cleaned up|cleanup')
LANECTX=R(r'worktree|lane[- ](branch|worktree|tip|head|manifest|allocation|computation|id)|lanes\.json|\blanes\b.{0,20}(topology|mission)|kitty/mission|coord|coordination|consolidat|merge|teardown|write checkout|single_branch|lanes_with_coord')
DL=R(r'data[- ]loss|silently (lose|lost|drop|discard|delet|overwrit|destroy)|\blost\b|lose[s]? (work|commits?|edits?|events?|data|the)|overwrit|destroy|discards?|truncat|reset --hard|wipe|clobber|deleted? .{0,40}(uncommitted|work|commits?|branch)|stranded|ships? (the )?(rejected|canceled|unreviewed)|unreviewed (code|content)? ?(land|ship)')
WV=R(r'wrong(ly)?|false (green|pass|positive|negative|refus)|passes? (with|silently|vacuous)|exit 0|accepts?|ships?|refuses? (its own|a valid|valid|legitimate|a correct|correct)|misreport|reports? (success|clean|healthy)|silently (pass|accept|succeed)|incorrect|verdict|refus')
FO=R(r'--force|\bforce[sd]?\b|override|--attest|bypass|SPEC_KITTY_[A-Z_]+=|--no-verify|hand[- ]edit|manual(ly)? (edit|fix|repair)|workaround')
NONBUG=R(r'^(epic|\[?adr|tech-debt|refactor|docs?:|\[?docs\]?|chore|feat|feature|design|spike|rfc|proposal|unify|extract|add |route the|mission write api|mission status read api|degod|slice \d|phase \d)|tidy|tech-debt')
CITITLE=R(r'^\[CI\]|red on main|nightly|\btest_\w+|corpus witness|fixture|flaky|\bci\b|pytest|mypy|ruff|sonar')
SDT=R(r'husk|status placement|coordination worktree.{0,10}s? status|wrong log|status[- ]surface|status.{0,30}(diverg|stale)|reads? .{0,40}(from|off) (the )?coord')
LANEWORDS=R(r'worktree|lane[- ](branch|worktree|tip|head|manifest|allocation|id)|lanes\.json|coordination|coord\b|teardown|write checkout|single_branch|consolidat')
NA_T=R(r'^(\[?epic|epic:|\[adr|\[architecture\]|audit |align |adopt |unify |extract |add |route |resolve the |mark |share |remove |document|hardening|reconcile |mission (status|write) (read )?api|tech-debt|refactor|feat|chore|design|spike)|degod|slice \d|phase \d|\bfollow-up\b|squad minor|part of #')
NA_B=R(r'^\s*(part of #|## (why|context|purpose|accepted scope|intent|goal|background|bluf)|\*\*why\*\*|follow-up from|> \*\*blocked by)')
BUG_T=R(r'\bbug\b|fails?\b|refus|crash|red\b|lose|lost|silently|wrong|broken|cannot|can.t|never|missing|false|regression|exit [01]|wedge|corrupt|overwrit|race|hang|deadlock|stale|stuck|blocks?\b|misses|ignores|drops')
DL2=R(r'data[- ]loss|silently (lose|lost|drop|discard|delet|overwrit|destroy)|\blost\b|\bloses?\b|overwrit|destroy|discards?|truncat|reset --hard|wipe|clobber|deletes?\b|vanish|mojibak|corrupt')
FO2=R(r'--force|forces? (an? )?(--)?force|override|--attest|bypass|--lenient|--no-verify|by hand|manual(ly)? (git|edit|repair|fix)|no (tool-mediated|sane|operator) (way|recovery|unblock)|hand-?edit')
WV2=R(r'exit 0|silently|false[- ](green|pass|positive|refus)|fake[- ]green|fail[- ]open|wrong(ly)?|accepts?|reports? (success|clean|healthy|committed)|passes|lands?\b|ships?\b|misfires?|refuses? (its own|a valid|valid|legitimate)|misreport|incorrect|degrad|loses .{0,20}binding|ignores?')
def severity(t,b):
    tl=t; b4=b[:400]
    if NA_T.search(tl) and not BUG_T.search(tl): return 'n/a'
    if NA_B.search(b) and not BUG_T.search(tl): return 'n/a'
    if not BUG_T.search(tl) and not re.search(r'what (goes wrong|happen|fails)|## (symptom|problem|summary|observed|impact)|reproduc',b4,re.I): return 'n/a'
    if DL2.search(tl): return 'data-loss'
    if FO2.search(tl): return 'forced-override'
    if WV2.search(tl): return 'wrong-verdict'
    if DL2.search(b4) and re.search(r'lost|lose|truncat|overwrit|destroy|delet|discard|vanish',b4,re.I): return 'data-loss'
    if FO2.search(b4): return 'forced-override'
    if WV2.search(b4): return 'wrong-verdict'
    return 'wasted-time'
def classify(d):
    t=d['title']; b=(d['body'] or '')[:1500]; tb=t+' \n'+b; labs=d['labels']; L=' '.join(labs)
    code=None
    if CITITLE.search(t) and not re.search(r'worktree|lane worktree|coord',t,re.I): code='SKIP'
    if code is None and SDT.search(t): code='SD'
    # title-first lane rules
    if code is None:
      for c,rx in (('HT',HT),('CG',CG),('SD',SD),('UF',UF),('WC',WC),('HC',HC),('DP',DP),('CT',CT),('WL',WL)):
        if rx.search(t): code=c;break
    if code is None and len(LANEWORDS.findall(b[:800]))>=3 and LANECTX.search(tb) and not (CI.search(t) or HOSTED.search(t) or (CHARTER.search(t) and 'domain:charter' in L)):
        for c,rx in (('HT',HT),('CG',CG),('SD',SD),('UF',UF),('WC',WC),('HC',HC),('CT',CT),('WL',WL)):
            if rx.search(b[:800]) and LANECTX.search(b[:800]): code=c;break
    # NL overrides for strong non-lane titles
    if code=='SKIP': code=None
    if code and (re.search(r'nightly suite red|^Nightly red',t,re.I)): code=None
    if code in ('CT',) and not re.search(r'coord|teardown|consolidat|merge|rollback|--abort|--resume|lane|branch',tb,re.I): code=None
    if code is None:
        if CI.search(t) or 'domain:ci' in L or 'from:ci' in L: area='CI/tests'
        elif HOSTED.search(t) or 'legacy:' in L or 'domain:status-api' in L: area='other(hosted/status-api)'
        elif CHARTER.search(t) or 'domain:charter' in L or 'domain:agent-profiles' in L: area='charter/doctrine'
        elif 'domain:upgrade' in L or 'domain:skills' in L or UPG.search(t): area='upgrade (non-worktree)'
        elif 'domain:review' in L or REVIEW.search(t): area='review'
        elif 'domain:status' in L or re.search(r'status|event|transition|move-task|claim|snapshot',t,re.I): area='status model (non-surface)'
        elif 'domain:docs' in L or DOCS.search(t): area='docs'
        elif 'domain:cli' in L or 'usability' in L: area='CLI UX'
        else: area='other'
        code='NL:'+area
    model={'WL':'worktree','DP':'worktree','UF':'worktree','HC':'worktree','SD':'worktree','HT':'lane-branch','CG':'lane-branch','CT':'coord','WC':'single_branch'}.get(code,'none')
    if code in('SD','HC') and re.search(r'coord',tb,re.I): model='coord'
    if code=='WC' and re.search(r'lane worktree|\.worktrees',tb,re.I): model='worktree'
    sev=severity(t,b)
    return code,model,sev
if __name__=='__main__':
    import csv,os
    pop=json.load(open(sys.argv[1])); out=sys.argv[2]
    hand={}
    if len(sys.argv)>3 and os.path.exists(sys.argv[3]):
        for r in csv.DictReader(open(sys.argv[3])): hand[int(r['number'])]=r
    os.makedirs(os.path.dirname(out),exist_ok=True)
    with open(out,'w',newline='') as f:
        w=csv.writer(f); w.writerow(['number','created','state','labels','title','cause_code','model','severity','method'])
        for d in sorted(pop,key=lambda d:d['number']):
            c,m,s=classify(d); meth='heuristic'
            if d['number'] in hand:
                h=hand[d['number']]; c,m,s=h['cause_code'],h['model'],h['severity']; meth='hand'
            w.writerow([d['number'],d['created_at'][:10],d['state'],';'.join(d['labels']),d['title'],c,m,s,meth])
