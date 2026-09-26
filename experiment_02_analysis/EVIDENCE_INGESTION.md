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
