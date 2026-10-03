# Story / Script Engine

Flow:

```text
Verified Research
      ↓
Shared Story Plan
      ↓
Resolve Required Format Branches + Psychology Profiles
      ├── Long-form Script
      └── Shorts Script
              ↓
Human Script Gate — review each required branch
              ↓
Approved Script Bundle
              ↓
Format Production Planning
```

The engine consumes only `research_engine/output/verified_packages/*` packages
whose status is `READY_FOR_STORY_SCRIPT`.

## Responsibility split

**Story Plan owns structure and audience psychology.** It decides the story
question, opening-hook intent, ordered viewer journey, factual claim placement,
reveal/payoff, closing intent, viewer state and the primary psychology function
of each beat. It does not write final narration.

**Format-specific Script Drafts own wording.** The shared Story Plan is not the
final narration. The engine resolves the approved `format_intent` before
writing, then generates a separate script for each required branch.

- `long_form` prioritizes sustained curiosity, comprehension, explanation and
  meaningful delayed payoff.
- `short` prioritizes immediate swipe-defense, low cognitive branching, rapid
  meaningful progress and frequent micro-payoffs.

Each section cites one or more `source_story_beat_ids`. Factual `claim_ids`
must be available from those cited beats, so a branch may compress or combine
the shared story without escaping verified research.

## Audience psychology contract

The psychology layer is a planning aid, not a promise of virality and not a
license for manufactured drama.

The Story Plan must explicitly model:

- **viewer state** — what the viewer already knows, expects and wants resolved;
- **high-impact opening** — the first spoken line is planned around
  contradiction, surprising fact, stakes, expectation violation, specific
  curiosity or a bold specific promise;
- **immediate support** — material following the opening must justify,
  contextualize or begin proving it;
- **beat psychology** — one primary mechanism per beat: curiosity, prediction,
  tension, stakes, novelty, expectation violation, clarity or payoff;
- **cognitive load** — each beat states how to keep the explanation
  understandable rather than stacking unrelated ideas;
- **open-loop accounting** — every explicitly opened loop must later receive a
  payoff; unresolved fake hooks fail deterministic validation;
- **tension/release and payoff** — tension exists to advance understanding and
  the final payoff must satisfy the approved package promise.

There is no **universal** fixed hook or reset interval. Long-form has no fixed
timing target. Shorts currently carries two explicit starting hypotheses:
`hook_target_seconds = 3` and an attention/reward refresh window of roughly
`4–6` seconds. These are production hypotheses for the Learning Engine to test
against actual Shorts retention, not claimed physiological laws.

The high-impact opening rule is **truth constrained**. A factual opening may use
only Research Gate accepted claims. The Script Writer must not convert a valid
contradiction or curiosity gap into unsupported sensational language.

## Title contract

The approved Packaging title is immutable after Packaging. It is the viewer
promise the rest of the system must fulfill.

- Story Plan must return the exact approved title.
- Script Draft must return the exact approved title.
- A different title fails deterministic validation.
- Later Format, Voice Performance and Production stages may not silently
  rewrite it.

## Hard boundaries

- Only Research Gate accepted claims are available as factual support.
- Story Plan factual beats may reference only accepted `claim_id` values.
- Long-form must cover the full shared Story Plan; Shorts may compress or
  combine beats while preserving the core question and payoff.
- Every script section cites one or more source Story Plan beats.
- Script claim IDs must come from the cited Story Plan beats.
- Unknown claim IDs fail deterministic validation.
- Source-video wording, story, personality, footage and exact execution are not
  inputs for copying.
- FAIR remains free-only through the shared YouTube bridge.
- A model-validated draft is not production-ready until the Human Script Gate
  accepts it.

The Human Script Gate reviews each required format branch independently. It
checks package-promise delivery, factual scope, claim mapping,
originality/source independence, Story Plan fidelity, whether the opening is
both high-impact and truthful, whether the branch-specific psychology serves
viewer understanding, and payoff clarity.

A concept moves forward only when **all required branches** are accepted. The
gate then writes one provenance-bound approved script bundle containing the
separate immutable narrations. Identical branch scripts, or a Short that is only
a prefix/truncation of long-form narration, fail closed.

## Selective section rework

Selective script review uses one canonical runtime path:

```text
script_section_state.py
        ↓
script_section_service.py
        ↓
script_section_rework_runner.py
        ↓
script_section_apply.py
```

The browser reaches that path through `/api/script-section-review`. The
section-review system is separate from the whole-branch Human Script Gate, but
both protect the same Script Draft and approval bundle.

### Slice 1 — canonical section state

`script_section_state.py` creates a state artifact under
`script_section_states/` for one exact format-specific Script Draft. Stable
target IDs are:

- `hook:opening`;
- one `section:<section_id>` target for each generated section; and
- `closing:closing`.

Every target carries a deterministic `target_sha256`, ordinal, decision,
locked flag and optional rework metadata. The state carries the exact source
draft path/SHA-256, `state_version`, timestamps and an audit history.

Missing or duplicate section IDs fail closed. Target IDs that collide after
filesystem normalization also fail closed. `assert_state_matches_draft()`
rebuilds the target set from the current Script Draft and rejects stale or
tampered state.

Slice 1 does not change narration.

### Slice 2 — section decisions

The canonical section actions are:

- `ACCEPT` — marks the target `ACCEPTED` and locks it;
- `LOCK` — freezes the current target without accepting it;
- `UNLOCK` — unlocks it and returns an accepted target to `PENDING`;
- `REWORK` — marks an unlocked target `REWORK_REQUESTED`; and
- `CANCEL_REWORK` — returns a rework target to `PENDING`.

Rework accepts a bounded reason or custom instruction. The canonical custom
reason token is `CUSTOM`. A locked target cannot be reworked until it is
unlocked. Every state action is recorded in history and advances
`state_version`; script text is not changed by these actions.

`script_section_service.py` resolves all filesystem paths from logical
concept/format/target identity. The browser does not supply arbitrary draft or
state paths. Rework or unlock invalidates stale branch-level approval artifacts.

Section-state mutations and whole-branch Script Gate decisions use the same
in-process lock. Whole-branch `ACCEPT` also checks the canonical state and
fails while any target is `REWORK_REQUESTED`.

### Slice 3 — bounded rework request preparation

Slice 3 adds a distinct `PREPARE_REWORK_REQUEST` service action. It prepares
the request only:

- no FAIR/model call;
- no A/B/C generation;
- no Script Draft mutation.

The selected target must already be `REWORK_REQUESTED`. The request contains:

- the exact selected target text and immutable metadata;
- only the immediately previous and next targets as read-only context;
- locked target IDs;
- the human rework reason/custom instruction;
- only accepted claims already mapped to the selected target;
- only Story Plan beats referenced by that target, plus shared story question,
  opening intent, payoff intent and closing intent;
- the branch psychology contract/profile;
- the exact bound Channel Voice;
- approved package constraints.

Provenance binds the request to the exact Script Draft, canonical section-state
artifact, original Script Request and Human Script Gate review request. It also
records `state_version` and the selected `target_sha256`.

`assert_request_current()` verifies those source hashes and rebuilds the
expected request from trusted current artifacts. Manual request edits, changed
draft/state/review/script requests, a cancelled rework, a newly locked target or
a changed target hash all fail closed.

Request preparation and current-state validation share the canonical state
lock. If state changes while a FAIR call is in flight, the runner checks the
request again before accepting the returned alternatives and writes no
alternatives artifact from the stale result.

### Slice 4 — bounded A/B/C generation and integrity validation

`GENERATE_ALTERNATIVES` consumes the exact Slice 3 request and asks FAIR for
three candidate rewrites only. It never edits the Script Draft or section state.

The response contract is strict both in the schema handed to FAIR and in local
deterministic validation. The top-level response may contain only
`concept_id`, `format`, `target_id` and `alternatives`. Each alternative
must contain exactly:

- `alternative_id` — A, B or C in order;
- `replacement_text`;
- `change_summary`; and
- `claim_ids_used`.

`claim_ids_used` must exactly match the accepted claim IDs already mapped to
the selected target. A target with no mapped claims must return an empty list.
This field is validation metadata only; it cannot change Script metadata.

A deterministic numeric-fact guard rejects a candidate that introduces a
numeric value not already present in the original selected text or its bound
accepted claim statements. This is deliberately conservative and supplements,
rather than replaces, the normal accepted-claim and full-script validation
boundaries.

A/B/C must be distinct from one another and from the original target, and each
candidate still passes the source-overlap block.

The runner validates that the Slice 3 request is still current before FAIR and
again after FAIR returns. Human state changes while inference is in flight
therefore discard the returned result.

Validated alternatives are provenance-bound to:

- the exact Slice 3 request and SHA-256;
- the current validation-contract SHA-256;
- the exact saved model-response path and SHA-256;
- the Script Draft and section-state provenance already carried by Slice 3; and
- the provider/model identity.

Cached alternatives are not trusted merely because a prior model-run report says
`VALIDATED`. The cached model response is revalidated, the alternatives
artifact is rebuilt deterministically, and any mismatch fails closed as
`CACHED_ALTERNATIVES_INVALID` without making another model call.

Human selection resolves the expected model-response path deterministically from
concept/format/target identity rather than trusting a path stored in the
alternatives artifact. Before A/B/C can be selected, the artifact must still
match the exact validated model response and current validation contract.

Slice 4 generation is non-destructive: tests assert both the Script Draft bytes
and section-state bytes remain unchanged.

### Slice 5 — explicit human selection and safe replacement

Slice 5 applies only an explicit human choice: `ORIGINAL`, `A`, `B` or
`C`. No model or automatic stage may choose a replacement on the human's
behalf.

Selection revalidates the exact Slice 4 alternatives artifact/model response
before any destructive write. The selected target must still be
`REWORK_REQUESTED` and unlocked.

All selection mutations run under the same canonical in-process section-state
lock used by Human Script review actions. Concurrent A-vs-B choices, manual
edits or state changes therefore serialize; only the first valid selection can
commit.

For A/B/C:

- only the selected target text is replaced;
- all non-target target hashes must remain unchanged;
- the full Script validator runs before the draft is accepted;
- the previous Script Draft is saved as an exact byte-for-byte version file;
- the saved version SHA-256 must equal the parent draft SHA-256;
- the selected target becomes `ACCEPTED` and locked; and
- the Human Script Gate request is rebuilt for the new draft while stale
  branch approval is invalidated.

For `ORIGINAL`, the Script Draft hash must remain byte-identical. Only review
state/audit artifacts change: the target is accepted and locked without
incrementing the human script revision.

The selection audit records parent draft/state hashes, the exact Slice 3 request
and Slice 4 model-response hashes, selected replacement hash, claim IDs used,
reviewer, resulting state version and revision lineage.

A Slice 5 transaction snapshots every file selection can mutate before the
first write:

- Script Draft;
- canonical section state;
- alternatives artifact;
- Human Script Gate request;
- Human Script Gate response;
- approved script bundle; and
- previous-version destination when A/B/C is chosen.

Snapshots preserve exact bytes and record backup hashes. Rollback first
preflights every backup before restoring any file, preventing a corrupt backup
from causing a partial rollback. Files that did not exist before the
transaction are removed during rollback.

If the process is interrupted after writes begin, the next selection recovers
any `PREPARED` or `IN_PROGRESS` transaction **before** enforcing the
one-time-selection check. A half-written `selection` field therefore cannot
permanently block recovery.

Slice 5 does not alter Slice 4 alternatives generation. Manual free-text editing
remains a separate human action, though it shares the same section-state lock
and exact parent-version helper.

### Slice 5B — saved-version restore

Every selection or manual edit saves the parent draft as
`revision_NNNN.script_draft.json` (the revision it contains). Slice 5B lets the
reviewer list those saved versions and restore one.

- `list_saved_versions` returns version ID, revision, hash, edit type and a
  `compatible` flag, without exposing filesystem paths. A version is
  compatible only when it belongs to the same concept, format and exact script
  request (request hash and source).
- `RESTORE_VERSION` (section service and `/api/script-section-review` with
  `version_id`) restores a compatible version as a **new** revision: the
  current draft is saved first, the restored draft keeps the current request
  provenance, passes the full Script validator, records `RESTORE_VERSION`
  provenance, and resets section decisions. The Human Script Gate response and
  approved bundle are invalidated, and stale alternatives and rework requests
  for the branch are removed.
- Restoring a version identical to the current script, an unknown version, a
  malformed `version_id` or a version from a different script request is
  refused without changing anything.
- The restore runs under the same section-state lock and recoverable
  transaction backups as selection and manual edit; any failure rolls back.

There is no restore button in the Experiment UI yet; the action is available
through the section service and API.

### Existing downstream selective-rework capabilities

The repository already contains capabilities beyond Slice 5:

- human selection can keep Original or apply A/B/C;
- selected replacement changes only the chosen target and runs the normal full
  Script validator;
- prior drafts are versioned and destructive updates use recoverable
  transaction backups;
- manual target editing uses the same target-isolation and validation boundary;
- the local UI/API exposes logical section-review actions without accepting
  user-supplied artifact paths.

Those downstream capabilities remain separate from Slice 4 generation.

### Slice 6 — Human Script Gate selective-review UI

Slice 6 exposes the canonical section-review backend inside the existing Human
Script Gate. It does not add a second API or duplicate state model.

The selective-review pane now provides:

- compact target-level progress counts for accepted, pending, rework and locked
  targets;
- a target selector with clear decision/lock state;
- a `Next unresolved` control;
- direct `Accept + lock`, `Lock`, `Unlock`, `Request rework` and
  `Cancel rework` actions;
- a separate `Prepare rework request` button that exercises Slice 3 without a
  model call;
- `Generate A / B / C` for Slice 4;
- inline `Original / A / B / C` cards with claim provenance;
- a collapsible manual-edit control; and
- whole-script `Accept / Rework / Reject` controls kept separate below the
  target-level workflow.

Every section mutation is single-flight in the browser. While an action is in
progress, target navigation, section actions and whole-script decisions are
disabled. Backend locking and Slice 5 transaction protection remain the final
authority.

Client-side validation rejects empty/unchanged manual edits and incomplete
custom rework instructions before POSTing. Backend validation remains
authoritative.

Whole-script `Accept` is disabled while any canonical target is
`REWORK_REQUESTED` or the section state is stale, matching the backend
approval boundary.

After any section action, the UI reloads the current Human Script Gate branch
immediately and keeps the operator on the same concept/format. A selected A/B/C
replacement or manual edit therefore appears in the main script text
immediately instead of waiting for the periodic status refresh.

The comparison layout uses two columns on wider screens and collapses to one
column on small screens.

### Slice 7 — section-review completion becomes a real handoff contract

Selective review remains optional at the branch level. If a branch never
prepares canonical section state, the existing whole-script Human Script Gate
can still approve that branch directly.

Once canonical section state **is prepared**, however, it becomes part of the
approval contract. Whole-script `ACCEPT` is blocked until every target is:

- `ACCEPTED`; and
- locked.

A merely locked `PENDING` target is not resolved. A `REWORK_REQUESTED`
target is not resolved. This prevents an operator from entering selective review
and then bypassing unfinished targets with the branch-level Accept button.

When all required branches are accepted, the approved-script bundle records
per-branch selective-review lineage inside `approved_provenance`:

- whether selective review was prepared;
- canonical section-state path;
- exact section-state SHA-256;
- section-state version;
- target count; and
- ordered target ID / target SHA-256 lineage.

The Script Gate no longer treats the mere existence of an approved bundle as
production readiness. It revalidates the current branch review responses,
Script Draft hashes and any prepared section-state lineage. A section-state
change after approval therefore removes that concept from
`production_ready_concept_ids` even if an old approved bundle file still
exists.

Older approved bundles remain compatible when no selective section review was
ever prepared. If a canonical section-state file now exists, the old bundle is
considered stale until the branch is reviewed and approved again.

The Human Script Gate UI mirrors the same rule: after section review is
prepared, whole-script Accept remains disabled until all targets are accepted
and locked.

Format is the receiving enforcement boundary. It independently verifies any
prepared section-review provenance before creating a Format Request:

- the section-state path must be the canonical path for concept/format;
- the stored section-state SHA-256 must match;
- the state must point to the canonical Script Draft;
- the Script Draft SHA-256 must still match the state binding;
- every target must remain accepted and locked;
- state version and target count must match; and
- ordered target ID/hash lineage must match.

The verified section-review summary is copied into the Format Request
provenance. Therefore a stale or manually redirected section-state cannot cross
from Script approval into Format planning.
