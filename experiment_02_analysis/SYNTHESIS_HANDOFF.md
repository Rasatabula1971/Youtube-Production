# Experiment 02 Synthesis / Transformation Handoff

## Purpose

This layer closes the analytical side of Experiment 02.

It takes evidence-valid analyzed source profiles and creates two deterministic
artifacts:

1. a mechanism library describing repeated observed mechanisms;
2. a Transformation Engine handoff containing replicated mechanisms that may
   justify concept exploration later.

It does not generate new video concepts itself.

It uses zero YouTube API calls and zero model calls.

## Input

Default input:

~~~text
experiment_02_analysis/output/profiles_analyzed/
~~~

These are final profiles produced after source evidence ingestion, analysis
request preparation, model or human analysis, deterministic evidence apply, and
final profile validation.

## Build

~~~powershell
python .\experiment_02_analysis\synthesis_handoff.py --mode build
~~~

Override the profile directory with --profiles-dir when needed.

If no analyzed profiles exist, the layer writes:

~~~text
WAITING_FOR_ANALYZED_PROFILES
~~~

It does not fabricate patterns.

## Mechanism states

### SINGLE_SOURCE_OBSERVATION

The mechanism does not meet the existing Experiment 02 replication gate across
independent videos and channels.

It stays in the mechanism library but does not enter the Transformation Engine
handoff.

### MODEL_SYNTHESIS_DRAFT

The mechanism meets the replication gate across independent videos/channels,
but the replicated support has not yet met the same gate among profiles with
review.completed=true.

It can enter the handoff only as REQUIRES_HUMAN_REVIEW.

### HUMAN_CONFIRMED_PATTERN

The mechanism meets the replication gate among human-reviewed profiles across
independent videos and channels.

It can be handed forward as READY_FOR_TRANSFORMATION_ENGINE.

These states are not scores or rankings.

## Replication evidence

For each mechanism, the library records:

- unique videos;
- unique channels;
- reviewed videos;
- reviewed channels;
- observed dimensions;
- topics;
- formats;
- occurrence count;
- observed finding examples;
- transferable-mechanism descriptions;
- source-specific elements to avoid; and
- accepted transformation directions that already pass the Source Dependency
  Test.

## Scope

The synthesis reports whether observed support is single-topic or cross-topic,
and single-format or cross-format.

Cross-topic or cross-format support is descriptive only. It is not treated as a
higher score.

## Human review gate

By default, require_human_review_for_ready is true.

Therefore model-generated analysis can produce a replicated draft, but it
cannot by itself create a ready Transformation Engine handoff.

That preserves the project's human review requirement.

## Source Dependency Test

Only transformation directions whose existing source_dependency_test.passes
value is exactly true are included.

A failed or missing Source Dependency Test is excluded from the accepted
direction list even if the containing profile is otherwise valid.

## Outputs

Generated files:

~~~text
experiment_02_analysis/output/synthesis/
├── mechanism_library.json
├── transformation_handoff.json
└── synthesis_summary.json
~~~

The mechanism library contains all observed mechanisms from valid profiles,
including single-source observations.

The transformation handoff contains only replicated patterns, with their
review state, evidence breadth, source-specific exclusions, and existing
accepted transformation directions.

## Important boundaries

The synthesis layer does not conclude that repeated mechanisms caused views,
retention, recommendation, or virality.

It does not rank mechanisms.

It does not calculate a composite mechanism score.

It does not automatically generate concepts.

Its job is to transform many evidence-valid source analyses into a clean,
auditable input for the next engine.
