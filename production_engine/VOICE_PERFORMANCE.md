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

Every branch beat is bound to the exact approved Script section narration
identified by the Format plan's `source_section_ids`.

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

## Next production slice

After this gate is proven, build the paid narration adapter with a dry-run cost
estimate, then local ffmpeg Audio QC and a timing map.

Visual acquisition remains cheap-first. A low-cost rough-cut/prototype should be
used to judge script, narration, pacing and scene sequence before escalating to
expensive final visual generation.
