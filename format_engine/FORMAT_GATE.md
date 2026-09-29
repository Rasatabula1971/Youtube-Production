# Human Format Gate

A deterministically valid format plan is a candidate, not a production order.

The gate exists because the expensive mistake at this stage is not a schema error. It is
planning one timeline and calling it two formats, or planning a branch that no longer
delivers the promise the Packaging Gate approved.

## Accept criteria

Every criterion in `format_gate_config.json` must be affirmed for `ACCEPT`:

- `branches_are_separate_productions` — each branch is planned in its own shape rather
  than as the same timeline re-cut or truncated.
- `promise_preserved_per_branch` — every branch still delivers the approved package
  promise and expected payoff for its own viewing context.
- `facts_within_accepted_claims` — factual beats stay within human-accepted research
  claims.
- `duration_intent_realistic` — the stated duration intent is achievable for the
  planned beats.
- `producible_from_available_material` — the plan can actually be produced from
  material the project can create or lawfully obtain.

## Decisions

| Decision | Result status                | Effect                                            |
| -------- | ---------------------------- | ------------------------------------------------- |
| `ACCEPT` | `READY_FOR_PRODUCTION_ENGINE` | Writes an approved format plan with provenance.   |
| `REWORK` | `FORMAT_REWORK_REQUIRED`      | Requires a note. Revokes any prior approval.      |
| `REJECT` | `FORMAT_REJECTED`             | Revokes any prior approval.                       |

`ACCEPT` requires every configured criterion to be true. `REWORK` requires a note.

## Staleness

Each review request is bound to the SHA-256 of the exact format plan it was prepared
from. If the plan changes after preparation, applying the decision fails with
`STALE_REVIEW_REQUEST` rather than approving material a human did not read.

The deterministic separation evidence (`branch_separation`), per-branch claim usage and
source-overlap report are carried into the review request so the reviewer sees what the
machine already checked.
