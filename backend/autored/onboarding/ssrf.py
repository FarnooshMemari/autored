"""SSRF protection for operator-submitted target URLs.

A public "enter a URL" feature must never let a user point AutoRed's server-side
browser/fetch at internal infrastructure (cloud metadata, loopback, RFC-1918,
link-local) or at a hostname that resolves to such an address (DNS rebinding).

`validate_target_url` is the single chokepoint:
  * scheme must be http/https, no embedded credentials, no fragment games
  * the hostname is resolved to *every* A/AAAA record
  * if ANY resolved address is non-public the URL is rejected
  * the resolved public IPs are returned so the caller can pin them and detect
    a later rebind (resolve-again-and-compare before each navigation)

`allow_private=True` is a development-only escape hatch (set by the operator via
AUTORED_ALLOW_PRIVATE_TARGETS=1) so the self-hosted loopback test targets can be
onboarded locally. It is OFF by default and must stay off in any public build.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_SCHEMES = ("http", "https")
# AWS/GCP/Azure/OpenStack link-local metadata endpoints share 169.254.0.0/16,
# already covered by is_link_local; listed here for defence-in-depth clarity.
_METADATA_IPS = {ipaddress.ip_address("169.254.169.254"), ipaddress.ip_address("fd00:ec2::254")}


class SSRFError(Exception):
    """Raised when a submitted URL is unsafe to fetch from the server."""


@dataclass(frozen=True)
class ResolvedTarget:
    url: str
    scheme: str
    host: str
    port: int
    origin: str               # scheme://host:port  (what OriginGuard pins)
    ips: tuple[str, ...]       # every resolved public IP, pinned against rebinding


def _as_v4(ip: ipaddress._BaseAddress) -> ipaddress._BaseAddress:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _is_public(ip: ipaddress._BaseAddress) -> bool:
    if ip in _METADATA_IPS:
        return False
    ip = _as_v4(ip)
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
        or ip.is_reserved or ip.is_unspecified
        or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"))  # CGNAT
    )


def _resolve(host: str) -> list[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise SSRFError(f"could not resolve host '{host}': {e}") from e
    out: list[ipaddress._BaseAddress] = []
    for info in infos:
        addr = info[4][0]
        try:
            out.append(ipaddress.ip_address(addr.split("%", 1)[0]))  # strip zone id
        except ValueError:
            continue
    if not out:
        raise SSRFError(f"host '{host}' did not resolve to any IP address")
    return out


def validate_target_url(url: str, *, allow_private: bool = False) -> ResolvedTarget:
    url = (url or "").strip()
    if not url:
        raise SSRFError("empty URL")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise SSRFError(f"scheme must be http or https, got '{parts.scheme or '(none)'}'")
    if parts.username or parts.password:
        raise SSRFError("URLs with embedded credentials are not allowed")
    host = (parts.hostname or "").lower()
    if not host:
        raise SSRFError("URL has no host")
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    if not (0 < port <= 65535):
        raise SSRFError(f"invalid port {port}")

    # A literal IP in the URL is classified directly; a hostname is resolved.
    try:
        literal = ipaddress.ip_address(host)
        resolved = [literal]
    except ValueError:
        resolved = _resolve(host)

    # Cloud metadata endpoints are blocked UNCONDITIONALLY — allow_private never reaches them.
    meta = [str(ip) for ip in resolved if _as_v4(ip) in _METADATA_IPS or ip in _METADATA_IPS]
    if meta:
        raise SSRFError(f"host '{host}' resolves to a cloud metadata address {meta}; always blocked")
    if not allow_private:
        bad = [str(ip) for ip in resolved if not _is_public(ip)]
        if bad:
            raise SSRFError(
                f"host '{host}' resolves to non-public address(es) {bad}; refusing to scan "
                "internal/loopback/metadata targets")

    origin = f"{parts.scheme.lower()}://{host}:{port}"
    return ResolvedTarget(url=url, scheme=parts.scheme.lower(), host=host, port=port,
                          origin=origin, ips=tuple(str(ip) for ip in resolved))


def assert_still_resolves_same(host: str, pinned_ips: tuple[str, ...], *, allow_private: bool = False) -> None:
    """DNS-rebind guard: re-resolve `host` and confirm it still maps only to the
    previously pinned public IPs. Call before each fresh navigation in a long mission."""
    try:
        ipaddress.ip_address(host)
        return  # literal IP, nothing to rebind
    except ValueError:
        pass
    current = {str(ip) for ip in _resolve(host)}
    if not allow_private:
        bad = [ip for ip in current if not _is_public(ipaddress.ip_address(ip))]
        if bad:
            raise SSRFError(f"host '{host}' now resolves to non-public address(es) {bad} (possible DNS rebind)")
    if not current <= set(pinned_ips):
        raise SSRFError(f"host '{host}' resolution changed to {sorted(current)} (pinned {sorted(pinned_ips)}); "
                        "possible DNS rebind, aborting")
