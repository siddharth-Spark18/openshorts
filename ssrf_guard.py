"""Connect-time SSRF guard for fetches that follow redirects on their own.

``security_utils.assert_public_url`` checks the URL a caller hands us, once,
before the fetch. yt-dlp then follows HTTP redirects, reads URLs out of the
pages it extracts (the generic extractor) and resolves every host again when
it connects, so the checked URL is not the only one it ends up talking to: a
public page that 302s to a private address, or a hostname whose DNS answer
changes between the check and the connect, gets past a submit-time check.

The guard sits where every one of those connections has to pass: name
resolution. Inside ``with guarded():`` this thread's ``socket.getaddrinfo``
only returns globally routable addresses, so a redirect, an embedded URL or a
rebinding answer that points inside the network fails to resolve instead of
being fetched, and the address that gets connected is the one that was
checked. Outside the block (database, internal services, everything else in
the process) nothing changes.

Hosts the deployment itself configures (download proxies, the PO-token
provider) may legitimately be private; they are read from their env vars and
let through, plus anything listed in ``SSRF_ALLOW_HOSTS``.

Name resolution done by another program (ffmpeg, node) is out of reach of a
Python hook; ``assert_public_urls`` covers the URLs handed to those.
"""
from __future__ import annotations

import contextlib
import os
import socket
import threading
from urllib.parse import urlparse

from security_utils import _ip_is_public, assert_public_url

_state = threading.local()
_original_getaddrinfo = socket.getaddrinfo
_install_lock = threading.Lock()
_installed = False

# Env vars whose URLs name infrastructure the deployment chose on purpose.
_ALLOW_ENV = ("PROXY_URL", "STATIC_PROXY_URLS", "BGUTIL_BASE_URL", "SSRF_ALLOW_HOSTS")


class BlockedAddressError(socket.gaierror):
    """A guarded lookup that only resolved to non-public addresses."""


def _host_of(item: str):
    item = item.strip()
    if not item:
        return None
    try:
        return urlparse(item if "://" in item else f"//{item}").hostname
    except ValueError:
        return None


def allowed_hosts() -> set:
    hosts = set()
    for var in _ALLOW_ENV:
        for item in os.environ.get(var, "").split(","):
            host = _host_of(item)
            if host:
                hosts.add(host.lower().rstrip("."))
    return hosts


def active() -> bool:
    return getattr(_state, "depth", 0) > 0


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    infos = _original_getaddrinfo(host, port, *args, **kwargs)
    if not active() or host is None:
        return infos
    name = host.decode() if isinstance(host, (bytes, bytearray)) else str(host)
    name = name.strip("[]").lower().rstrip(".")
    if not name or name in allowed_hosts():
        return infos
    public = [info for info in infos if _ip_is_public(info[4][0])]
    if not public:
        raise BlockedAddressError(
            socket.EAI_NONAME, f"{name} does not resolve to a public address")
    return public


def install():
    """Wrap ``socket.getaddrinfo`` once per process. Inert until ``guarded()``."""
    global _installed
    with _install_lock:
        if _installed:
            return
        socket.getaddrinfo = _guarded_getaddrinfo
        _installed = True


@contextlib.contextmanager
def guarded():
    """Only public addresses resolve on this thread for the duration."""
    install()
    _state.depth = getattr(_state, "depth", 0) + 1
    try:
        yield
    finally:
        _state.depth -= 1


def assert_public_urls(info) -> None:
    """Check every URL an extracted yt-dlp ``info`` would hand to an external
    downloader (ffmpeg resolves and redirects on its own, past the hook)."""
    if not isinstance(info, dict):
        return
    seen = set()
    for fmt in [info] + list(info.get("formats") or []) + list(info.get("requested_formats") or []):
        if not isinstance(fmt, dict):
            continue
        for key in ("url", "manifest_url", "fragment_base_url"):
            url = fmt.get(key)
            if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in seen:
                seen.add(url)
                host = (urlparse(url).hostname or "").lower().rstrip(".")
                if host and host in allowed_hosts():
                    continue
                assert_public_url(url)
