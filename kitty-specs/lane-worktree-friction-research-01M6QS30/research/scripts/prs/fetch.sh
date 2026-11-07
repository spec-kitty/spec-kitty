d=2026-08-06
: > search.jsonl
while [ "$d" \< 2026-11-07 ]; do
  e=$(date -d "$d +6 days" +%F)
  n=$(gh api -X GET search/issues -f q="repo:spec-kitty/spec-kitty is:pull-request is:merged merged:$d..$e" -f per_page=1 --jq .total_count)
  echo "$d..$e $n" >&2
  p=1; while [ $(( (p-1)*100 )) -lt $n ]; do
    gh api -X GET search/issues -f q="repo:spec-kitty/spec-kitty is:pull-request is:merged merged:$d..$e" -f per_page=100 -f page=$p --jq '.items[]|{number,title,labels:[.labels[].name],merged:.pull_request.merged_at,body:((.body//"")[:1500])}' >> search.jsonl
    p=$((p+1)); done
  d=$(date -d "$d +7 days" +%F)
done
