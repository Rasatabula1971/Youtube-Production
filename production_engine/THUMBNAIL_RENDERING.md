# Thumbnail Rendering

## Purpose

Turns each human-approved package into an uploadable 1280x720 thumbnail built
from one locked channel template, then shows it at phone size and in a mock
feed beside the niche's breakout thumbnails before a human gate approves it.

## Locked template, varied subject

`thumbnail_template.json` holds the roughly 80% that stays fixed across
videos:

- 1280x720 canvas and a 2 MB JPEG ceiling;
- subject zone on the right, text zone on the left;
- dark blurred-subject background with a scrim behind the text;
- bold font, uppercase, thick black outline and drop shadow;
- last text line and an underline bar in the accent colour;
- optional logo position;
- a timestamp safe zone (bottom right) that text and logo may not enter.

The template is validated on load. Changing it invalidates earlier renders
for review purposes.

Per video, only three things vary:

- the **subject image**, supplied with provenance;
- the **accent colour**, pre-filled from the package palette (`"cold blue"`
  becomes the template's blue) and editable;
- the **text overlay**, taken verbatim from the approved package. It cannot
  be edited here; changing it means reworking the package.

## Experiment UI

Once a package is approved at the Packaging Gate, **Analyze & Create** shows the
Human Thumbnail Gate panel for each approved package:

- enter the subject image path, source tier, licence, source URL, attribution
  and accent, then **Save subject** (this creates or refreshes the render spec);
- **Render** runs the `thumbnail_render` job; **Layout preview** runs
  `thumbnail_render_preview` for packages without a subject image;
- review the full-size render, the 360px and 168px previews, a dark/light mock
  feed beside the niche study's breakout thumbnails, the approved package and
  the advisories;
- tick the five criteria and Accept, Rework (note required) or Reject.

Accept is disabled for placeholder previews and stale renders. Changing the
subject or accent after a decision returns the package to PENDING until it is
re-rendered and reviewed; a re-render that changes the image withdraws an
earlier approval. Gate edits are locked while a pipeline job is running, like
the other human gates. Thumbnail work is not part of the automatic machine
workflow because it needs a human-supplied subject image.

## Commands

~~~powershell
python .\production_engine\thumbnail_render.py --mode prepare
#   fill subject_image in production_engine\output\thumbnails\<package_id>\render_spec.json
python .\production_engine\thumbnail_render.py --mode render
python .\production_engine\thumbnail_render.py --mode render --placeholder   # layout preview without a subject
python .\production_engine\thumbnail_render.py --mode review --response .\my_thumbnail_review.json
~~~

`prepare` reads `packaging_engine/output/approved_packages.json` and keeps any
human edits (accent, subject image) when it refreshes a spec.

## Subject image provenance

`subject_image.source_tier` must be one of the tiers the template allows:
own library, free commercial licence, public domain, allowed Creative Commons,
or generated (motion graphic, cheap AI, Higgsfield). Editorial excerpts and
unknown sources are refused. Non-own sources need a licence; licensed web
sources also need a source URL. A competitor's thumbnail is never a valid
subject.

## Outputs

`production_engine/output/thumbnails/<package_id>/`:

| File | Contents |
|---|---|
| `thumbnail.jpg` | 1280x720 upload, at most 2 MB |
| `phone_home_360.png`, `phone_suggested_168.png` | phone-size previews |
| `feed.html` | mock mobile feed, dark and light, home (360px) and suggested (168px), with your thumbnail inserted among up to 8 niche breakout thumbnails from the niche study, a timestamp badge, and titles clamped to two lines |
| `render_report.json` | layout (lines, font size), hashes, colour metrics, subject/background luminance, advisories |

Text layout measures each candidate line with the real font, then picks the
1-3 line split that allows the largest size inside the text zone. If the text
needs less than the template's minimum size, the render is `BLOCKED` and the
package text must be reworked.

## Advisories (non-blocking)

| Rule | Meaning |
|---|---|
| `PHONE_TEXT_TOO_SMALL` | Text is under 12px tall in the 168px preview |
| `BACKGROUND_NOT_DARK` | Area outside the subject zone is brighter than the template target |
| `SUBJECT_NOT_BRIGHTER` | Subject zone is not clearly brighter than the background |
| `ACCENT_IN_CROWDED_HUE` | Accent falls in one of the niche study's most common hue families |
| `PLACEHOLDER_SUBJECT` | Layout preview only |

## Human Thumbnail Gate

Start from `thumbnail_review_response_template.json`. ACCEPT requires every
criterion:

- `matches_approved_package`
- `single_focal_point`
- `readable_at_phone_size`
- `stands_out_in_feed`
- `subject_image_rights_verified`

ACCEPT is refused for placeholder renders and for stale renders (approved
package, template, render spec or image changed since rendering). REWORK
requires a note. An accepted thumbnail is recorded in
`production_engine/output/approved_thumbnails/<package_id>.json` with its hash;
a later REWORK or REJECT removes that record. See D-072.

## Requirements

`ffmpeg`/`ffprobe` with `drawtext` (libfreetype), and a bold TrueType font.
The template searches Impact/Arial Bold (Windows, macOS) and DejaVu/Liberation
Sans Bold (Linux). Set `THUMBNAIL_FONT_FILE` to use a specific font; once
chosen, keep it fixed so the template stays consistent.
