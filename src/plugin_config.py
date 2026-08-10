"""Helpers for generating browser plugin configuration."""

import re
from typing import Optional


_HOST_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
_IPV4_OCTET = r"(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
_HOST_RE = re.compile(
    rf"^(?:"
    rf"(?P<ipv4>(?:{_IPV4_OCTET}\.){{3}}{_IPV4_OCTET})"
    rf"|(?P<hostname>(?:{_HOST_LABEL}\.)*{_HOST_LABEL})"
    rf")(?:\:(?P<port>\d{{1,5}}))?$"
)


def sanitize_plugin_host_header(host_header: str) -> Optional[str]:
    """Return a validated host[:port] suitable for a connection URL."""
    normalized = (host_header or "").strip()
    normalized = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", normalized)
    normalized = normalized.split("/", 1)[0]

    match = _HOST_RE.fullmatch(normalized)
    if not match:
        return None

    # A dotted numeric value must satisfy the strict IPv4 branch rather than
    # being accepted as a syntactically valid hostname.
    hostname = match.group("hostname")
    if hostname and re.fullmatch(r"\d+(?:\.\d+){3}", hostname):
        return None

    port = match.group("port")
    if port is not None and not 1 <= int(port) <= 65535:
        return None

    return normalized


def build_plugin_connection_url(
    host_header: str,
    server_host: str,
    server_port: int,
) -> str:
    sanitized_host = sanitize_plugin_host_header(host_header)
    if sanitized_host:
        return f"http://{sanitized_host}/api/plugin/update-token"

    fallback_host = "127.0.0.1" if server_host == "0.0.0.0" else server_host
    return f"http://{fallback_host}:{server_port}/api/plugin/update-token"
