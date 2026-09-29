# Production Engine

Stage 07 begins after the Human Format Gate accepts a format plan.

The first implemented production slice is the **Visual Acquisition + Cost
Router**. It is intentionally offline. It does not search the web, download
media, call an AI model, or spend credits.

## Flow

```text
Format Gate approved plan
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

The order is a cost policy, not a claim that any source is automatically legal
to use. A short clip is never treated as permission merely because it is short.

## Pre-monetization budget

The default configuration targets no more than **US$5** of paid visual
generation per video and hard-stops automated paid visual routing at **US$10**.
These are operating constraints for channel testing, not permanent production
rules.

The budget can be changed later without changing the manifest schema.

## Third-party excerpts

An `EDITORIAL_EXCERPT` is never auto-selected. It remains
`HUMAN_REVIEW_REQUIRED` until the later source/copyright/licensing gate confirms
that the intended use is acceptable in context.

The system records provenance so a reviewer can inspect:

- source URL or local path;
- licence/reference information;
- commercial-use flag when known;
- attribution requirement when known;
- intended duration;
- the script/format beat the asset supports.

There is deliberately no "three-second rule" in the code.

## Commands

Prepare manifests from accepted format plans:

```bash
python production_engine/visual_acquisition.py --mode prepare
```

Re-evaluate manifests after candidate assets have been added:

```bash
python production_engine/visual_acquisition.py --mode route
```

## Output

```text
production_engine/output/
├── visual_manifests/
│   └── <concept>.<format>.visual_manifest.json
└── visual_summary.json
```

Each format beat becomes one visual requirement. Later acquisition adapters can
append candidate assets to a requirement without changing its provenance-bound
identity.

## Higgsfield

Higgsfield remains the paid premium fallback for generated visuals and the
planned narration renderer. It is no longer the default visual source. Paid
generation happens only after cheaper acceptable routes have been exhausted.
