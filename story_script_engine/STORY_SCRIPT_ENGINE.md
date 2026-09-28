# Story / Script Engine

Flow:

**Prepare Script Requests → Generate Script Drafts → Human Script Gate → Ready for Production**

The engine consumes only `research_engine/output/verified_packages/*` packages whose status is
`READY_FOR_STORY_SCRIPT`.

## Hard boundaries

- The approved package promise is carried into the script request.
- Only Research Gate accepted claims are available as factual support.
- Every factual script section references approved `claim_id` values.
- Unknown claim IDs fail deterministic validation.
- Source-video wording, story, personality, footage and exact execution are not inputs for copying.
- FAIR remains free-only through the shared YouTube bridge.
- A model-validated draft is not production-ready until the Human Script Gate accepts it.

The Human Script Gate checks promise delivery, factual scope, claim mapping, originality/source
independence and story/payoff clarity. ACCEPT produces an approved script artifact with provenance.
