"""SSRF (Server-Side Request Forgery) protection utilities."""

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> None:
    """Block requests to private/internal networks.

    Raises ValueError if the URL targets a private, loopback, link-local,
    or reserved IP address, or uses a disallowed scheme.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"Scheme not allowed: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")

    for _family, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_loopback:
            continue  # allow localhost (local services like Ollama, own server)
        if ip.is_private or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"Requests to private/internal addresses are blocked: {hostname}")


async def ssrf_event_hook(request: httpx.Request) -> None:
    """Httpx event hook that validates every request URL (including redirects)."""
    validate_url(str(request.url))
