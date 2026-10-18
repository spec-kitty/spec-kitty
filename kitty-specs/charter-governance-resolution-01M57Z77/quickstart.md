# Quickstart: verifying the Mission

```bash
# #6404: synthesized tactics reach context through their directive
spec-kitty charter synthesize
spec-kitty charter context --action implement --mission-type software-dev --json --no-mark-loaded | jq '.tactics'

# #6406 / #6407: declared ids and org selections (org pack declaring QA_003 in qa-003-no-fake-green.directive.yaml)
spec-kitty charter activate directive qa-003-no-fake-green
spec-kitty charter context --action plan --mission-type software-dev --no-mark-loaded   # lists QA_003
spec-kitty charter context --include directive:QA_003 --no-mark-loaded

# #6408: narrow activation
spec-kitty charter activate toolguide gherkin --only
spec-kitty charter interview --defaults --narrow-activation --selected-directives DIRECTIVE_001 --json

# #6405: stack detection
spec-kitty charter status --json | jq '.synthesis.evidence.code'
```
