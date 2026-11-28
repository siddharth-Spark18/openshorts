"""Connect-time SSRF guard (ssrf_guard.py).

The submit-time check (security_utils.assert_public_url) only sees the URL the
caller sent. yt-dlp follows redirects and resolves every host again when it
connects, so a public page that redirects inside the network, or a DNS answer
that changes after the check, got past it. Inside ``guarded()`` name
resolution itself refuses non-public addresses on that thread.
"""
import http.server
import socket
import threading

import pytest

import ssrf_guard


def test_private_names_do_not_resolve_inside_the_guard():
    with ssrf_guard.guarded():
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("localhost", 80)
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("127.0.0.1", 80)
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("169.254.169.254", 80)
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("100.64.0.1", 80)


def test_nothing_changes_outside_the_guard():
    ssrf_guard.install()
    assert socket.getaddrinfo("127.0.0.1", 80)
    with ssrf_guard.guarded():
        pass
    assert socket.getaddrinfo("127.0.0.1", 80)


def test_guard_is_per_thread():
    seen = {}

    def other():
        seen["infos"] = socket.getaddrinfo("127.0.0.1", 80)

    with ssrf_guard.guarded():
        t = threading.Thread(target=other)
        t.start()
        t.join()
    assert seen["infos"]


def test_configured_infrastructure_hosts_still_resolve(monkeypatch):
    monkeypatch.setenv("STATIC_PROXY_URLS", "http://user:pw@127.0.0.1:3128, http://10.0.0.5:8080")
    monkeypatch.setenv("BGUTIL_BASE_URL", "http://localhost:4416")
    with ssrf_guard.guarded():
        assert socket.getaddrinfo("127.0.0.1", 3128)
        assert socket.getaddrinfo("localhost", 4416)


def test_public_addresses_pass():
    with ssrf_guard.guarded():
        assert socket.getaddrinfo("8.8.8.8", 443)


def test_external_downloader_urls_are_checked():
    from security_utils import UnsafeURLError
    with pytest.raises(UnsafeURLError):
        ssrf_guard.assert_public_urls(
            {"formats": [{"url": "http://169.254.169.254/latest/meta-data"}]})
    with pytest.raises(UnsafeURLError):
        ssrf_guard.assert_public_urls({"url": "http://127.0.0.1:8000/x.m3u8"})
    ssrf_guard.assert_public_urls({"formats": [{"url": "https://8.8.8.8/v.mp4"}]})


class _Recorder(http.server.BaseHTTPRequestHandler):
    hits = []
    location = None

    def do_GET(self):  # noqa: N802
        type(self).hits.append(self.path)
        if type(self).location:
            self.send_response(302)
            self.send_header("Location", type(self).location)
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"internal secret")

    def log_message(self, *a):
        pass


def _serve(handler):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_yt_dlp_redirect_into_the_network_is_not_followed(monkeypatch):
    """A page the caller may reach (allowlisted here to stand in for a public
    host) redirects to an internal one: yt-dlp must not reach the target."""
    yt_dlp = pytest.importorskip("yt_dlp")

    class Internal(_Recorder):
        hits = []
        location = None

    class Entry(_Recorder):
        hits = []

    internal = _serve(Internal)
    Entry.location = f"http://localhost:{internal.server_port}/latest/meta-data"
    entry = _serve(Entry)
    monkeypatch.setenv("SSRF_ALLOW_HOSTS", "127.0.0.1")
    try:
        opts = {"quiet": True, "no_warnings": True, "skip_download": True,
                "retries": 0, "extractor_retries": 0, "socket_timeout": 5}
        with ssrf_guard.guarded(), yt_dlp.YoutubeDL(opts) as ydl:
            with pytest.raises(Exception):
                ydl.extract_info(f"http://127.0.0.1:{entry.server_port}/video", download=False)
        assert Entry.hits, "the entry page was never fetched; the test proves nothing"
        assert Internal.hits == []
    finally:
        internal.shutdown()
        entry.shutdown()
