# Decision Moment `01M5BV5F2GCC1ZQW0466TD6MY2`

- **Mission:** `persistent-deactivation-ledger-01M59YAA`
- **Origin flow:** `plan`
- **Slot key:** `plan.contract.document_scope`
- **Input key:** `contract_document_scope`
- **Status:** `resolved`
- **Created:** `2026-10-20T05:04:53.840798+00:00`
- **Resolved:** `2026-10-20T05:04:58.528000+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

Should activation.yaml hold the full charter-contract ActivationConfig (packs, languages, contextActivations, appliedPresets)?

## Options

_(none)_

## Final answer

No. Those stay where they are; the proxy/API/ACL seam maps current homes onto the contract's schema object before passing them to the activation module. What matters is content alignment: shapes may be aggregated or mapped as long as the representations are compatible.

## Rationale

_(none)_

## Change log

- `2026-10-20T05:04:53.840798+00:00` — opened
- `2026-10-20T05:04:58.528000+00:00` — resolved (final_answer="No. Those stay where they are; the proxy/API/ACL seam maps current homes onto the contract's schema object before passing them to the activation module. What matters is content alignment: shapes may be aggregated or mapped as long as the representations are compatible.")
