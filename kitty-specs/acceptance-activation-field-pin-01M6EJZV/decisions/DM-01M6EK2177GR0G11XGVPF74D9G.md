# Decision Moment `01M6EK2177GR0G11XGVPF74D9G`

- **Mission:** `acceptance-activation-field-pin-01M6EJZV`
- **Origin flow:** `specify`
- **Slot key:** `specify.pin.which-side`
- **Input key:** `pin_which_side`
- **Status:** `resolved`
- **Created:** `2026-11-02T16:56:37.863479+00:00`
- **Resolved:** `2026-11-02T16:56:43.308423+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The acceptance test pins 10 activation fields and CharterYaml declares 13. Is the test stale or is the model wrong?

## Options

- The test is stale: derive from the vocabulary authority
- The model is wrong: remove three fields
- Pin the intended count with a rationale

## Final answer

The test is stale and the model is right. CharterYaml's 13 activation fields are intentional: #6556 added activated_glossary_packs, activated_skills and activated_anti_patterns because the activation writer writes them to charter.yaml, ACTIVATION_YAML_KEYS (the single vocabulary authority) holds exactly 13, and the model-vs-authority parity gate is green. The test's hard-coded len(...) == 10 was true at #6496 when the model had ten and went stale; it also derived its names from the model, so it could never detect a wrong key set. Fix: take the field set from pack_manager.ACTIVATION_YAML_KEYS, keep the behavioural model_validate + real-CLI proof, add a non-vacuity guard, and rename the test.

## Rationale

_(none)_

## Change log

- `2026-11-02T16:56:37.863479+00:00` — opened
- `2026-11-02T16:56:43.308423+00:00` — resolved (final_answer="The test is stale and the model is right. CharterYaml's 13 activation fields are intentional: #6556 added activated_glossary_packs, activated_skills and activated_anti_patterns because the activation writer writes them to charter.yaml, ACTIVATION_YAML_KEYS (the single vocabulary authority) holds exactly 13, and the model-vs-authority parity gate is green. The test's hard-coded len(...) == 10 was true at #6496 when the model had ten and went stale; it also derived its names from the model, so it could never detect a wrong key set. Fix: take the field set from pack_manager.ACTIVATION_YAML_KEYS, keep the behavioural model_validate + real-CLI proof, add a non-vacuity guard, and rename the test.")
