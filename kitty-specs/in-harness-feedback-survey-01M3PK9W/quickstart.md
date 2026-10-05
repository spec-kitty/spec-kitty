# Quickstart: In-Harness Feedback Survey

How to exercise the feature end to end once it is implemented. It uses a local loopback endpoint so nothing leaves the machine.

## 1. Start a throwaway local endpoint

```bash
python3 -c '
import http.server, json
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        print(json.dumps(json.loads(body), indent=2), flush=True)
        self.send_response(204); self.end_headers()
http.server.HTTPServer(("127.0.0.1", 8765), H).serve_forever()'
```

## 2. Point Spec Kitty at it and inspect the settings

```bash
export SPEC_KITTY_FEEDBACK_URL=http://127.0.0.1:8765/feedback   # loopback http is allowed; anything else must be https
spec-kitty feedback --status
```

Expected: the effective destination, the list of fields a submission contains, the last-shown date (`never`), and `automatic prompts: on`.

## 3. Give feedback on demand (terminal)

```bash
spec-kitty feedback
```

Answer the rating (1–5), optionally a comment and an email, then confirm **Send feedback?**. The local endpoint prints exactly one JSON body that matches `contracts/feedback-submission.schema.json` with `"trigger": "on_demand"` and `"harness": "cli"`. With the email left blank, there is no `email` key.

## 4. Agent protocol (what a harness does at a trigger)

```bash
spec-kitty feedback --agent-check --trigger mission_end --agent cursor --json
# -> {"action": "prompt", "reason": "eligible", ...}   (the offer is now recorded as shown)

spec-kitty feedback --agent-submit --trigger mission_end --agent cursor \
  --rating 4 --comment "Faster planning, please" --consent yes --json
# -> {"status": "handed_off", "message": "Thanks for your feedback."}

spec-kitty feedback --agent-check --trigger op_close --agent cursor --json
# -> {"action": "none", "reason": "throttled", ...}    (weekly limit)
```

## 5. Controls

```bash
spec-kitty feedback --prompts off   # same effect as choosing "don't ask again"
spec-kitty feedback --prompts on
```

## 6. Silent failure check

Stop the local endpoint and repeat step 3 or 4. Control returns immediately, the same thank-you appears, there is no error output, and the exit status is 0.

## 7. Dormant check

```bash
unset SPEC_KITTY_FEEDBACK_URL
spec-kitty feedback --agent-check --trigger mission_end --agent cursor --json
# -> {"action": "none", "reason": "no_endpoint", ...}   (upstream build ships no default endpoint)
spec-kitty feedback
# -> explains that no feedback endpoint is configured; asks nothing
```

Preferences live in the per-user config directory (`feedback.json`). Delete that file to reset the weekly window during testing.
