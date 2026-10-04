# Packaging Engine Framework

## Purpose

The Packaging Engine turns a human-accepted concept into several structured
title / thumbnail / opening-frame packages before script drafting.

It implements the project's package-before-script rule.

The deterministic framework does not call a model or the network itself and
does not rank package options. The guided workflow may invoke the separate
`package_model_runner.py`, which uses FAIR free-only routing and then returns
responses to this deterministic validator.

## Input

Default input:

~~~text
transformation_engine/output/research_handoff.json
~~~

This contains concepts already accepted by the human Concept Gate.

## Prepare

~~~powershell
python .\packaging_engine\packaging_engine.py --mode prepare
~~~

One package-generation request is created per accepted concept.

Each request carries:

- premise;
- provisional audience promise;
- format;
- mechanism;
- transformation method;
- existing research questions;
- source-dependency result;
- Concept Gate provenance.

## Package contract

Each proposed package must include:

- title;
- thumbnail message;
- thumbnail visual concept;
- optional thumbnail text overlay;
- opening-frame purpose and visual concept;
- expected viewer;
- awareness level;
- one core promise;
- curiosity gap;
- expected payoff;
- format intent;
- explanation of how title and thumbnail complement each other;
- factual/evidentiary dependencies that downstream research must verify.

The title and thumbnail are treated as one communication unit.

## Generate with FAIR

The guided workflow can run all current requests through FAIR free-only routing:

~~~powershell
python .\packaging_engine\package_model_runner.py --mode batch
~~~

Each generated response is bound to the SHA-256 of its exact package request.
Requests are bound to the current accepted-concept handoff. Paid inference is
fail-closed.

## Apply

For manual/offline use, place completed response JSON under:

~~~text
packaging_engine/output/package_responses/
~~~

Then run:

~~~powershell
python .\packaging_engine\packaging_engine.py --mode apply
~~~

Outputs:

~~~text
packaging_engine/output/
├── package_requests/
├── package_responses/
├── package_candidates.json
├── rejected_packages.json
└── summary.json
~~~

Structural acceptance does not approve a package for use. Human Packaging Gate
approval is still required.

The guided UI uses `package_review.py` to review one package at a time and
enforces at most one accepted package per concept.

## Boundary

The Packaging Engine does not:

- score clickability;
- predict CTR;
- declare one package the winner;
- permit misleading promises;
- write the script;
- assume package facts are already verified.

Research dependencies explicitly capture what must be verified before the
package can safely control the script.


## Viewer-need packaging contract

Each package must preserve the accepted concept's viewer need and include:

- `viewer_problem`;
- `viewer_moment`;
- `desired_outcome`;
- `one_sentence_promise`;
- `gap_positioning`;
- `channel_fit_alignment`.

The one-sentence promise should make the value easy to understand in the form:

~~~text
This video helps [specific viewer/problem] so they can [specific outcome].
~~~

Gap positioning must not upgrade a `HYPOTHESIS` or `UNASSESSED` gap into a
proven audience fact.

## Slice 23 architecture migration — post-script title direction

Packaging v1.0 changes the active sequencing contract. The legacy Packaging
Engine in this directory remains available to read historical artifacts and
resume older runs, but it is no longer an active prerequisite before Research.

New active sequence:

```text
accepted concept
→ verified research
→ approved story/script
→ 5 Short title directions + 5 Long-form title directions
→ Human Title Direction Gate
→ mature Packaging Engine (next slice)
```

### Internal working title versus public title

Story, Script and Format require a stable internal title for provenance and
artifact identity. That value is now marked `INTERNAL_WORKING_TITLE` and must
not be interpreted as the final public YouTube title.

Legacy `selected_titles` are ignored when generating current Script/Format
artifacts. A public title may be rewritten later without invalidating approved
narration merely because wording changed.

### Post-script 5+5 title directions

`title_direction.py` prepares one request per exact current
`approved_script_bundle`. It carries:

- opening hook and hook mechanism;
- approved script section outline;
- story question and payoff intent;
- approved evidence claims;
- five configured psychological angles;
- Short versus Long-form identity;
- title-length guidance rather than a hard 60-character cutoff.

`title_direction_model_runner.py` uses the existing FAIR free-first routing
policy. It requests exactly five Short and five Long-form directions and fails
closed on invented evidence references or malformed stable IDs.

Each candidate stores:

- `title_id`;
- `format`;
- `title_text`;
- `psychological_angle`;
- `primary_driver`;
- `secondary_driver`;
- `core_claim`;
- `evidence_refs`;
- `character_count`;
- `search_intent`.

No viral score, CTR prediction or automatic winner ranking is produced.

### Human Title Direction Gate

`title_direction_review.py` requires one Short and one Long-form selection per
concept. A selection records a preferred psychological/title direction and is
explicitly **not** final wording.

The selected artifact uses:

`PREFERRED_TITLE_AND_PSYCHOLOGICAL_DIRECTION_NOT_FINAL_WORDING`

and stores `final_wording_editable_later=true`.

Rework is scoped to `TITLE_DIRECTIONS_ONLY`. It changes the title-direction
request, invalidates only the title-generation response/candidate aggregate,
and leaves approved script/evidence untouched.

Historical selections are archived append-only. Current state is bound to the
candidate-set SHA-256; stale candidate sets reopen the gate.

### Slice 23 boundary

The successful boundary is:

`TITLE_DIRECTION_SELECTED`

Format and Production remain held after that point until Slice 24 builds the
Packaging Brief and Viewer Promise Contract and begins mature title/thumbnail
coordination.

## Slice 24 — Packaging Brief + Viewer Promise Contract

Slice 24 starts after the post-script Human Title Direction Gate and builds one
deterministic brief per concept/format:

```text
TITLE_DIRECTION_SELECTED
        ↓
packaging_brief_prepare
        ↓
approved script + opening hook + payoff
+ verified research + selected title direction
+ Human Framing + audience context
        ↓
PACKAGING_BRIEF_READY
        ↓
STOP
```

The brief does not use a model. It only projects already-approved upstream
artifacts, which keeps the truth boundary explicit before psychological angle
expansion and thumbnail creation.

Each brief contains:

- internal pre-publish `video_id` (`concept_id:format`);
- format;
- compact source evidence;
- approved concept;
- approved script metadata and exact approved sections;
- opening hook;
- central question;
- payoff;
- selected title direction and psychology metadata;
- target audience context;
- SEARCH/BROWSE/HYBRID intent;
- approved claims;
- approved numeric tokens;
- strongest approved visual opening event;
- strongest core fact;
- strongest approved stakes/consequence;
- strongest desired transformation/resolution;
- rejected/rework research claims as prohibited/unsupported context;
- Viewer Promise Contract.

The Viewer Promise Contract explicitly records what a click is supposed to mean:

`viewer_expectation`, `promise_subject`, `promise_question`,
`promise_stakes`, and `promise_payoff`.

The brief fails closed on missing script/hook/evidence/title direction, evidence
conflicts, unsupported evidence references and invalid intent classifications.

Saved briefs are rebuild-current. Any upstream byte change that changes the
derived contract invalidates the brief.

Slice 24 deliberately does not generate thumbnails, pair titles and thumbnails,
score packages, approve final packaging, or unlock Format/Production. Those are
later Packaging slices.

## Slice 25 — Psychological Packaging Angles + Thumbnail Concepts

Slice 25 expands the evidence-bound Packaging Brief into deliberate packaging
hypotheses before any title-thumbnail pairing:

```text
PACKAGING_BRIEF_READY
        ↓
prepare psychological angle requests
        ↓
FAIR free-first angle generation
        ↓
5 distinct psychological hypotheses per format
        ↓
prepare thumbnail concept requests
        ↓
FAIR free-first thumbnail concept generation
        ↓
1 structured thumbnail concept per angle
        ↓
THUMBNAIL_CONCEPTS_READY
        ↓
STOP
```

### Psychological angle contract

Every format receives exactly five hypotheses with:

- `angle_id`;
- `primary_driver`;
- `secondary_driver`;
- `viewer_question`;
- `emotional_trigger`;
- `stakes`;
- `information_given`;
- `information_withheld`;
- `expected_click_reason`;
- `evidence_refs`;
- `selected_title_direction_alignment`.

Five different primary drivers are mandatory. Exactly one hypothesis is the
`ANCHOR` to the human-selected title direction; four are deliberate
`ALTERNATIVE` hypotheses.

SEARCH emphasizes subject/problem/payoff clarity. BROWSE emphasizes attention,
curiosity, stakes and consequence. HYBRID balances semantic clarity with
psychological attraction. Shorts prioritize instant comprehension and rapid
promise confirmation; Long-form can support deeper mystery and open loops.

The model may propose creative framing, but it may not invent facts. Evidence
refs must come from approved claims. Unapproved numbers and unsupported
high-risk factual words are rejected.

### Thumbnail concept contract

Every current angle receives one concept containing:

- `thumbnail_id`;
- `angle_id`;
- `hero_subject`;
- `secondary_element`;
- `visual_anomaly`;
- `visual_action`;
- `emotion`;
- `composition`;
- `background`;
- `subject_separation_method`;
- `text`;
- `text_word_count`;
- `viewer_visual_question`;
- `timestamp_safe`;
- `mobile_legibility_intent`;
- `evidence_refs`;
- `aspect_ratio`;
- `primary_focal_points`;
- `meaningful_visual_elements`;
- `critical_bottom_right_content`;
- `face_present`.

The validator enforces 16:9, one primary focal point, no more than three
meaningful visual elements, four thumbnail-text words maximum, exact word-count
metadata, timestamp safety and no critical bottom-right content.

Thumbnail evidence must be approved and remain connected to the originating
angle. Unsupported numbers, unsupported high-risk factual wording and obvious
multi-word repetition of the selected title direction are rejected.

### Cost and retry behavior

Both generation stages use the existing free-first FAIR bridge and the existing
direct backup policy. Work is split per internal `video_id`, so a provider
failure does not destroy already validated format outputs. Validated responses
are skipped on retry when their request hash is unchanged.

### Slice 25 boundary

`THUMBNAIL_CONCEPTS_READY` is not packaging approval. No image is rendered,
no title-thumbnail pair is selected, no package score is produced, and
Format/Production remain locked.

Slice 26 can now evaluate cross-candidate title-thumbnail compatibility,
redundancy, information gain, promise consistency and claim/hook alignment.

## Slice 26 — Title + Thumbnail Pairing and Package Validation

Slice 26 turns the Slice 25 creative hypotheses into a complete compatibility
matrix:

```text
THUMBNAIL_CONCEPTS_READY
        ↓
5 current titles × 5 current thumbnails
        ↓
25 package hypotheses per format
        ↓
5 resumable validation chunks per format
        ↓
semantic + evidence + promise + hook validation
        ↓
PASS / REWORK / REJECT per package
        ↓
PACKAGE_VALIDATION_READY
        ↓
STOP
```

### Full cross-pairing

The pairing engine explicitly rejects the assumption:

`Title 1 → Thumbnail 1`

Each title is evaluated against every thumbnail. Stable package IDs bind
`title_id + thumbnail_id`.

The selected Human Title Direction remains marked in the matrix. If the human
edited that selected title wording at the Title Direction Gate, the edited
wording is preserved rather than reverting to the original model text.

### Pairing dimensions

Each package explicitly carries or evaluates:

- semantic redundancy;
- psychological complementarity;
- information gain;
- visual/text redundancy;
- Viewer Promise consistency;
- Hook Alignment;
- title claim validation;
- thumbnail claim validation.

Lexical overlap is checked deterministically, but zero-redundancy is not a
simplistic no-shared-words rule. Significant repeated information can trigger
REWORK while unavoidable shared terminology may remain acceptable.

### Diagnostic dimensions

Each pair stores separate 0–5 diagnostics for:

- `scroll_stop`;
- `clarity`;
- `curiosity`;
- `stakes`;
- `specificity`;
- `visual_simplicity`;
- `title_strength`;
- `complementarity`;
- `credibility`;
- `promise_alignment`;
- `hook_alignment`.

There is no aggregate viral score and no ranking or automatic winner.

### Hard validation

The configured hard rejection codes are:

- `unsupported_material_claim`;
- `factually_false_claim`;
- `thumbnail_misrepresents_video`;
- `title_misrepresents_video`;
- `evidence_conflict`;
- `prohibited_claim`.

Hard truth failures always override psychology scores.

Claim assessments use only approved evidence refs already attached to the paired
title or thumbnail component. The evaluator cannot borrow an unrelated approved
claim to justify another component.

Promise states include PASS, UNDERPROMISE, OVERPROMISE, WRONG_PROMISE,
DELAYED_ACKNOWLEDGEMENT and MISSING_PAYOFF. Overpromise, wrong promise and a
missing payoff become hard package failures. Underpromise or delayed
acknowledgement are repairable rework states.

Hook Alignment stores PASS / REWORK / FAIL and a reason. A non-PASS hook
alignment becomes targeted rework rather than silently changing the approved
script.

### Title-length policy

The preferred 45–60 character range remains guidance only. Titles beyond that
range are recorded as outside the preferred range but are not automatically
rejected.

### Resumability and artifact namespace

Validation is chunked by thumbnail, five title comparisons at a time. Current
validated chunks survive retries when their exact request hash is unchanged.

Mature artifacts are isolated under:

`packaging_engine/output/mature_packaging/`

This prevents Slice 26 from overwriting the legacy pre-script
`output/package_candidates.json`.

Primary artifacts include:

- `package_candidates.json`;
- `package_validation.json`;
- `promise_alignment.json`;
- pairing request/response/model-run directories.

### Slice 26 boundary

`PACKAGE_VALIDATION_READY` means every current 25-pair matrix has complete
PASS / REWORK / REJECT validation.

It does **not** mean a package has been accepted.

Slice 26 does not:

- choose a winner;
- approve a final title;
- approve a final thumbnail;
- render a thumbnail image;
- create A/B variants;
- unlock Format/Production.

Slice 27 adds the Final Packaging Gate on top of these validated hypotheses.

## Slice 27 — Final Packaging Gate + targeted rework

```text
PACKAGE_VALIDATION_READY
        ↓
Human Final Packaging Gate (one decision per format)
        ├─ ACCEPT one PASS package ──→ final package bundle per concept
        ├─ REWORK → title directions | thumbnail concepts | script branch
        └─ REJECT (holds Format until a package is accepted)
        ↓
FINAL_PACKAGING_APPROVED → Format planning (re-enabled)
```

`final_packaging_review.py` reads the complete current Slice 26 matrix. For each
format it lists every pair, PASS first, with its diagnostics, findings, Viewer
Promise and opening hook.

### Title shortlist (D-134)

The gate leads with a shortlist of 2–3 of the five titles, built by
`title_shortlist.py` from the pair validations. No model is called and no
viral score is produced. Titles are ranked in this order:

1. the title direction chosen at the Title Direction Gate;
2. more PASS pairs, meaning the title works with more thumbnails;
3. the mean of `title_strength`, `clarity`, `credibility` and
   `promise_alignment` over its PASS pairs;
4. `title_id`, so ties are stable.

A title with no PASS pair is not eligible. A title whose content words
overlap a shortlisted one at or above `near_duplicate_threshold` (0.5) never
takes a place. When fewer than `minimum` (2) qualify, the shortfall is stated
and not filled.

Each entry carries its reason, and each package is marked
`in_title_shortlist`. Shortlisted packages are listed first and the rest stay
reachable. Accepting a title outside the shortlist needs a note, and the
decision records `title_in_shortlist`. Settings live under `title_shortlist`
in `final_packaging_gate_config.json`.

### Accept

A package can be accepted only when:

- its Slice 26 status is in `acceptable_validation_statuses` (default `PASS`);
- its thumbnail image is approved and current at the Human Thumbnail Gate
  (`require_approved_thumbnail_image`, default on; render id
  `<video_id>--<thumbnail_id>`);
- the reviewer affirms every criterion in `final_packaging_gate_config.json`:
  title and thumbnail read as one unit, one clear promise, the opening hook
  confirms the click, the script delivers the promise, claims stay within
  approved evidence and, with images required, the approved image is the
  thumbnail.

The title wording is the validated wording. Changing it means reworking the
title directions, so every accepted title has passed Slice 26.

### Rework

Rework needs a target and an authoritative note. The note is tagged with the
format and routed to the layer that is weak:

| Target | Effect |
|---|---|
| `TITLE_DIRECTIONS` | Withdraws the accepted title-direction selection for the concept and writes the note into its title request (`reopen_for_rework`), exactly like Rework at the Title Direction Gate. Both formats regenerate. |
| `THUMBNAIL_CONCEPTS` | Records the note and the previous concepts in `output/thumbnail_concept_rework.json`. Only that format's thumbnail request changes, so only its concepts, pairs and renders regenerate. |
| `SCRIPT` | Submits Rework for that script branch at the Script Gate with the note. Everything downstream of the script regenerates. |

The automatic workflow then walks back through the regenerated stages to the
gate.

### Reject

Reject records that no package is acceptable for a format. It holds Format
planning. It stays in force until the matrix for that format changes or the
reviewer accepts a package.

### Staleness and the bundle

Every decision is bound to the package's content hash and, for images, the
approved image hash. A changed pair, matrix or image returns the format to
PENDING.

When every format of a concept is accepted, a final package bundle is written
to `output/mature_packaging/final_packages/<concept>.final_package.json`. It
holds the exact title, thumbnail text and concept, approved image, opening
hook, Viewer Promise, decision and provenance per format.

Format requests carry the bundle and its content hash, and a changed bundle
makes the Format request stale. Every decision is also archived under
`final_packaging_history/`. See D-099.

## Niche thumbnail conventions

Set `channel_niche` in `packaging_config.json` and run the niche thumbnail
study (`NICHE_THUMBNAIL_STUDY.md`) to give Slice 25 thumbnail concept requests
the niche's breakout-thumbnail conventions. Requests are unchanged while the
niche is unset or has no study for that format. See D-097.

Validated concepts can then be rendered into images for review; see
`production_engine/THUMBNAIL_RENDERING.md` and D-098.
