# Niche Thumbnail Study

## Purpose

Generic title/thumbnail guidance is a starting hypothesis. Niche
conventions are stronger local evidence. This study tabulates what the
breakout thumbnails in one niche + format actually look like, compares them
with the Slice 25 thumbnail contract and D-096 title guidance, and feeds the
result into Slice 25 thumbnail concept requests.

It is descriptive and correlational. It does not measure or predict CTR.

## Stages

All output goes to `packaging_engine/output/niche_thumbnails/<niche>__<format>/`.

~~~powershell
python .\packaging_engine\niche_thumbnail_study.py --mode select   --niche automotive_racing --format long_form
python .\packaging_engine\niche_thumbnail_study.py --mode acquire  --niche automotive_racing --format long_form
python .\packaging_engine\niche_thumbnail_study.py --mode measure  --niche automotive_racing --format long_form
python .\packaging_engine\niche_thumbnail_study.py --mode annotate --niche automotive_racing --format long_form
#   edit annotations.json, set each reviewed item to CONFIRMED
python .\packaging_engine\niche_thumbnail_study.py --mode tabulate --niche automotive_racing --format long_form
~~~

| Stage | Network | What it does |
|---|---|---|
| `select` | no | Reads Experiment 01 `raw_results.json` (sources in `niche_thumbnail_config.json`, or `--source`). Keeps `ON_INTENT` videos of the niche and format, ranks by outlier-reliability tier, then channel-relative outlier ratio, then views, with at most 2 per channel. Targets 30; below 20 the study is `INSUFFICIENT_SAMPLE`. |
| `acquire` | yes | Downloads each public thumbnail from `https://i.ytimg.com/vi/<id>/` (`maxresdefault.jpg`, falling back to `hqdefault.jpg`). Records URL, SHA-256 and size. Re-runs reuse files whose hash still matches. |
| `measure` | no | Uses `ffprobe` for resolution and `ffmpeg` to decode a 64x36 RGB grid, then computes deterministic metrics: background tone (border luminance), centre lift, bright-subject-on-dark flag, luminance spread, saturation, hue-family shares, dominant/secondary hue family, warm share, and whether the image meets 1280x720. |
| `annotate` | local only | Creates or refreshes `annotations.json` without overwriting existing work. Humans record `text_overlay` (exact text), `focal_subject`, `focal_subject_type`, `visual_element_count`, `visual_cue_count`, `face_present`. `--draft-model <ollama model>` pre-fills PENDING items from a local Ollama vision model as `DRAFT`. |
| `tabulate` | no | Writes `tabulation.json`, `tabulation.csv` and `REPORT.md`. |

## What is tabulated

- **Color** (all measured thumbnails): background tone distribution, dominant
  hue families, the two most crowded hue families, accent differentiation
  candidates (warm or blue families that dominate under 10% of the niche),
  median warm share, contrast and saturation, bright-subject-on-dark share,
  share meeting 1280x720.
- **Text and focal subject** (human-CONFIRMED annotations only): word-count
  buckets (0 / 1-2 / 3-5 / 6+), share of text that repeats the title, focal
  subject types, face share, median element and cue counts.
- **Titles**: median title length.
- **Rule comparison**: for each packaging rule, the share of the niche that
  conforms. Thresholds come from the live `packaging_config.json`: at most
  `maximum_meaningful_visual_elements` elements and `maximum_text_words` words
  (Slice 25), long-form titles of 45-60 characters (D-096), Shorts titles within
  `short_title_contract.max_chars`. The overlap and arrow/circle limits live
  under `comparison` in `niche_thumbnail_config.json`. At least 50% (`convention_share`) is `NICHE_FOLLOWS`, otherwise
  `NICHE_DIVERGES`.

The study is `COMPLETE` when at least 20 thumbnails are measured and 20
annotations are confirmed; otherwise `PARTIAL`.

## Packaging integration

Set `channel_niche` in `packaging_config.json` (for example
`"automotive_racing"`). Slice 25 thumbnail concept requests for a format whose
tabulation exists then carry `niche_thumbnail_conventions` and an instruction to
follow a convention only where it does not conflict with the thumbnail
contract, and to choose colours outside the crowded hue families.

With `channel_niche` left `null`, or with no study for that format, requests
are byte-identical to before, so existing concepts stay current. Setting the
niche, or re-tabulating with different results, makes affected concept
requests stale so they are regenerated.

The thumbnail renderer also reads `channel_niche` to place real niche
thumbnails in its mock feed and to flag an accent in a crowded hue family.

## Boundaries

- DRAFT model annotations are never tabulated.
- Thumbnail images are stored only under ignored `output/`.
- The study describes the niche's breakout videos. It does not show that any
  feature caused a video's performance. See D-097.
