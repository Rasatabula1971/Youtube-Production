# Format Engine

Stage 06 of the system map.

Flow:

**Prepare Format Requests → Generate Format Plans → Human Format Gate → Ready for Production Engine**

The engine consumes only `story_script_engine/output/approved_scripts/*` artifacts whose
`script_gate.status` is `READY_FOR_PRODUCTION`.

## Why this stage exists

Long-form and Shorts are separate production branches. They may share:

- source understanding;
- research;
- accepted facts;
- the master story package.

They are not identical edits of the same timeline. The Format Engine is where that
separation becomes an explicit, checkable artifact instead of an assumption.

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

- Only Script Gate approved scripts enter format planning.
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
