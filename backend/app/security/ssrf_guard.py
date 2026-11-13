"""Strict SSRF guard and safe public URL fetcher for job descriptions.

Security controls:
1. Only `http` and `https` schemes are allowed.
2. Userinfo (`user:pass@host`) and empty/localhost hostnames are rejected.
3. DNS resolution (`socket.getaddrinfo`) is inspected before every hop; any IP that is
   private, loopback, link-local, multicast, reserved, unspecified, or cloud metadata
   (`169.254.169.254`, `100.100.100.200`, `fd00:ec2::254`, etc.) is blocked.
4. Redirects (`301/302/303/307/308`) are followed manually up to `MAX_REDIRECTS` (3),
   re-validating the target URL and its resolved IPs on every hop.
5. Response size is capped in streaming mode (`MAX_URL_RESPONSE_BYTES` = 2 MB) with
   a strict timeout (`URL_TIMEOUT_SECONDS` = 10s).
6. Never attempts to bypass authentication, CAPTCHAs, or anti-bot walls (401/403/429).
"""

from __future__ import annotations

import asyncio
import html
import ipaddress
import re
import socket
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx

from app.core.errors import AppError, ValidationFailed
from app.core.logging import get_logger

log = get_logger("app.security.ssrf_guard")

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "kubernetes.default",
    "kubernetes.default.svc",
}
CLOUD_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("192.0.0.192"),
}

MAX_REDIRECTS = 3
MAX_URL_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB HTML ceiling
URL_TIMEOUT_SECONDS = 10.0

ResolverFn = Callable[[str, int], list[str]]


class SSRFBlockedError(AppError):
    status_code = 403
    code = "ssrf_blocked"


class ExternalFetchError(AppError):
    status_code = 422
    code = "url_extraction_failed"


def is_ip_public_and_safe(ip_str: str) -> bool:
    """Returns True only if `ip_str` is a globally routable public IP address."""
    try:
        ip = ipaddress.ip_address(ip_str.split("%")[0])
    except ValueError:
        return False

    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    if ip in CLOUD_METADATA_IPS:
        return False

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    ):
        return False

    # Carrier-grade NAT 100.64.0.0/10
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
        return False

    return True


def _default_resolve(hostname: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    return list({ item[4][0] for item in infos if item and item[4] })


def validate_public_url(url: str, *, resolver: ResolverFn | None = None) -> str:
    """Validates URL syntax, hostname and DNS-resolved IP addresses against SSRF."""
    raw = (url or "").strip()
    if not raw or len(raw) > 2048:
        raise ValidationFailed("Informe uma URL pública válida.", code="invalid_url")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SSRFBlockedError(
            "Apenas URLs públicas com protocolo HTTP ou HTTPS são permitidas."
        )

    if parsed.username or parsed.password:
        raise SSRFBlockedError("URLs contendo credenciais embutidas não são permitidas.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise ValidationFailed("URL inválida: host ausente.", code="invalid_url")

    if hostname in BLOCKED_HOSTNAMES or hostname.endswith((".local", ".internal", ".localhost", ".lan")):
        raise SSRFBlockedError("Endereços locais ou internos não são permitidos.")

    # Direct IP literal check
    try:
        ipaddress.ip_address(hostname)
        if not is_ip_public_and_safe(hostname):
            raise SSRFBlockedError(
                "Acesso bloqueado: endereço IP privado, local ou reservado."
            )
        return raw
    except ValueError:
        pass

    port = parsed.port or (443 if scheme == "https" else 80)
    resolve_fn = resolver or _default_resolve
    try:
        resolved_ips = resolve_fn(hostname, port)
    except socket.gaierror as exc:
        raise ExternalFetchError(
            "Não foi possível resolver o domínio informado. Cole a descrição da vaga manualmente."
        ) from exc

    if not resolved_ips:
        raise ExternalFetchError(
            "O domínio informado não retornou endereços válidos. Cole a descrição manualmente."
        )

    for ip_str in resolved_ips:
        if not is_ip_public_and_safe(ip_str):
            log.warning("ssrf_dns_blocked", extra={"hostname": hostname})
            raise SSRFBlockedError(
                "Acesso bloqueado por segurança: o domínio resolve para um endereço interno ou privado."
            )

    return raw


_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript|svg|head|nav|footer|header)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_BLOCK_TAG_RE = re.compile(r"</?(?:p|div|li|ul|ol|br|h[1-6]|tr|section|article)[^>]*>", re.IGNORECASE)
_ANY_TAG_RE = re.compile(r"<[^>]+>")
_CAPTCHA_HINTS = (
    "verify you are human",
    "cf-turnstile",
    "g-recaptcha",
    "hcaptcha",
    "enable javascript and cookies to continue",
)


def extract_visible_text_from_html(raw_html: str) -> str:
    """Strips scripts/styles/tags and converts HTML into clean readable plain text."""
    lower = raw_html.lower()
    if any(hint in lower for hint in _CAPTCHA_HINTS) and len(raw_html) < 25_000:
        raise ExternalFetchError(
            "A página da vaga exige autenticação ou verificação anti-bot. "
            "Por favor, copie e cole a descrição da vaga diretamente."
        )

    without_scripts = _SCRIPT_STYLE_RE.sub(" ", raw_html)
    with_newlines = _BLOCK_TAG_RE.sub("\n", without_scripts)
    no_tags = _ANY_TAG_RE.sub(" ", with_newlines)
    unescaped = html.unescape(no_tags)

    lines: list[str] = []
    for ln in unescaped.splitlines():
        cleaned = re.sub(r"\s+", " ", ln).strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines).strip()


async def fetch_public_job_url_text(
    url: str,
    *,
    resolver: ResolverFn | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> str:
    """Safely fetches a public URL with SSRF protection on every redirect hop."""
    current_url = await asyncio.to_thread(validate_public_url, url, resolver=resolver)

    headers = {
        "User-Agent": "CareerMatchAI-JobReader/1.0 (+https://localhost)",
        "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
    }

    async def _do_fetch(client: httpx.AsyncClient) -> str:
        nonlocal current_url
        for _ in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream(
                    "GET",
                    current_url,
                    headers=headers,
                    follow_redirects=False,
                    timeout=URL_TIMEOUT_SECONDS,
                ) as resp:
                    if resp.status_code in {301, 302, 303, 307, 308}:
                        location = resp.headers.get("location")
                        if not location:
                            raise ExternalFetchError(
                                "Redirecionamento inválido na URL informada. Cole a descrição da vaga."
                            )
                        next_url = urljoin(current_url, location)
                        current_url = await asyncio.to_thread(
                            validate_public_url, next_url, resolver=resolver
                        )
                        continue

                    if resp.status_code in {401, 403, 429}:
                        raise ExternalFetchError(
                            "O site da vaga bloqueou o acesso automatizado ou requer login. "
                            "Por favor, cole a descrição da vaga manualmente."
                        )
                    if resp.status_code >= 400:
                        raise ExternalFetchError(
                            f"Não foi possível acessar a URL (HTTP {resp.status_code}). "
                            "Cole a descrição da vaga manualmente."
                        )

                    ctype = (resp.headers.get("content-type") or "").lower()
                    if ctype and not any(t in ctype for t in ("text/html", "text/plain", "application/xhtml")):
                        raise ExternalFetchError(
                            "A URL informada não aponta para uma página de texto/HTML. Cole a descrição da vaga."
                        )

                    buf = bytearray()
                    async for chunk in resp.aiter_bytes(chunk_size=32 * 1024):
                        buf.extend(chunk)
                        if len(buf) > MAX_URL_RESPONSE_BYTES:
                            raise ExternalFetchError(
                                "A página excede o tamanho máximo permitido. Cole a descrição da vaga manualmente."
                            )
                    raw_body = bytes(buf).decode("utf-8", errors="replace")
                    text = extract_visible_text_from_html(raw_body)
                    if len(text) < 40:
                        raise ExternalFetchError(
                            "Não foi possível extrair texto suficiente da URL (a página pode exigir renderização ou login). "
                            "Cole a descrição da vaga manualmente."
                        )
                    return text
            except (SSRFBlockedError, ExternalFetchError, ValidationFailed):
                raise
            except httpx.RequestError as exc:
                raise ExternalFetchError(
                    "Falha de conexão ao acessar a URL pública. Cole a descrição da vaga manualmente."
                ) from exc

        raise ExternalFetchError(
            "A URL excedeu o limite máximo de redirecionamentos permitidos. Cole a descrição da vaga."
        )

    if http_client is not None:
        return await _do_fetch(http_client)

    async with httpx.AsyncClient(follow_redirects=False, timeout=URL_TIMEOUT_SECONDS) as client:
        return await _do_fetch(client)
