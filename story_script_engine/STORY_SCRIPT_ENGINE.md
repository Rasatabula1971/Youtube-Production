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

## Selective section rework — Slice 1 contract

Selective rework is being added incrementally. Slice 1 adds only deterministic
review state; it makes no model call and does not change Human Script Gate
behavior yet.

Each exact script draft can be mapped to stable review targets:

- `hook:opening`;
- one `section:<section_id>` target for every generated script section; and
- `closing:closing`.

The state is SHA-256 bound to the exact draft. Duplicate or missing section IDs
fail closed. Human actions may ACCEPT, LOCK, UNLOCK, request REWORK, or cancel a
pending rework request. ACCEPT locks the target. A locked target cannot be
reworked until explicitly unlocked.

Rework requests record a bounded reason plus an optional human instruction.
They do **not** overwrite narration. Later slices will generate alternatives for
only the selected target and require a separate human choice before any draft
replacement occurs.

If the source draft changes after section state is created, the old state is
stale and cannot be applied silently.

### Slice 2 — bounded alternatives

A target marked `REWORK_REQUESTED` can now produce a separate rework request.
The request includes the selected text, immutable target metadata, the accepted
claims and Story/Channel constraints, plus only the immediately adjacent
read-only context needed to preserve flow.

FAIR returns exactly three candidates: `A`, `B`, and `C`. The response may
contain replacement wording and a short change summary only; it cannot alter
section IDs, source Story beats, claim IDs, psychology labels, reward labels or
locked neighbors.

Alternative generation is still non-destructive. The output artifact keeps the
original text and records `selection: null`. No generated alternative replaces
the script until a later Human Selection slice explicitly applies one.

The rework request is bound to the exact script draft, exact section-state file,
state version, target hash and original script request. Any intervening change
makes the request stale before a model call is allowed.

### Slice 3 — human selection and safe replacement

Generated alternatives still cannot edit a script by themselves. A human must
explicitly choose `ORIGINAL`, `A`, `B`, or `C`.

Choosing `ORIGINAL` keeps the draft bytes unchanged and marks that target
accepted/locked. Choosing A/B/C changes only the selected text field. All other
targets, including every locked target, must retain the same deterministic
target hash. The selected replacement is then run through the normal full-script
validator before it can be written.

Before a replacement, the prior draft is saved under `script_versions/`.
The section state is rebased to the new draft hash, the selected target becomes
accepted/locked, and existing Human Script Gate responses/approved bundles are
invalidated so stale approval cannot flow downstream.

Selection uses a recoverable transaction journal with backups of the draft,
section state and alternatives artifact. A failed/interrupted operation rolls
those core artifacts back instead of leaving a partially applied replacement.

### Slice 4A — local UI service/API boundary

The local control UI reaches selective rework through
`/api/script-section-review`. Browser requests provide only logical
`concept_id`, `format`, `target_id`, action/reason, and selection values.
They never provide draft, state, request, alternatives, version or transaction
filesystem paths.

The service resolves those paths from project-owned output directories and
verifies the draft identity after filesystem normalization. Target IDs that
would collide after filename normalization are rejected when section state is
created.

The endpoint supports preparing section state, target accept/lock/unlock/rework,
bounded alternative generation, and explicit alternative selection. Rework or
unlocking an accepted target invalidates any stale branch response and approved
script bundle immediately.
