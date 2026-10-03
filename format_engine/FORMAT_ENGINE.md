# Format Engine

Stage 06 of the system map.

Flow:

**Prepare Format Requests → Generate Format Plans → Human Format Gate → Ready for Production Engine**

The engine consumes only `story_script_engine/output/approved_scripts/*` artifacts whose
`script_gate.status` is `READY_FOR_PRODUCTION`.

## Why this stage exists

Long-form and Shorts already arrive here as **separately written and
Human-Script-Gate-approved narrations**. The Format Engine no longer decides how
one master narration should become two formats.

Its job is production planning around each immutable branch script:

- scene and beat structure;
- visual treatment and proof;
- duration intent;
- aspect ratio;
- source-section traceability;
- production pacing and producibility.

The branches still share research, accepted facts, the package promise and the
shared upstream Story Plan, but their narration is already format-specific.

## Branch resolution

The approved concept `format_intent` decides which branches must be planned:

| `format_intent` | Required branches         |
| --------------- | ------------------------- |
| `long_form`     | `long_form`               |
| `short`         | `short`                   |
| `either`        | `long_form` **and** `short` |

An unknown `format_intent` fails deterministic validation rather than defaulting to a
branch. Branch duration bounds, beat minimums and aspect ratios live in
`format_config.json`; they are configurable project constraints, not proven rules.

## Hard boundaries

- Only a complete approved script bundle enters format planning.
- Each production branch may reference only section IDs from its matching
  approved script branch.
- Format planning may not rewrite, paraphrase, shorten, combine or substitute
  approved narration.
- Only Research Gate accepted claims are available as factual support.
- Every beat carrying factual material references approved `claim_id` values.
- Every beat traces to the approved script `section_id` values it is built from.
- Each branch must carry at least one accepted claim, so no branch drifts free of
  the verified research.
- Branches that are identical, or that differ only by truncation of one timeline,
  fail deterministic validation.
- Duration intent must fall inside the configured bounds for that branch.
- Source-video wording, story, personality, footage and exact execution are not inputs
  for copying; the shared overlap check still applies to beat treatments.
- FAIR remains free-only through the shared YouTube bridge.
- A model-validated plan is not producible until the Human Format Gate accepts it.

## Artifacts

```text
format_engine/output/
├── format_requests/            # prepared, provenance-bound planning requests
├── format_responses/           # raw validated model responses
├── format_plans/               # plan + validation report
├── format_review_requests/     # human gate requests
├── format_review_responses/    # recorded human decisions
└── approved_format_plans/      # gate-accepted plans, ready for production
```

## Commands

```bash
python format_engine/format_engine.py --mode prepare
python format_engine/format_model_runner.py --mode batch
python format_engine/format_review.py --mode prepare
python format_engine/format_review.py --mode apply --request <request> --response <response>
```

No score, ranking, predicted retention or automatic branch winner is produced.

## Script section-review provenance

Format treats the approved Script bundle as a provenance-bound input.

If selective section review was never prepared for a branch, Format preserves
the original one-click Script Gate path.

If selective review was prepared, Format verifies the exact canonical
section-state before preparing a Format Request. The state path, SHA-256,
version, target count, target lineage and bound Script Draft must all remain
current, and every target must still be accepted and locked.

A stale, redirected or incomplete prepared section state blocks the Script →
Format handoff. The verified section-review summary is carried in
`request_provenance.section_review`.

## Slice 8 stale-output cleanup

Format preparation treats the current approved Script bundle as the root of the
Format artifact chain.

For each concept, a changed Format Request invalidates its downstream:

- model response;
- Format Plan;
- model-run report;
- raw FAIR output;
- Human Format Gate request;
- Human Format Gate decision; and
- approved Format Plan.

Aggregate model/gate summaries are also removed when their source request set
changes.

Even when a request filename/hash remains current, downstream artifacts are
checked against their own provenance. A response, plan, model run, gate packet,
gate decision or approved plan whose bound request/plan hash no longer matches
is removed. An orphan raw FAIR output without a current validated model-run
report is stale and removed as well.

Valid unchanged provenance is preserved, so successful FAIR work is not
discarded unnecessarily.

Human Format Gate preparation independently ignores stale plans whose
`plan_provenance.request_source` and `request_sha256` do not match the
canonical current Format Request. It also removes stale gate requests,
decisions and approved plans before exposing the gate to the operator.
