"""File-only, single-key signer for governed Pep Health service assertions."""

import base64
import binascii
import json
import math
import os
import re
import secrets
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_MAX_KEY_FILE_BYTES = 128
_MAX_JSON_INTEGER = 2**53 - 1


class ServiceAssertionError(ValueError):
    """A stable, non-sensitive assertion configuration or signing failure."""


def _new_jti() -> str:
    return secrets.token_urlsafe(32)


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _encoded_json(value: dict[str, str | int]) -> str:
    return _base64url(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))


@dataclass(frozen=True, slots=True, repr=False)
class ServiceAssertionSigner:
    """One immutable active key/kid; private key bytes are never public."""

    kid: str
    _key: Ed25519PrivateKey = field(repr=False)
    _clock: Callable[[], float] = field(repr=False)
    _jti_source: Callable[[], str] = field(repr=False)

    def sign(self, subject: str) -> str:
        """Sign only the trusted HA subject supplied by the request boundary."""
        if not isinstance(subject, str) or not subject.strip():
            raise ServiceAssertionError("INVALID_SERVICE_ASSERTION_SUBJECT")
        try:
            now = self._clock()
            if (
                isinstance(now, bool)
                or not isinstance(now, (int, float))
                or not math.isfinite(now)
                or not 0 <= now <= _MAX_JSON_INTEGER - 30
            ):
                raise ValueError
            issued_at = math.floor(now)
            expires_at = issued_at + 30
            jti = self._jti_source()
            if not isinstance(jti, str) or not jti.strip():
                raise ValueError
            header = _encoded_json({"alg": "EdDSA", "typ": "H0-SA", "kid": self.kid})
            claims = _encoded_json(
                {
                    "iss": "getfit",
                    "aud": "peptide-health-read",
                    "sub": subject,
                    "iat": issued_at,
                    "exp": expires_at,
                    "jti": jti,
                    "kid": self.kid,
                }
            )
            message = f"{header}.{claims}"
            signature = self._key.sign(message.encode("ascii"))
            return f"{message}.{_base64url(signature)}"
        except Exception:
            # Never propagate dependency messages containing subject, JTI or key material.
            raise ServiceAssertionError("SERVICE_ASSERTION_SIGNING_FAILED") from None


def _validate_key_file(metadata: os.stat_result) -> None:
    if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= _MAX_KEY_FILE_BYTES:
        raise ValueError
    if os.name == "posix" and metadata.st_mode & (stat.S_IRGRP | stat.S_IROTH):
        raise ValueError


def _load_key(path: Path) -> Ed25519PrivateKey:
    metadata = path.lstat()
    _validate_key_file(metadata)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as key_file:
        opened = os.fstat(key_file.fileno())
        _validate_key_file(opened)
        if (metadata.st_dev, metadata.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError
        # Recheck after open even on systems lacking O_NOFOLLOW.
        if stat.S_ISLNK(path.lstat().st_mode):
            raise ValueError
        encoded = key_file.read(_MAX_KEY_FILE_BYTES + 1)
    if len(encoded) > _MAX_KEY_FILE_BYTES:
        raise ValueError
    encoded = encoded.strip()
    if re.fullmatch(rb"[A-Za-z0-9_-]{43}=?", encoded) is None:
        raise ValueError
    raw = base64.b64decode(encoded.rstrip(b"=") + b"=", altchars=b"-_", validate=True)
    if len(raw) != 32 or _base64url(raw).encode("ascii") != encoded.rstrip(b"="):
        raise ValueError
    return Ed25519PrivateKey.from_private_bytes(raw)


def load_service_assertion_signer(
    path: str | Path,
    *,
    kid: str,
    clock: Callable[[], float] = time.time,
    jti_source: Callable[[], str] = _new_jti,
) -> ServiceAssertionSigner:
    """Load exactly one owner-readable key file during application construction."""
    if not isinstance(kid, str) or not kid.strip():
        raise ServiceAssertionError("PEP_HEALTH_CONFIGURATION_INVALID")
    try:
        key = _load_key(Path(path))
    except (OSError, ValueError, TypeError, binascii.Error):
        raise ServiceAssertionError("PEP_HEALTH_CONFIGURATION_INVALID") from None
    return ServiceAssertionSigner(kid=kid, _key=key, _clock=clock, _jti_source=jti_source)
