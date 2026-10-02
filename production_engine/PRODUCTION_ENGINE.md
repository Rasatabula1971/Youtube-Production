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

## Slice 11 — narration request, quote and Human Spend Gate

Human approval of the free narration prototype unlocks preparation, not
spending.

The Production Engine first creates a commercial-safe Sound Design Brief from
the current preview approval. The brief copies descriptive timing, mood, SFX
and ducking intent only; prototype/reference media is not attached.

A narration render request is quote-eligible only when all of these are current:

- approved Voice Performance spec;
- approved free narration preview and exact preview audio;
- Sound Design Brief;
- configured licensed voice identity, licence reference and calibration;
- verified provider narration contract.

The render request records hashes for the Voice Performance spec and Sound
Design Brief. Existing quote files are validated against the exact current
render-request hash, provider, currency and attempt policy.

A missing quote produces `WAITING_FOR_PROVIDER_QUOTE`. A stale, malformed or
mismatched quote also returns to quote-required state; it does not crash the
pipeline and does not reuse the old cost. The system never guesses provider
pricing.

Only a current provider quote can produce `READY_FOR_SPEND_GATE`. The Human
Narration Spend Gate then displays the current initial estimate and worst-case
USD amount and requires explicit approval of that ceiling. Its ACCEPT records
authorization; it still does not execute the paid narration render.

Changing the current estimate invalidates old spend-review decisions and
approved spend artifacts.

The checked-in Higgsfield narration provider contract remains intentionally
unverified, so production will stop at provider setup/quote requirements until
those prerequisites are supplied from verified provider information.

## Slice 12 — authorized narration return and deterministic Audio QC

The paid narration API adapter remains intentionally unimplemented until a
provider endpoint and schema are verified. Slice 12 instead implements the safe
return path after a human has already authorized the exact current quote.

The chain is:

```text
Human Narration Spend ACCEPT
        ↓
WAITING_NARRATION_RENDER_RETURN
        ↓
register provider job/ref + actual cost + every segment audio file
        ↓
managed narration audio + provenance-bound render result
        ↓
local ffprobe / ffmpeg Audio QC
        ↓
narration timing map
        ↓
NARRATION_AUDIO_READY
        ↓
STOP before visual production
```

Actual cumulative cost cannot exceed the accepted worst-case narration ceiling.
The registered result records the exact render-request hash, exact spend
approval hash, exact cost-estimate hash, provider job/reference and per-segment
audio hashes.

Audio is copied into `production_engine/output/narration_audio/` so downstream
work does not depend on arbitrary external file paths.

The narration request now contains a provider-independent
`expected_duration_seconds` for each segment, derived from immutable text at a
base 150 words/minute adjusted by the approved delivery speed. This duration is
the QC baseline. Provider-returned duration values are not trusted.

Audio QC accepts only the current registered provider return. It verifies
duration tolerance, unexpected silence, clipping, exact segment coverage,
missing files and attempt limits. A replacement provider return deletes stale
QC/timing artifacts before the new files are evaluated.

A QC summary is `PASS` only when every current authorized branch has a current
PASS result. Partial branch coverage cannot report a global PASS.

Slice 12 does not execute paid narration and does not start storyboard or visual
production.

## Slice 13 — narration-bound visual manifest, storyboard and search request

Visual production now begins only after final narration has passed deterministic
local Audio QC.

The zero-spend planning chain is:

```text
current QC-passed narration timing map
        ↓
visual acquisition manifest
        ↓
cinematic storyboard
        ↓
rights-aware visual search request
        ↓
VISUAL_SEARCH_READY
```

The visual acquisition manifest records the exact approved Format Plan and the
exact narration timing-map path/hash. Server readiness independently checks both
against current production state, so a historical manifest cannot unlock the
storyboard after narration changes.

Storyboard cards are timed from the final narration map. Narration segment IDs
must exactly equal the visual requirement beat IDs for the branch. The
storyboard records hashes of both inputs and is current only while both remain
unchanged.

The visual search request records the exact storyboard hash and per-shot
fingerprints. Rebuilding search preparation removes stale request/result files.
Raw discovery results can be reused only when the corresponding shot
fingerprint is unchanged.

The search request policy remains:

- search existing assets before generation;
- never treat downloadability as reuse permission;
- never auto-approve creator/editorial excerpts;
- never auto-approve unknown rights; and
- never allow paid generation calls during this stage.

Slice 13 intentionally stops before `visual_search_acquire`.
