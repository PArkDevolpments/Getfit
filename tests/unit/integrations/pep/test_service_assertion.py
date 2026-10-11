"""Canonical H6 assertions and the file-only private-key boundary."""

import base64
import importlib
import json
import logging
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

KEY = bytes(range(32))
ENCODED_KEY = base64.urlsafe_b64encode(KEY).decode().rstrip("=")
SUBJECT = "synthetic-ha-subject-private-sentinel"
JTI = "synthetic-jti-private-sentinel"


def loader() -> Any:
    try:
        module = importlib.import_module("hwa.integrations.pep.service_assertion")
    except ModuleNotFoundError:
        pytest.fail("Missing file-only H6 assertion signer")
    return module.load_service_assertion_signer


def key_file(tmp_path: Path, content: bytes = ENCODED_KEY.encode()) -> Path:
    path = tmp_path / "private-key"
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def test_exact_canonical_assertion_verifies_with_only_configured_key(tmp_path: Path) -> None:
    signer = loader()(
        key_file(tmp_path), kid="synthetic-kid", clock=lambda: 1700000000.9, jti_source=lambda: JTI
    )
    assertion = signer.sign(SUBJECT)
    header, claims, signature = assertion.split(".")
    assert "=" not in assertion
    assert decode(header) == b'{"alg":"EdDSA","kid":"synthetic-kid","typ":"H0-SA"}'
    assert decode(claims) == (
        b'{"aud":"peptide-health-read","exp":1700000030,"iat":1700000000,'
        b'"iss":"getfit","jti":"synthetic-jti-private-sentinel","kid":"synthetic-kid",'
        b'"sub":"synthetic-ha-subject-private-sentinel"}'
    )
    Ed25519PrivateKey.from_private_bytes(KEY).public_key().verify(
        decode(signature), f"{header}.{claims}".encode()
    )
    with pytest.raises(InvalidSignature):
        Ed25519PrivateKey.from_private_bytes(bytes(reversed(KEY))).public_key().verify(
            decode(signature), f"{header}.{claims}".encode()
        )


def test_each_call_uses_new_jti_and_current_clock(tmp_path: Path) -> None:
    times = iter([1700000000, 1700000100])
    jtis = iter(["synthetic-first-jti", "synthetic-second-jti"])
    signer = loader()(
        key_file(tmp_path),
        kid="synthetic-kid",
        clock=lambda: next(times),
        jti_source=lambda: next(jtis),
    )
    first = json.loads(decode(signer.sign(SUBJECT).split(".")[1]))
    second = json.loads(decode(signer.sign(SUBJECT).split(".")[1]))
    assert (first["jti"], second["jti"]) == ("synthetic-first-jti", "synthetic-second-jti")
    assert (first["iat"], second["iat"]) == (1700000000, 1700000100)
    assert (first["exp"], second["exp"]) == (1700000030, 1700000130)


def test_default_random_source_does_not_reuse_assertions(tmp_path: Path) -> None:
    signer = loader()(key_file(tmp_path), kid="synthetic-kid")
    jtis = {json.loads(decode(signer.sign(SUBJECT).split(".")[1]))["jti"] for _ in range(32)}
    assert len(jtis) == 32
    assert all(len(jti) >= 32 for jti in jtis)


@pytest.mark.parametrize("subject", ["", " ", "\t\n", None, True, 123])
def test_blank_or_non_string_subject_fails_closed(tmp_path: Path, subject: Any) -> None:
    signer = loader()(key_file(tmp_path), kid="synthetic-kid")
    with pytest.raises(ValueError):
        signer.sign(subject)


@pytest.mark.parametrize("kid", ["", " ", "\t\n", None, True, ["old", "new"]])
def test_blank_or_multiple_kids_fail_closed(tmp_path: Path, kid: Any) -> None:
    with pytest.raises(ValueError):
        loader()(key_file(tmp_path), kid=kid)


@pytest.mark.parametrize(
    "now",
    [float("nan"), float("inf"), -float("inf"), -1, True, "1700000000", None, 2**53 - 20, 10**400],
)
def test_invalid_time_or_unrepresentable_expiry_fails_closed(tmp_path: Path, now: Any) -> None:
    signer = loader()(key_file(tmp_path), kid="synthetic-kid", clock=lambda: now)
    with pytest.raises(ValueError):
        signer.sign(SUBJECT)


@pytest.mark.parametrize("jti", ["", " ", None, True])
def test_invalid_jti_source_fails_closed(tmp_path: Path, jti: Any) -> None:
    signer = loader()(key_file(tmp_path), kid="synthetic-kid", jti_source=lambda: jti)
    with pytest.raises(ValueError):
        signer.sign(SUBJECT)


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b" ",
        b"not!base64",
        b"+" * 43,
        b"/" * 43,
        b"\xff",
        b"A" * 42,
        b"A" * 44,
        b"A" * 43 + b"===",
        b"A" * 8192,
    ],
)
def test_invalid_key_encoding_length_or_oversized_file_fails_closed(
    tmp_path: Path, content: bytes
) -> None:
    with pytest.raises(ValueError):
        loader()(key_file(tmp_path, content), kid="synthetic-kid")


@pytest.mark.parametrize("padded", [False, True])
def test_loads_one_base64url_key_once(tmp_path: Path, padded: bool) -> None:
    content = base64.urlsafe_b64encode(KEY) if padded else ENCODED_KEY.encode()
    path = key_file(tmp_path, content + b"\n")
    signer = loader()(path, kid="synthetic-kid")
    path.unlink()
    assertion = signer.sign(SUBJECT)
    header, claims, signature = assertion.split(".")
    Ed25519PrivateKey.from_private_bytes(KEY).public_key().verify(
        decode(signature), f"{header}.{claims}".encode()
    )


def test_missing_and_directory_key_paths_fail_closed(tmp_path: Path) -> None:
    for path in (tmp_path / "missing", tmp_path):
        with pytest.raises(ValueError):
            loader()(path, kid="synthetic-kid")


def test_symlink_key_file_fails_closed(tmp_path: Path) -> None:
    path = key_file(tmp_path)
    link = tmp_path / "symlink"
    try:
        link.symlink_to(path)
    except OSError:
        pytest.skip("Symlink creation requires an unavailable Windows privilege")
    with pytest.raises(ValueError):
        loader()(link, kid="synthetic-kid")


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission boundary")
@pytest.mark.parametrize("mode", [0o640, 0o604, 0o660, 0o666])
def test_group_or_world_readable_key_fails_closed(tmp_path: Path, mode: int) -> None:
    path = key_file(tmp_path)
    path.chmod(mode)
    with pytest.raises(ValueError):
        loader()(path, kid="synthetic-kid")


@pytest.mark.skipif(os.name != "posix", reason="POSIX non-regular file boundary")
def test_fifo_key_fails_closed_without_blocking(tmp_path: Path) -> None:
    path = tmp_path / "fifo"
    os.mkfifo(path)
    with pytest.raises(ValueError):
        loader()(path, kid="synthetic-kid")


def test_signer_is_immutable_and_public_surface_does_not_expose_key(tmp_path: Path) -> None:
    signer = loader()(key_file(tmp_path), kid="synthetic-kid")
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        signer.kid = "other-kid"
    for name in dir(signer):
        if not name.startswith("_"):
            assert not isinstance(getattr(signer, name), (bytes, Ed25519PrivateKey))
    assert ENCODED_KEY not in repr(signer)
    assert repr(KEY) not in repr(signer)


def test_sequential_rotation_emits_only_current_configured_kid(tmp_path: Path) -> None:
    for kid, raw_key in [("old-kid", KEY), ("new-kid", bytes(reversed(KEY)))]:
        path = key_file(tmp_path, base64.urlsafe_b64encode(raw_key))
        signer = loader()(path, kid=kid)
        for _ in range(2):
            header, claims, signature = signer.sign(SUBJECT).split(".")
            assert json.loads(decode(header))["kid"] == kid
            assert json.loads(decode(claims))["kid"] == kid
            Ed25519PrivateKey.from_private_bytes(raw_key).public_key().verify(
                decode(signature), f"{header}.{claims}".encode()
            )
        del signer


def test_success_and_failures_do_not_log_or_expose_sensitive_sentinels(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    signer = loader()(key_file(tmp_path), kid="synthetic-kid", jti_source=lambda: JTI)
    assertion = signer.sign(SUBJECT)
    errors = []
    for operation in [
        lambda: signer.sign(" "),
        lambda: loader()(key_file(tmp_path, b"private-key-invalid-sentinel"), kid="synthetic-kid"),
    ]:
        with pytest.raises(ValueError) as error:
            operation()
        errors.append(str(error.value))

    def failing_clock() -> float:
        raise RuntimeError(f"{ENCODED_KEY}:{SUBJECT}:{JTI}:{assertion}")

    failed = loader()(key_file(tmp_path), kid="synthetic-kid", clock=failing_clock)
    with pytest.raises(ValueError) as error:
        failed.sign(SUBJECT)
    errors.append(str(error.value))
    for sentinel in [
        ENCODED_KEY,
        repr(KEY),
        SUBJECT,
        JTI,
        assertion,
        "private-key-invalid-sentinel",
    ]:
        assert sentinel not in caplog.text
        assert all(sentinel not in message for message in errors)
