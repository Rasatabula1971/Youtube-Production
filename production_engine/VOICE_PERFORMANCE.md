# Voice Performance Layer

The Voice Performance Layer is the first Production Engine sub-stage after the
Human Format Gate.

It answers one question only: **how should the already-approved words be
delivered?**

It does not write or rewrite narration, render audio, choose a winning take,
predict retention, or spend provider credits.

## Flow

```text
Human Format Gate approved plan
        ↓
Bind format beats to immutable approved narration
        ↓
FAIR free-only performance planning
        ↓
Deterministic validation
        ↓
Human Performance Gate
        ↓
[future] paid narration renderer
        ↓
[future] local Audio QC + timing map
        ↓
Visual acquisition / rough-cut production
```

## Performance controls

The planning artifact uses the deliberately narrow D-061 control vocabulary:

- emotion;
- intensity;
- speed;
- pause before/after;
- emphasis terms.

Allowed emotions are `neutral`, `curious`, `serious`, `concerned`,
`tense`, `reflective`, with `surprised` allowed only on a reveal beat.

The initial numeric limits live in `voice_performance_config.json`. They are
operating hypotheses, not proven audience-performance rules.

## Immutable narration

Every branch beat is bound only to the exact approved narration from the
**matching format-specific script branch** identified by the Format plan's
`source_section_ids`. A Shorts performance request cannot read long-form
sections, and a long-form request cannot read Shorts sections.

The branch's script psychology profile is carried forward as context, including
the Shorts hook/refresh hypotheses where applicable. Voice Performance may
adjust delivery only; it cannot alter the branch script.

The model response has no narration field. It therefore cannot silently rewrite
the spoken text. Emphasis terms must already occur in that immutable narration.

The Packaging title remains immutable downstream.

## Cost boundary

`voice_model_runner.py` uses the existing FAIR bridge and fails if
`paid_inference_executed` is anything other than `false`.

No Higgsfield API call exists in this slice.

The Human Performance Gate must accept the specification before a future paid
renderer can be introduced. Voice ID, licence reference and calibration
artifact are tracked as render prerequisites and may remain unset while this
zero-spend planning layer is tested.

## Human Performance Gate

An ACCEPT decision requires all configured criteria:

- narration text unchanged;
- delivery matches branch intent;
- restrained emotion curve;
- pace and pauses support comprehension;
- emphasis is grounded in spoken words.

The review request is SHA-256 bound to the exact performance specification so a
stale decision cannot approve a regenerated plan.

A **Rework** decision writes the human note back into the free planning request,
invalidates the current specification, and automatically regenerates a new plan.
It does not simply reopen the same gate.

## Next production slice

After this gate is proven, build the paid narration adapter with a dry-run cost
estimate, then local ffmpeg Audio QC and a timing map.

Visual acquisition remains cheap-first. A low-cost rough-cut/prototype should be
used to judge script, narration, pacing and scene sequence before escalating to
expensive final visual generation.

## Slice 9 — Format handoff provenance and stale-output cleanup

Voice preparation treats the current Human Format Gate approved plan as the
root of each Voice Performance branch.

When a generated Voice request changes, the matching downstream chain is
invalidated:

- model response;
- Voice Performance spec;
- model-run report;
- raw FAIR output;
- Human Performance Gate request;
- Human Performance Gate decision; and
- approved Voice spec.

Aggregate model/gate summaries are also removed when their source request set
changes.

Human Performance Gate preparation independently verifies that each performance
spec points to the canonical current Voice request and that its recorded
`request_sha256` matches the request on disk. Stale specs are not exposed for
human approval, and stale/malformed decisions or approved Voice specs are
removed.

Unchanged current provenance remains cacheable. The cleanup therefore protects
against stale approvals without forcing unnecessary model work.
