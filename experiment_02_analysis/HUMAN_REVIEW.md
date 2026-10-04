# Experiment 02 Human Review Gate

## Purpose

The human review gate converts evidence-valid model analysis into human-reviewed
Experiment 02 profiles.

It is the bridge between model-assisted analysis and the synthesis layer's
HUMAN_CONFIRMED_PATTERN state.

No model or network calls are made.

## Prepare one review packet

~~~powershell
python .\experiment_02_analysis\human_review.py --mode prepare --profile ".\experiment_02_analysis\output\profiles_analyzed\VIDEO_ID.json"
~~~

The packet is written under:

~~~text
experiment_02_analysis/output/human_review_requests/
~~~

Each factual or transfer item receives a stable item ID and includes its
supporting evidence snippets.

Working hypotheses are shown for context but are not factual review items.

## Batch prepare

~~~powershell
python .\experiment_02_analysis\human_review.py --mode batch-prepare
~~~

This prepares review packets for all analyzed profiles.

## Review decisions

Every reviewable item requires exactly one decision:

- ACCEPT
- REJECT

There is no implicit default.

The reviewer should compare the statement with its cited evidence rather than
approve it because the source video performed well.

## Apply

Create a response from human_review_response_template.json, then run:

~~~powershell
python .\experiment_02_analysis\human_review.py --mode apply --profile ".\experiment_02_analysis\output\profiles_analyzed\VIDEO_ID.json" --request ".\experiment_02_analysis\output\human_review_requests\VIDEO_ID.review_request.json" --response ".\path\to\review_response.json"
~~~

Rejected items are removed.

Accepted items remain unchanged.

The resulting profile is validated again.

review.completed becomes true only when:

- every review item has a decision;
- the reviewer identifier is present;
- there are no unknown or duplicate item IDs; and
- the post-review profile still passes Experiment 02 validation.

## Outputs

~~~text
experiment_02_analysis/output/
├── human_review_requests/
├── human_review_reports/
└── profiles_reviewed/
~~~

The synthesis layer should use profiles_reviewed when the objective is to
produce HUMAN_CONFIRMED_PATTERN evidence.

## Boundary

Human review is not a mechanism score and not a popularity judgment.

Its purpose is to decide whether each analysis claim fairly represents the
evidence and should be carried into cross-video synthesis.

## Decision history

Every decision is appended to an append-only log and never rewritten (D-133):

- analysis findings: `experiment_02_analysis/output/human_review_history.jsonl`,
  with the reviewer, note, the decision replaced and the profile hash it was
  made against;
- vision frames: `experiment_02_analysis/output/vision_review_history.jsonl`,
  with the accepted observation and the source hashes.

The review response still holds only the current decision; the review page
shows each finding's full history.
