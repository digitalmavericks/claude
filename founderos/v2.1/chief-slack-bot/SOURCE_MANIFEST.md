# Frozen Build Inputs

This public manifest identifies the private canonical artifacts used to build the
CHIEF Slack identity pack without copying their contents or machine paths into
the repository.

| Canonical artifact | Bytes | SHA-256 |
|---|---:|---|
| `LAW_CHIEF_SLACK_BOT_SOL_ULTRA_BUILD_2026-07-26.md` | 2,915 | `addc2afce3b7d33761582a3e565e503af7ff6d8f3d90ad289f1cdb784373e064` |
| `LAW_CHIEF_INBOX_ROUTING_2026-07-23.md` | 2,014 | `ca5dfa1fb2f30f1716add06b3142a0d36d694ee1f45b7fcb9d47cc80bd2d88e1` |
| `SCA_BUILD_PLAN_ADDENDUM_CHIEF_RUNTIME_2026-07-23.md` | 2,471 | `b6801dcaa976497019e20acfbcc1d656ec7bfa1a931972be4c28a2d39c65966f` |
| `AGENTS.md` identity-registry snapshot | 19,455 | `fb97641cd0efdabce0fc8b00a990c9f09405d337d24678bde10b461c6a7a91c1` |
| User-supplied Slack thread export | 14,856 | `c0b510ca0cf0474aca282dbb0529ce1b49fab6435e631b44779f6d7042666646` |
| AgentBus assignment `6499607b` | 1,956 | `4060ac76de14851217bb9e7d5296058c599be952de33c9b7235e929d0aa3d6a8` |

Repository base: `digitalmavericks/claude` `main` at
`1e5f42c7cff99d2e93369b01b3816666e66a7f8c`.

The mounted workspace remains canonical. This branch is an install-pack build
surface and cannot amend governance, runtime identity, or inbox law.
