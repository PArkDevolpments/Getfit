"""Ingress-aware presentation URL helpers.

Home Assistant Supervisor Ingress serves Getfit below a per-session path prefix.
Root-relative browser URLs bypass that prefix, so templates and client-side API
requests must be generated relative to the trusted ingress base when it is present.
"""

import re

from fastapi import Request

_INGRESS_PATH = re.compile(r"^/api/hassio_ingress/[A-Za-z0-9_-]{6,128}$")


def ingress_prefix(request: Request) -> str:
    """Return a validated Supervisor ingress path prefix, or an empty direct-app prefix."""

    value = request.headers.get("x-ingress-path", "").rstrip("/")
    if not value or _INGRESS_PATH.fullmatch(value) is None:
        return ""
    return value


def ingress_url(request: Request, path: str) -> str:
    """Prefix an application-root path for Home Assistant Ingress."""

    normalized = "/" + path.lstrip("/")
    return f"{ingress_prefix(request)}{normalized}"
