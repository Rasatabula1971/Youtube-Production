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

### One budget per video (D-136)

`video_budget.py` keeps one append-only ledger,
`output/video_budget_ledger.jsonl`, keyed by video (`concept:format`). Every
paid step records into it:

| Step | Records |
|---|---|
| Narration Spend Gate ACCEPT | reserves the approved worst case; any other decision releases it |
| Narration return | the actual cumulative narration cost |
| Visual Spend Gate AUTHORIZE | reserves the shot's maximum; Keep placeholder or Retry releases it |
| Generated visual import | the shot's actual cost |
| Thumbnail candidate generation | reserves the maximum before the call, then records the actual |
| Thumbnail import, final sound import | the actual cost already spent outside the app |

An item counts at the larger of its live reservation and its actual spend.

- **Above the ceiling:** a new reservation that would take the video's
  committed total above `ceiling_usd` is refused. This applies across
  narration, visuals and thumbnails.
- **Above the target:** a reservation is allowed and the overrun is flagged.
- **Actual spend:** always recorded, because it has already happened.

The target (US$5) and ceiling (US$10) live in `video_budget_config.json`,
with `confirmed_by_human: false` until you confirm them. The stage caps (per
shot, per thumbnail, global visual workflow) still apply on top of the
budget. The `/produce` page shows each video's committed and spent totals.

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

## Paid narration dispatch (D-139)

`narration_dispatch.py` makes the paid provider call itself and hands the
audio to the existing return registration. Audio QC, the Final Audio Gate and
the per-video budget then apply unchanged.

**When it is allowed.** All of these must hold:

- the provider contract is verified (`provider_contract` in
  `narration_render_config.json`; until then the narration request is
  BLOCKED);
- `provider_adapter` names an adapter kind, model and voice, the API key
  variable (`NARRATION_PROVIDER_API_KEY`) and the price per 1,000
  characters, which is never guessed;
- the Narration Spend Gate approved the exact current request;
- the estimate for the segments to render, plus what this narration already
  cost, stays within the approved worst case.

**Re-recording.** The first dispatch renders every segment. After a
`REWORK_SEGMENTS` decision at the Final Audio Gate, a dispatch re-records
only the named segments, as the next attempt within the approved
regeneration policy. The other segments keep their registered audio.

**Failures.** A provider failure part-way records what was already spent,
in the dispatch history and in the budget.

**The built-in adapter.** `HTTP_TTS_JSON` posts:

```json
{"model": "...", "voice_id": "...", "text": "...", "speed": 1.0,
 "emotion": "...", "intensity": "...", "format": "wav"}
```

It accepts either an audio response or JSON with base64 `audio`, plus an
optional `cost_usd` and `job_id`. A provider with another shape needs one
adapter function in `ADAPTERS`.

**UI.** The buttons are on `/produce`: "Generate narration with the
provider" on an approved Narration spend item, and "Re-record N segments" on
a Final audio rework. Each asks for confirmation first.

## Human Visual Plan Gate (D-138)

After the free narration preview is approved, `visual_plan_review.py` builds
the complete visual plan per video. It holds the paid narration until you
approve it on `/produce#plan`.

- **Built from:** the approved format plan, using the same requirements as
  the visual manifest.
- **Each shot shows:**
  - its beat, purpose, visual treatment and claims;
  - its window in the approved preview, taken from the preview's per-beat
    audio;
  - the first source tier it will try.
- **Also shown:** the video's budget (D-136).

| Decision | Effect |
|---|---|
| `APPROVE_VISUAL_PLAN` | Bound to the format plan, the preview audio and the plan content. |
| `REWORK_VISUAL_PLAN` | Needs a note; spend stays held until the format plan is reworked. |

- **Enforcement.** The server refuses ACCEPT at the Narration Spend Gate for
  a video whose plan is not approved. The workflow stops at
  `HUMAN_VISUAL_PLAN_GATE`, or at `VISUAL_PLAN_REWORK_REQUIRED` after a
  rework.
- **Already-spent videos.** A video whose narration spend was authorized
  before this gate existed is not pulled back to it.
- **After the paid narration.** Once it is approved (D-137), the storyboard
  is retimed to the real audio as before; its shots are the approved plan's
  beats.

## Human Final Audio Gate (D-137)

Audio QC is automatic: it checks duration, silence, clipping and missing
files. After it passes, `narration_final_review.py` holds the exact paid
narration for a human to listen to, segment by segment, on `/produce#audio`.

| Decision | Effect |
|---|---|
| `APPROVE_FINAL_AUDIO` | Makes this audio the narration. |
| `REWORK_SEGMENTS` | Names segments to re-record, with a note; the next provider return replaces them. |
| `REJECT_AUDIO` | The whole return is unusable; needs a note. |

- **Binding.** An approval is bound to the hashes of the QC report and the
  timing map, so a new return or a re-run of QC reopens it.
- **Ready means approved.** The server treats narration audio as ready only
  once it is approved, so the visual manifest, storyboard and everything
  timed from the audio wait for it.
- **Stops.** The workflow stops at `HUMAN_FINAL_AUDIO_GATE`, or at
  `FINAL_AUDIO_REWORK_REQUIRED` after a rework or reject.
- **History.** Decisions are appended to `final_narration_history.jsonl`.

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

## Slice 14 — resumable zero-cost visual discovery and candidate gate

The current storyboard-driven search request now flows through zero-cost
discovery before stopping for human selection.

The acquisition runner accepts only a current search request. It records the
exact request hash/fingerprint in the raw discovery artifact and revalidates
the request before every shot-level provider call.

Raw discovery is checkpointed per shot. A later run may reuse a prior shot only
when its storyboard/search fingerprint is unchanged and that shot had no
provider errors. This makes interrupted searches resumable without blindly
repeating already-complete calls.

Provider adapters are fail-soft at the provider boundary. One provider timeout
or malformed payload is recorded without cancelling valid results from the
other zero-cost sources. Candidate counts and provider errors are retained per
shot.

Compiled results inherit the exact search-request hash. A result is current
only while its request file exists and matches the stored hash, that request is
still current against the storyboard, concept/format identities match, and the
result shot IDs/fingerprints exactly match the current request.

The Human Visual Candidate Gate requires complete current result coverage for
all branches that require search. Partial branch results cannot unlock review.

This stage is discovery-only: no visual file is downloaded, creator/editorial
footage is never auto-approved, and no paid generation provider is called.

## Slice 16 — managed visual asset truth boundary and rough cut

The visual rough cut no longer treats a selected candidate URL as if the media
itself were available.

A real rough-cut asset requires a current `managed_visual_asset` record whose
candidate ID/fingerprint, search-result hash, candidate-review hash, optional
rights-review hash and local asset hash are all current.

For verified free/owned selections, `visual_asset_acquire.py` may copy or
download the asset through the existing safe zero-cost acquisition channels.
Search-result provenance is revalidated before acquisition. For editorial
selections, current Human Rights/Context approval is checked against the exact
current review/candidate fingerprints, but the file is never auto-downloaded.

`visual_rough_cut.py` records, per used shot, the managed registry path/hash and
asset path/hash. A selected shot without a current managed file is emitted as a
placeholder with an explicit reason rather than a false existing-asset
assignment.

The server considers a rough cut current only when its storyboard, candidate
review, required rights review, and complete managed-asset registry set all
match current files. Registering a new manual visual invalidates the existing
rough cut so it is rebuilt automatically.

Automatic acquisition failures block current rough-cut preparation. Missing
manual editorial files do not block structural rough-cut review; they stay
visible placeholders.

Slice 16 ends at the Human Rough-Cut Gate and never authorizes paid visual
generation.

## Slice 15 — provenance-bound visual Rights/Context Gate

Visual candidate selection now derives its route from candidate provenance.

Automatic reuse requires a recognized reusable source tier, `VERIFIED` rights,
explicit commercial-use permission, and a source URL or local path.

Recognized creator/editorial tiers are never treated as automatically reusable,
even if a result payload is tampered to say `ELIGIBLE`. They route to the
Human Rights/Context Gate.

Unsupported source tiers cannot use the rights gate as an escape hatch. A
candidate with unknown provenance is rejected even if it claims
`DISCOVERY_ONLY` or `HUMAN_REVIEW_REQUIRED`.

Before a rights/context decision can be displayed or written,
`visual_rights_review.py` verifies:

1. the candidate review is complete;
2. its source-result SHA-256 matches the current result file;
3. that result still passes `search_result_is_current`;
4. concept and format identity match;
5. the selected result/shot fingerprint is current;
6. the selected candidate fingerprint is current; and
7. the candidate still routes to the recognized Rights/Context Gate.

The rights artifact records both the candidate-review provenance and the exact
search-result provenance. Stale review files are excluded and any associated
stale rights artifact is removed.

This stage records human editorial/context intent only. It downloads no media,
authorizes no spend, and stops before Slice 16 asset acquisition.

## Slice 17 — current gap planning and globally capped Visual Spend Gate

`visual_gap_planner.py` now treats the Human Rough-Cut review as a strict
provenance boundary. A gap plan is current only while:

- the rough-cut file exists in the managed rough-cut directory;
- the rough-cut review exists in the managed review directory;
- the review decision is exactly `APPROVE_WITH_GAPS`;
- `approved_for_gap_planning` is true;
- the review points to the exact current rough-cut path/hash;
- concept and format identities match; and
- rebuilding the plan from those current inputs produces the exact stored plan.

Gap preparation removes historical plans that no longer satisfy that contract.

`visual_spend_review.py` consumes only current gap plans. Orphaned/stale spend
reviews are pruned. Human decisions are fingerprint-bound to the current hero
gap.

Spend policy is fail-closed. The configuration must use USD, explicitly require
human authorization, explicitly forbid paid calls without authorization, and
provide finite positive per-shot/workflow caps.

The workflow hard cap is calculated across all current gap-plan branches.
`apply_action` serializes spend mutations with an in-process lock so two
concurrent authorizations cannot both pass against the same remaining budget.
Non-finite amounts are rejected before comparison.

Slice 17 produces no generation handoff. It stops at the Human Visual Spend
Gate, the no-spend boundary, or completed spend decisions. Paid provider
execution remains impossible in this stage.

## Slice 18 — canonical visual spend → zero-cost generation handoff and assembly

The visual spend artifact is now canonical and tamper-resistant. Reconciliation
preserves/recomputes the review status, summary and branch authorization total.
Invalid or over-cap decisions are removed from current state.

`visual_generation_handoff.py` consumes the complete current visual-spend
snapshot rather than scanning arbitrary review files. It emits requests only for
`AUTHORIZE_GENERATION` decisions in a globally valid spend state.

Each generated request binds:

- current gap-plan path/hash;
- current visual-spend-review path/hash;
- exact human spend-decision SHA-256; and
- exact maximum authorized USD cost.

The request explicitly records `provider_call_authorized=false` and
`execution_authorized=false`. Preparing it spends nothing.

`visual_assembly_plan.py` now validates the exact current gap plan, requires a
complete current spend review whenever hero gaps exist, recognizes current
managed asset statuses, and revalidates managed/generated local files.

The assembly plan can resolve to:

- `READY_FOR_EDIT_ASSEMBLY`;
- `WAITING_FOR_PREMIUM_GENERATED_ASSETS`;
- `WAITING_FOR_LOCAL_VISUAL_ASSETS`; or
- `WAITING_FOR_EXISTING_VISUAL_RETRY`.

A premium generation request that is missing or stale remains a pending premium
slot. A generated asset is accepted only when its request hash, local asset hash
and actual cost remain current and within the request's authorized maximum.

Assembly plans can be independently rebuilt and compared through
`assembly_plan_is_current`, so later asset/request changes invalidate an old
timeline instead of silently surviving.

Slice 18 ends before edit-manifest creation and before any video rendering.

## Slice 19 — provenance-bound edit manifest and local structural preview

`edit_manifest.py` now treats currentness as a rebuildable contract.

A manifest can be produced only from a current
`READY_FOR_EDIT_ASSEMBLY` visual assembly and current PASS narration
QC/timing. Narration QC is tied to the current registered render result, and
every QC/timing segment must match in exact unique order.

The manifest records SHA-256 hashes for:

- visual assembly;
- narration Audio-QC;
- narration timing map;
- approved sound-design brief when present; and
- every narration audio file used by the preview timeline.

`manifest_is_current` reloads and rebuilds the complete manifest from current
inputs. Any assembly, narration file, QC/timing or sound change invalidates the
stored manifest.

`edit_preview_render.py` rejects a stale manifest before FFmpeg execution.
Rendering is local-only. It produces neutral placeholders where the manifest
explicitly permits them, muxes QC-passed narration at timing-map positions, and
writes a non-publishable structural preview.

`preview_result_is_current` requires the exact current manifest hash, exact
preview SHA-256 and exact preview byte count. Stale result JSON and stale preview
media are pruned during batch rendering.

The render command exits partial/non-zero when any current manifest fails to
render, rather than reporting successful automation with hidden render
failures.

`edit_preview_review.py` consumes the same current-preview contract, so a
human cannot approve a preview after its manifest or preview bytes have become
stale.

No paid provider, premium visual execution, generated music/SFX, upload or
publish action exists in Slice 19.
## Slice 20 — approved edit direction to current final-production handoff

After the Human Edit Preview Gate approves the current free structural preview,
the normal workflow automatically runs one more deterministic zero-spend step:

```text
current Human Edit Preview approval
        ↓
revalidate current preview + edit manifest
        ↓
revalidate final visual and narration bytes
        ↓
revalidate current Sound Design Brief
        ↓
provider-neutral final-production handoff
        ↓
FINAL_PRODUCTION_HANDOFF_READY
        ↓
STOP
```

The final handoff is rebuild-current. Merely retaining the same filenames is not
enough: the approval must still target a current Slice 19 preview, that preview
must still target a current edit manifest, every final visual/narration file
hash must match, and the Sound Design Brief must still be current against its
own approved narration-preview provenance.

The stored handoff is independently rebuildable. If rebuilding from current
inputs produces a different payload, the old handoff is stale and cannot count
as final-production readiness.

Generated-visual cost reporting is limited to current generated assets actually
used by the final visual track; historical/replaced generated assets are not
summed into the handoff.

Slice 20 remains a hard no-spend boundary. It performs no paid provider call,
no final music/SFX generation, no final video render, no upload, and no publish
action. A successful handoff therefore reports readiness for a later final
sound/provider-or-licensed-asset registration stage rather than claiming that
the video is publish-ready.

## Slice 21 — final sound requirement and licensed-asset boundary

The current Slice 20 final-production handoff now automatically becomes an exact
final-sound plan before any final rendering work begins:

```text
current final-production handoff
        ↓
final_sound_plan_prepare
        ↓
fingerprinted MUSIC / SFX requirements
        ↓
WAITING_FOR_FINAL_SOUND_ASSETS
        ↓
human registers licensed local asset
        or explicitly omits requirement
        ↓
FINAL_SOUND_ASSETS_READY
        ↓
STOP
```

`final_sound_plan.py` accepts only a current rebuild-valid Slice 20 handoff.
It converts approved sound-design intent into stable requirement IDs and
fingerprints while explicitly keeping provider calls, spend authorization,
final rendering, upload and publishing disabled.

`final_sound_asset_import.py` is the managed-media trust boundary. A registered
file must be a supported audio type, non-empty, explicitly commercial-safe and
bound to a licence/ownership reference. The local file is copied into
`production_engine/output/final_sound_assets/` and its SHA-256 and byte count
are recorded against the exact current sound plan and requirement fingerprint.

A non-zero cost is accepted only as a record of an already completed external
human purchase. The human must explicitly confirm that fact. The app never
interprets registration as permission to buy media and never executes the
provider transaction.

A planned sound may also be intentionally omitted, but only through an explicit
human note. This avoids forcing unnecessary sound into an edit while preventing
a missing asset from silently becoming an omission.

Slice 21 stops at `FINAL_SOUND_ASSETS_READY`. It does not mix final sound into
video, create a publish-ready render, upload, or publish. Those remain the next
production boundary.

## Slice 22 — rebuild-current local final render and Human Final Export Gate

Slice 22 turns the fully resolved Slice 21 media set into a local final
candidate and then stops for exact-byte human review:

```text
FINAL_SOUND_ASSETS_READY
        ↓
final_render_manifest_prepare
        ↓
current visuals + narration + licensed/omitted sound resolutions
        ↓
final_render_local
        ↓
local H.264/AAC final candidate
        ↓
HUMAN_FINAL_EXPORT_GATE
        ↓
APPROVE_EXPORT
        or
RETURN_TO_VISUALS / RETURN_TO_NARRATION / RETURN_TO_SOUND
        ↓
FINAL_EXPORT_APPROVED
        ↓
STOP
```

`final_render_manifest.py` rebuilds the complete final-render contract from
live current inputs. The manifest rejects stale visual/narration bytes, stale
sound plans, incomplete sound resolutions, and unknown sound-to-narration
segment references. Every registered sound resolution is bound by its
requirement fingerprint, resolution-file hash and managed asset hash. Explicit
human sound omissions cross the manifest as provenance records rather than
silently disappearing.

Music beds use the narration segment timing window. SFX cues use deterministic
segment-relative placement. The fixed local mix policy is recorded in the
manifest so a later re-render cannot silently change levels. The Human Final
Export Gate is the creative check for the final mix.

`final_render.py` uses local FFmpeg only. It renders approved final visual
assets with no placeholder frames, mixes QC-passed narration and current
licensed final sound, encodes H.264/AAC, and records the exact resulting SHA-256
and byte count. Internal visual timeline gaps fail closed; a short visual tail
is extended by holding/looping the last approved asset through the narration
duration.

`final_export_review.py` is the final human gate for Slice 22. Approval is
bound to the exact current render-result artifact and exact final MP4 hash.
Replacing any upstream current media or changing the rendered file invalidates
that approval.

An approved export is still not an upload or publish authorization. Slice 22
records `upload_authorized=false` and `publish_authorized=false`, performs no
network upload, and invokes no publishing API.

Slice 22 ends at `FINAL_EXPORT_APPROVED`.

## Thumbnail rendering

Slice 25 thumbnail concepts that have at least one title pair passing Slice 26
validation can be rendered into 1280x720 images from a locked template,
previewed at phone size and in a mock niche feed, and reviewed at a Human
Thumbnail Gate. Approving an image does not choose the title-thumbnail
package; that is the Final Packaging Gate, which by default requires the
chosen package's image to be approved here. See `THUMBNAIL_RENDERING.md`,
D-098 and D-099.
