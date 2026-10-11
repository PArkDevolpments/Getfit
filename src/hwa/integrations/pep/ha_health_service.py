"""Request-scoped, assertion-only transport for Pep's governed HA service."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Protocol, cast

from websockets.asyncio.client import ClientConnection, connect

_ENDPOINT = "ws://supervisor/core/websocket"
_UNAVAILABLE = "PEP_HEALTH_UNAVAILABLE"
_GOVERNED_ERRORS = frozenset(
    {
        "HEALTH_AUTHORITY_DISABLED",
        "SERVICE_ASSERTION_STARTUP_QUARANTINE",
        "INVALID_SERVICE_ASSERTION",
        "PERSON_CONTEXT_UNAVAILABLE",
        "ASSERTION_RATE_LIMITED",
    }
)


class WebSocket(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


WebSocketConnector = Callable[..., AbstractAsyncContextManager[WebSocket]]


class _SingleConnectionConnect(connect):
    """The pinned WebSocket connector must never follow an HTTP redirect."""

    def process_redirect(self, exc: Exception) -> Exception:
        return exc


@dataclass(frozen=True, slots=True)
class HaHealthServiceEnvelope:
    """Strict envelope; recursively immutable payload is never included in repr."""

    status_code: int
    body: Mapping[str, object] = field(repr=False)
    headers: Mapping[str, str] = field(repr=False)


@dataclass(frozen=True, slots=True)
class HaHealthServiceFailure:
    """Only a stable public failure survives a failed transport attempt."""

    reason: Literal["PEP_HEALTH_UNAVAILABLE"] = "PEP_HEALTH_UNAVAILABLE"


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _invalid_constant(value: str) -> object:
    raise ValueError


def _freeze(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _envelope(frame: dict[str, object]) -> HaHealthServiceEnvelope:
    if (
        frame.get("type") != "result"
        or type(frame.get("id")) is not int
        or frame["id"] != 1
        or frame.get("success") is not True
    ):
        raise ValueError
    result = frame.get("result")
    if not isinstance(result, dict):
        raise ValueError
    response = result.get("response")
    if not isinstance(response, dict):
        raise ValueError
    status_code = response.get("status_code")
    body = response.get("body")
    headers = response.get("headers")
    if (
        type(status_code) is not int
        or not isinstance(body, dict)
        or not isinstance(headers, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items()
        )
        or headers.get("Cache-Control") != "no-store"
    ):
        raise ValueError
    if status_code != 200:
        error = body.get("error")
        body = {
            "error": error if isinstance(error, str) and error in _GOVERNED_ERRORS else _UNAVAILABLE
        }
    return HaHealthServiceEnvelope(
        status_code=status_code,
        body=cast(Mapping[str, object], _freeze(body)),
        headers=MappingProxyType(cast(dict[str, str], headers)),
    )


@dataclass(frozen=True, slots=True, repr=False, init=False)
class HaHealthServiceClient:
    """One connection and one service command per attempt; never retries."""

    _supervisor_token: str
    _connector: WebSocketConnector
    _timeout_seconds: float
    _monotonic: Callable[[], float]
    _logger: logging.Logger

    def __init__(
        self,
        *,
        supervisor_token: str,
        connector: WebSocketConnector = _SingleConnectionConnect,
        timeout_seconds: float = 5.0,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if (
            not isinstance(supervisor_token, str)
            or not supervisor_token.strip()
            or isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("PEP_HEALTH_CONFIGURATION_INVALID")
        # websockets' debug frames and exception logs can contain credentials/body.
        # An isolated disabled logger suppresses them without global logging changes.
        logger = logging.Logger("hwa.pep.health.transport")
        logger.disabled = True
        logger.propagate = False
        object.__setattr__(self, "_supervisor_token", supervisor_token)
        object.__setattr__(self, "_connector", connector)
        object.__setattr__(self, "_timeout_seconds", float(timeout_seconds))
        object.__setattr__(self, "_monotonic", monotonic)
        object.__setattr__(self, "_logger", logger)

    def _check_deadline(self, deadline: float) -> None:
        if self._monotonic() >= deadline:
            raise TimeoutError

    async def _receive(self, socket: WebSocket, deadline: float) -> dict[str, object]:
        raw = await socket.recv()
        self._check_deadline(deadline)
        frame = cast(
            object,
            json.loads(raw, object_pairs_hook=_json_object, parse_constant=_invalid_constant),
        )
        if not isinstance(frame, dict):
            raise ValueError
        return cast(dict[str, object], frame)

    async def _send(self, socket: WebSocket, message: dict[str, object], deadline: float) -> None:
        await socket.send(json.dumps(message, separators=(",", ":")))
        self._check_deadline(deadline)

    @asynccontextmanager
    async def _connection(self, deadline: float) -> AsyncIterator[WebSocket]:
        cancelled = False
        socket: WebSocket | None = None
        try:
            async with self._connector(
                _ENDPOINT,
                proxy=None,
                open_timeout=None,
                close_timeout=self._timeout_seconds,
                ping_interval=None,
                logger=self._logger,
            ) as socket:
                try:
                    yield socket
                except asyncio.CancelledError:
                    cancelled = True
                    raise
                finally:
                    if isinstance(socket, ClientConnection):
                        # websockets starts its close clock during context exit.
                        # Give it only this attempt's remaining budget; an expired
                        # or cancelled attempt must release the transport now.
                        remaining = max(0.0, deadline - self._monotonic())
                        socket.close_timeout = remaining
                        if cancelled or remaining == 0:
                            socket.transport.abort()
        except asyncio.CancelledError:
            if isinstance(socket, ClientConnection):
                socket.transport.abort()
                await socket.wait_closed()
            raise
        except Exception:
            if cancelled:
                if isinstance(socket, ClientConnection):
                    socket.transport.abort()
                    await socket.wait_closed()
                # An adapter's cleanup failure must not convert cancellation into
                # a successful request returning an ordinary unavailable result.
                raise asyncio.CancelledError from None
            raise

    async def get_health_context(
        self, assertion: str
    ) -> HaHealthServiceEnvelope | HaHealthServiceFailure:
        """Pass only the assertion to HA; discard every raw transport failure."""
        try:
            deadline = self._monotonic() + self._timeout_seconds
            async with asyncio.timeout(self._timeout_seconds):
                async with self._connection(deadline) as socket:
                    self._check_deadline(deadline)
                    if (await self._receive(socket, deadline)).get("type") != "auth_required":
                        raise ValueError
                    await self._send(
                        socket, {"type": "auth", "access_token": self._supervisor_token}, deadline
                    )
                    if (await self._receive(socket, deadline)).get("type") != "auth_ok":
                        raise ValueError
                    await self._send(
                        socket,
                        {
                            "id": 1,
                            "type": "call_service",
                            "domain": "peptide_site",
                            "service": "get_health_context",
                            "service_data": {"assertion": assertion},
                            "return_response": True,
                        },
                        deadline,
                    )
                    envelope = _envelope(await self._receive(socket, deadline))
                self._check_deadline(deadline)
                return envelope
        except Exception:
            # CancelledError is a BaseException and propagates after context cleanup.
            # No raw exception, HA message, body, assertion or token escapes this seam.
            return HaHealthServiceFailure()
