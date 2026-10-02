# Production Engine

Stage 07 begins after the Human Format Gate accepts a format plan.

The implemented Production Engine now has two policy slices:

1. **Voice Performance planning + Human Performance Gate** — free-only planning
   of how immutable narration is delivered.
2. **Visual Acquisition + Cost Router** — offline cheap-first mapping of visual
   requirements.

Neither slice renders paid media.

## Current flow

```text
Format Gate approved plan
        ↓
Voice Performance request
        ↓
FAIR free-only performance plan
        ↓
Human Performance Gate
        ↓
Visual requirement manifest
        ↓
Own/reusable asset library
        ↓
Verified free commercial / public-domain / compatible CC material
        ↓
Editorial excerpt candidate → human rights/context review
        ↓
Motion graphic / still treatment
        ↓
Cheap AI generation
        ↓
Higgsfield premium fallback
```

The Voice Performance stage comes first because delivery and narration timing
shape the edit. See `VOICE_PERFORMANCE.md`.

## Pre-monetization budget

The default visual configuration targets no more than **US$5** of paid visual
generation per video and hard-stops automated paid visual routing at **US$10**.
These are operating constraints for channel testing, not permanent production
rules.

The budget can be changed later without changing the manifest schema.

## Third-party excerpts

An `EDITORIAL_EXCERPT` is never auto-selected. It remains
`HUMAN_REVIEW_REQUIRED` until the later source/copyright/licensing gate
confirms that the intended use is acceptable in context.

The system records provenance so a reviewer can inspect:

- source URL or local path;
- licence/reference information;
- commercial-use flag when known;
- attribution requirement when known;
- intended duration;
- the script/format beat the asset supports.

There is deliberately no "three-second rule" in the code.

## Commands

Prepare Voice Performance requests:

```bash
python production_engine/voice_performance.py --mode prepare
```

Generate free-only performance plans through FAIR:

```bash
python production_engine/voice_model_runner.py --mode batch
```

Prepare the Human Performance Gate:

```bash
python production_engine/voice_review.py --mode prepare
```

After human performance approval, prepare visual manifests:

```bash
python production_engine/visual_acquisition.py --mode prepare
```

Re-evaluate visual manifests after candidate assets have been added:

```bash
python production_engine/visual_acquisition.py --mode route
```

## Output

```text
production_engine/output/
├── voice_performance_requests/
├── voice_performance_specs/
├── voice_performance_review_requests/
├── voice_performance_review_responses/
├── approved_voice_specs/
├── visual_manifests/
│   └── <concept>.<format>.visual_manifest.json
└── visual_summary.json
```

Each format beat becomes one visual requirement. Later acquisition adapters can
append candidate assets to a requirement without changing its provenance-bound
identity.

## Paid narration remains unbuilt

D-061 still governs paid narration: Higgsfield is the planned licensed-voice
renderer, but the paid adapter is intentionally not part of the current slice.
Before a paid call is allowed, the system still needs:

- configured licensed voice identity;
- licence reference;
- completed voice calibration artifact;
- dry-run worst-case cost estimate;
- accepted Human Performance Gate decision.

After rendering, local ffmpeg Audio QC must check duration, unexpected silence,
clipping and missing segments. No automatic acoustic emotion grading or
automatic take winner is planned.

## Rough-cut/prototype boundary

Before escalating to expensive final visual generation, the production design
keeps a low-cost rough-cut/prototype step so script, narration, pacing and scene
sequence can be judged together. This is a planned production boundary, not yet
an implemented renderer.

## Higgsfield visuals

Higgsfield remains the paid premium fallback for generated visuals, not the
default visual source. Paid visual generation happens only after cheaper
acceptable routes have been exhausted.

## Slice 10 — zero-cost narration preview boundary

The first production work after Human Performance approval is a free local
prototype, not a paid narration request.

The chain is:

1. deterministic pre-render engagement validation;
2. current narration-preview manifest preparation;
3. reference-only music/SFX planning;
4. local Kokoro narration preview rendering; and
5. Human Narration Preview Gate.

Every step is fail-closed against stale provenance. Engagement results record
the approved Voice Performance spec hash. Preview manifests carry that same
approved-spec provenance. Render metadata binds the exact manifest hash and
rendered audio hash. The human approval records both hashes plus the approved
Voice spec hash.

Paid narration preparation independently rechecks the current approved preview
against the current Voice Performance spec and rendered preview audio. A
previous approval cannot be reused after upstream performance changes.

The preview renderer has no network/paid fallback. Missing Kokoro/local audio
dependencies stop the chain before the human listen gate.
