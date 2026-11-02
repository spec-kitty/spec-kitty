# No new contract

This Mission changes no wire contract: it fixes the repository root a contract *check* reads.

The contract under check is the pinned, bundled `mission-status` OpenAPI document of
`spec-kitty-events` (`pins/read-service.source.yaml`, fetched by `make sync-services`), and it is
unmodified. See [#6966](https://github.com/spec-kitty/spec-kitty/issues/6966) and PR #7095.
