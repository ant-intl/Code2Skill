"""Security guardrails for source scanning and model endpoints."""

from __future__ import annotations

import ipaddress
import re
import socket
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private_key_block"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws_access_key"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "github_token"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "api_key"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "slack_token"),
]


def validate_model_url(base_url: str, allow_public_url: bool = False) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Model URL must use http or https")
    if not parsed.hostname:
        raise ValueError("Model URL must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("Model URL must not embed credentials")
    if allow_public_url:
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(parsed.hostname, port)
        }
    except socket.gaierror as exc:
        raise ValueError(f"Unable to resolve model host {parsed.hostname!r}") from exc
    for address in addresses:
        if address.is_private or address.is_loopback or address.is_link_local:
            continue
        raise ValueError(
            f"Refusing public model host {parsed.hostname!r} ({address}); "
            "use --allow-public-model-url only for an approved endpoint"
        )


def secret_marker(text: str) -> Optional[str]:
    for pattern, name in SECRET_PATTERNS:
        if pattern.search(text):
            return name
    return None


def is_probably_binary(payload: bytes) -> bool:
    if not payload:
        return False
    if b"\x00" in payload:
        return True
    sample = payload[:2048]
    control_bytes = sum(1 for byte in sample if byte < 9 or 13 < byte < 32)
    return control_bytes / max(1, len(sample)) > 0.20


def is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
