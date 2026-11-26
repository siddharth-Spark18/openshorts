"""yt-dlp client selection for YouTube, shared by the download (``main.py``)
and the duration probe (``cloud/metering.py``) so the two cannot drift.

Why the client list is explicit. With account cookies yt-dlp's defaults are
``tv_downgraded`` + ``web``, and for a share of videos both come back
UNPLAYABLE / SABR-only, which surfaces as "Video unavailable" with no
formats. That looked like an IP ban (it also happened on every static ISP IP)
and for a week sent ~26 downloads a week to the per-GB proxy, which then
downloaded 360p through the same dead client list. Measured on 6-sep-2026
inside the prod container, same static proxy, same video:

    cookies + default clients            -> Video unavailable
    cookies + mweb (+ PO token)          -> 1080p
    no cookies + default clients         -> 1080p
    cookies + default,mweb (+ PO token)  -> 1080p (also on a video that worked)

``mweb`` needs a GVS PO token for its https formats, which the bgutil
provider mints as long as the webpage is NOT skipped (``player_skip:
webpage`` drops the account's Data Sync ID and the token request fails).
The old fallback list (``tv_embed``, ``android``) is gone from yt-dlp: the
first is "unsupported", the second is skipped whenever cookies are present.
"""

HD_CLIENTS = ["default", "mweb"]


class NotASingleVideo(ValueError):
    """The URL is a YouTube page that is not one video (search, playlist,
    channel). Raised before yt-dlp ever sees it, by the probe and the
    download alike."""


def youtube_non_video_reason(url):
    """Why this YouTube URL is not a single video, or None if it is one.

    A search page or a bare playlist is walked entry by entry by yt-dlp even
    with ``noplaylist`` (that option only strips the ``list=`` off a
    ``watch`` link). Measured in the prod container on 17-sep-2026: a
    ``results?search_query=`` URL held the probe's executor thread for
    2220 s and still failed on an entry that "premieres in 4 days", after
    the same URL had paid the per-GB proxy three times in a day. So the
    check is by path, up front and free: nothing that is not one video is
    worth a single request.
    """
    from urllib.parse import urlparse, parse_qs
    try:
        parts = urlparse(url or "")
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if host == "youtu.be":
        return None if parts.path.strip("/") else "youtu.be link without a video id"
    if not (host == "youtube.com" or host.endswith(".youtube.com")):
        return None
    path = parts.path.rstrip("/") or "/"
    if path == "/watch":
        return None if parse_qs(parts.query).get("v") else "a watch page without a video id"
    first = path.split("/")[1] if path != "/" else ""
    if first in ("shorts", "live", "embed", "v", "e"):
        return None
    if first == "results":
        return "a search results page, not a video"
    if first == "playlist":
        return "a playlist, not a video; open one video in it and paste that link"
    if first.startswith("@") or first in ("channel", "c", "user"):
        return "a channel page, not a video"
    if first in ("feed", "", "gaming", "music"):
        return "a YouTube page with no video in it"
    return None


def pot_provider_args(bgutil_http, bgutil_script):
    """Extractor args selecting the PO token provider (bgutil http or script)."""
    if bgutil_http:
        return {"youtubepot-bgutilhttp": {"base_url": [bgutil_http]}}
    if bgutil_script:
        return {"youtubepot-bgutilscript": {"script_path": [bgutil_script]}}
    return {}


def hd_extractor_args(bgutil_http, bgutil_script):
    """Extractor args for the HD attempt, or None when no PO token provider
    is configured (the HD path needs one; the plan then skips it)."""
    provider = pot_provider_args(bgutil_http, bgutil_script)
    if not provider:
        return None
    return {**provider, "youtube": {"player_client": list(HD_CLIENTS)}}


def fallback_extractor_args(bgutil_http, bgutil_script):
    """Extractor args for the conservative attempt: same live client list,
    the provider when there is one, and never ``player_skip`` (see module
    docstring). Without a provider mweb still serves the progressive 360p
    format, which is enough for a probe and better than no download."""
    return {**pot_provider_args(bgutil_http, bgutil_script),
            "youtube": {"player_client": list(HD_CLIENTS)}}


def download_source(url, output_dir, options, fmt, progress_hook, sanitize):
    """Extract once and atomically publish the MP4 after post-processing."""
    import os
    from pathlib import Path
    import tempfile
    import yt_dlp

    with tempfile.TemporaryDirectory(dir=output_dir) as stage:
        opts = {
            **options, "format": fmt, "outtmpl": os.path.join(stage, "source.%(ext)s"),
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}],
            "progress_hooks": [progress_hook],
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        title = sanitize(info.get("title") or "video").strip(".") or "video"
        result = Path(stage) / "source.mp4"
        if not result.is_file() or not result.stat().st_size:
            raise RuntimeError("Downloader did not produce an MP4.")
        result.replace(Path(output_dir) / f"{title}.mp4")
        return title
