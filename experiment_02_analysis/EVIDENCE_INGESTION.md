# Experiment 02 Evidence Ingestion

## Purpose

This layer turns source material already available to the project into stable,
citeable Experiment 02 evidence.

It is deliberately **offline**:

- no YouTube API calls;
- no transcript scraping;
- no video downloading;
- no thumbnail downloading;
- no LLM calls.

The user supplies the source files. The ingestion layer records provenance,
hashes the files, parses supported transcript formats, and creates stable
evidence IDs.

## Supported inputs

### Transcript

Supported file types:

- `.srt`
- `.vtt`
- `.txt`
- `.md`

SRT/VTT cues become timestamped evidence items such as:

`transcript.t000000000_000002500_0001`

Plain-text transcripts are split by paragraph:

`transcript.p0001`

### Thumbnail

A local thumbnail image can be registered with:

- file path;
- SHA-256 hash;
- MIME type; and
- an optional human observation.

If no observation is supplied, the file is marked
`REGISTERED_UNOBSERVED` and is **not** added as claim-supporting evidence.

### Opening frame

Handled the same way as the thumbnail.

### Structured notes

A JSON notes file supports:

- `visual_note`
- `timing_note`
- `audio_note`

Each note requires a non-empty observation and can include start/end seconds.

See:

`evidence_notes_template.json`

## Bundle manifest

Evidence ingestion is driven by one manifest per source video.

Start from:

`evidence_bundle_template.json`

Example:

```json
{
  "video_id": "abc123",
  "profile": "output/profiles_to_complete/abc123.json",
  "transcript": "evidence/abc123/transcript.srt",
  "thumbnail": {
    "path": "evidence/abc123/thumbnail.jpg",
    "observation": "Large gearbox image occupies most of the frame; short text appears at left."
  },
  "opening_frame": {
    "path": "evidence/abc123/opening_frame.jpg",
    "observation": "Opening frame shows the gearbox cutaway before the narrator explains it."
  },
  "notes": "evidence/abc123/evidence_notes.json"
}
```

Paths are resolved relative to the bundle manifest.

## Run

```powershell
python .\experiment_02_analysis\evidence_ingest.py --bundle ".\path\to\bundle.json"
```

The prepared source profile is not overwritten.

The enriched profile is written to:

`experiment_02_analysis\output\profiles_enriched\<video_id>.json`

An ingestion report is written to:

`experiment_02_analysis\output\ingestion_reports\`

## Provenance

Imported evidence records include source-file path and SHA-256 hash.

The enriched profile also records:

- bundle-manifest hash;
- original prepared-profile hash;
- registered source files; and
- imported evidence count.

This allows later analysis to trace a finding back to the exact source file
that was ingested.

## Important boundary

Registering a source file is not the same as observing a mechanism.

For example, a thumbnail file with no written visual observation is preserved
as source provenance but cannot support a creative finding.

Experiment 02 analysis still requires explicit evidence references and
appropriate evidence types.


## Automatic source acquisition

The offline ingestion boundary remains unchanged.

Approved Experiment 02 profiles can now be populated by a separate network
collector:

`source_acquisition/experiment_02_evidence.py`

Run:

~~~powershell
python .\source_acquisition\experiment_02_evidence.py --mode acquire
~~~

The collector uses `yt-dlp` only for:

- English subtitles / automatic captions;
- the video thumbnail; and
- source metadata (`.info.json`).

Normal caption acquisition passes `--skip-download`. If captions fail, the source-acquisition layer may temporarily download best-audio only, transcribe it locally with Whisper, and delete the temporary audio immediately after transcription.

A transcript/caption file is required before the collector calls the offline
ingestion layer. Thumbnail-only acquisition does **not** create an enriched
profile and therefore does not unlock analysis.

Downloaded source files and acquisition reports are written under:

`source_acquisition\output\experiment_02\<video_id>\`

The collector creates a normal evidence bundle and invokes
`evidence_ingest.py`. The existing ingestion rules still apply: an unobserved
thumbnail is registered as provenance but cannot support a creative finding.

Acquisition is idempotent. A current enriched profile whose ingestion provenance
matches the prepared-profile SHA-256 and contains transcript evidence is reused
without another network call.


## Visual structure acquisition

After transcript-backed source evidence is ready, an optional visual-structure
stage can add objective pacing evidence:

`source_acquisition/experiment_02_visual.py`

Run:

~~~powershell
python .\source_acquisition\experiment_02_visual.py --mode acquire
~~~

Requirements:

- `yt-dlp`
- `ffmpeg`

The visual stage asks `yt-dlp` only for a low-resolution stream URL. It does
not save the full video file. `ffmpeg` streams that rendition and:

- extracts an opening frame around 0.25 seconds;
- applies a fixed scene-change detector;
- retains a bounded set of timestamped representative scene frames; and
- writes timestamped `timing_note` evidence plus a whole-video detector
  summary.

The scene-change notes are objective detector outputs. They may support pacing
observations, but they are **not** semantic descriptions of what appears in the
frame.

The opening frame and retained scene frames are source artifacts for a later
human or multimodal-vision layer. Until an observation is attached, they do not
become claim evidence.

If visual acquisition fails after a valid transcript is available, the guided
workflow may continue with transcript-only analysis. A force-retry remains
available under **Tools & Diagnostics**.


## Human-gated visual observation review

After visual-structure sampling, Experiment 02 can prepare a bounded semantic
review set from the retained opening/scene frames:

`experiment_02_analysis/vision_review.py`

Prepare:

~~~powershell
python .\experiment_02_analysis\vision_review.py --mode prepare --provider auto
~~~

The default `auto` mode behaves as follows:

- if `EXPERIMENT_02_VISION_MODEL` names an installed model in local Ollama,
  the model proposes a factual frame description;
- otherwise the packet is prepared for human-only review.

The project `.env` may contain:

~~~text
EXPERIMENT_02_VISION_MODEL=
OLLAMA_HOST=http://127.0.0.1:11434
~~~

The Ollama host is intentionally restricted to localhost. No paid/cloud vision
provider is required.

### Evidence rule

A model proposal is **not evidence**.

Every retained frame remains `PENDING` until a human:

- accepts the proposed observation;
- edits it and accepts the edited observation; or
- rejects the frame.

Only accepted observations are written as Experiment 02 evidence.

Accepted scene-frame observations become `visual_note` evidence tied to the
actual frame file SHA-256. An accepted opening-frame observation becomes
`opening_frame` evidence. Rejected frames contribute no semantic evidence.

The review set is bounded to the opening frame plus at most eight evenly sampled
scene frames per source video, preventing the review UI from becoming another
long scrolling page.
