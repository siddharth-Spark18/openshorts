# Thumbnail Studio (`thumbnail.py`, `/api/thumbnail/*`)

## Titles

Titles come from the transcript plus 10 frames at 1024px, never the whole video
(an hour of video is ~1M tokens for a text task). Two calls: a 25-title
brainstorm across fixed styles, then a critic that scores, dedupes by angle and
returns 10, each paired with a 1-4 word `thumbnail_text` that complements the
title rather than repeating it. Rules baked in: payoff inside 50 characters
(phones cut there), keyword in the first 3 words, same language as the
transcript.

Text model is `GEMINI_MODEL_THUMBNAIL` (default `gemini-3.7-flash`), deliberately
not `GEMINI_MODEL`: flash-lite is fine for a closed-choice layout pick and
visibly worse at creative titles. Image model is `GEMINI_IMAGE_MODEL` (default
`gemini-3.1-flash-image`).

## Images

Thumbnails are `count` **different concepts**, not one prompt repeated: a text
call designs each (hook text, side for the text, palette, scene prompt), then one
image call per concept in parallel. By default (`burn_text=true`) the image model
leaves that side as negative space and PIL sets the text in Anton with a black
stroke, so accents and spelling are never wrong; the `AI painted` toggle lets the
model render the text itself. Every output is cover-cropped to 1280x720 and
saved under YouTube's 2 MB limit.

`GET /api/thumbnail/frames/{session}` scores sampled frames by face area and
sharpness (MediaPipe + Laplacian), keeps them spread across the runtime, and the
dashboard offers them as the person reference so the thumbnail shows the creator;
an uploaded face photo still wins.

## Sources and limits

A link given to `/api/thumbnail/upload` or `/analyze` goes through
`_validate_source_url` like `/api/process`, and in cloud mode is probed
(hourly probe cap, no per-GB proxy past `PAID_PROXY_DAILY_MB`) and reserved
**before** anything downloads it. The download then runs in a worker thread
with the same budget decision and its paid bytes go to the proxy ledger. A
source (link or file) over `THUMBNAIL_MAX_SOURCE_MINUTES` (180) is refused with
413. Transcription costs one minute per `THUMBNAIL_SOURCE_MINUTES_PER_CHARGED`
(10) source minutes, never less than `TRANSCRIBE_MINUTES`; `/analyze` on a
source it transcribes itself adds that to its own minute.

Refinement and description calls are bounded: message/title length, the last
`THUMBNAIL_CONVERSATION_MAX_TURNS` chat turns sent back, refinements per
session, calls per user and hour, and a free account at zero minutes can only
keep working on a session it already paid for (`metered`). All limits live in
`cloud/config.py` and are env-overridable.

Transcribing in the API process (thumbnails, `/api/subtitle` on a dubbed clip)
must end with `transcribe_backends.release_models()`, or the ASR model stays
resident in uvicorn (see `jobs-and-deploys.md`).
