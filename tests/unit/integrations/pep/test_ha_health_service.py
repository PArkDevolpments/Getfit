"""One-shot HA protocol tests using a synthetic external WebSocket boundary."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import FrozenInstanceError
from typing import Any

import pytest
from websockets.asyncio.client import ClientConnection, connect
from websockets.asyncio.server import ServerConnection, serve
from websockets.protocol import CLOSED

TOKEN = "synthetic-private-token"
ASSERTION = "synthetic-private-assertion"
SENTINEL = "synthetic-private-payload"


def module() -> Any:
    spec = importlib.util.find_spec("hwa.integrations.pep.ha_health_service")
    assert spec is not None, "Missing one-shot HA service client"
    return importlib.import_module("hwa.integrations.pep.ha_health_service")


def response(*, status_code: object = 200, body: object = None) -> dict[str, Any]:
    return {
        "status_code": status_code,
        "body": {"nested": {"value": SENTINEL}, "items": [1, 2]} if body is None else body,
        "headers": {"Cache-Control": "no-store"},
    }


def result(envelope: object = None, **changes: object) -> dict[str, Any]:
    return {
        "id": 1,
        "type": "result",
        "success": True,
        "result": {"response": response() if envelope is None else envelope},
        **changes,
    }


class Clock:
    now = 100.0

    def __call__(self) -> float:
        return self.now


class Peer:
    def __init__(self, frames: list[object] | None = None) -> None:
        self.frames = (
            frames
            if frames is not None
            else [{"type": "auth_required"}, {"type": "auth_ok"}, result()]
        )
        self.sent: list[dict[str, Any]] = []
        self.events: list[str] = []
        self.closed = False
        self.connections = 0
        self.endpoint = ""
        self.options: dict[str, Any] = {}
        self.block_at: str | None = None
        self.raise_at: str | None = None
        self.advance_at: str | None = None
        self.clock = Clock()
        self.started = asyncio.Event()

    async def step(self, name: str) -> None:
        self.events.append(name)
        if name == self.raise_at:
            raise RuntimeError(SENTINEL + TOKEN + ASSERTION)
        if name == self.advance_at:
            self.clock.now += 2.0
        if name == self.block_at:
            self.started.set()
            await asyncio.Event().wait()

    @asynccontextmanager
    async def connector(self, endpoint: str, **kwargs: Any) -> AsyncIterator[Peer]:
        self.connections += 1
        self.endpoint = endpoint
        self.options = kwargs
        await self.step("connect")
        try:
            yield self
        finally:
            self.closed = True
            await self.step("close")

    async def recv(self) -> str:
        await self.step(f"recv-{len([e for e in self.events if e.startswith('recv-')])}")
        frame = self.frames.pop(0)
        return frame if isinstance(frame, str) else json.dumps(frame)

    async def send(self, data: str) -> None:
        await self.step(f"send-{len(self.sent)}")
        self.sent.append(json.loads(data))


def client(peer: Peer, *, timeout_seconds: float = 1.0) -> Any:
    return module().HaHealthServiceClient(
        supervisor_token=TOKEN,
        connector=peer.connector,
        timeout_seconds=timeout_seconds,
        monotonic=peer.clock,
    )


@pytest.mark.asyncio
async def test_exact_auth_service_sequence_and_immutable_envelope() -> None:
    peer = Peer()
    before = asyncio.all_tasks()
    transport = client(peer)
    envelope = await transport.get_health_context(ASSERTION)
    assert isinstance(envelope, module().HaHealthServiceEnvelope)
    assert envelope.status_code == 200
    assert envelope.body["nested"]["value"] == SENTINEL
    assert envelope.headers == {"Cache-Control": "no-store"}
    assert peer.endpoint == "ws://supervisor/core/websocket"
    assert peer.sent == [
        {"type": "auth", "access_token": TOKEN},
        {
            "id": 1,
            "type": "call_service",
            "domain": "peptide_site",
            "service": "get_health_context",
            "service_data": {"assertion": ASSERTION},
            "return_response": True,
        },
    ]
    assert peer.events == ["connect", "recv-0", "send-0", "recv-1", "send-1", "recv-2", "close"]
    assert peer.connections == 1
    assert peer.closed
    assert asyncio.all_tasks() == before
    with pytest.raises(FrozenInstanceError):
        envelope.status_code = 503
    with pytest.raises(TypeError):
        envelope.body["nested"]["value"] = "changed"
    with pytest.raises(TypeError):
        envelope.headers["Cache-Control"] = "public"
    assert envelope.body["items"] == (1, 2)
    for private in (TOKEN, ASSERTION, SENTINEL):
        assert private not in repr(envelope)
        assert private not in repr(transport)


def bad_frames() -> list[Any]:
    cases: list[Any] = [
        pytest.param([], id="not-object"),
        pytest.param("not JSON " + SENTINEL, id="invalid-json"),
        pytest.param(result(id=2), id="wrong-id"),
        pytest.param(result(id=True), id="boolean-id"),
        pytest.param(result(id=1.0), id="float-id"),
        pytest.param(result(type="event"), id="wrong-type"),
        pytest.param(result(success=1), id="numeric-success"),
        pytest.param(result(success=False, error={"message": SENTINEL}), id="ha-error"),
        pytest.param(result(result={}), id="missing-response"),
        pytest.param(result(result=[]), id="result-not-object"),
        pytest.param(result([]), id="response-not-object"),
        pytest.param(result(response(status_code=True)), id="boolean-status"),
        pytest.param(result(response(status_code=200.0)), id="float-status"),
        pytest.param(result(response(status_code="200")), id="string-status"),
        pytest.param(result(response(body=[])), id="body-not-object"),
        pytest.param('{"id":1,"id":2,"type":"result"}', id="duplicate-json-key"),
        pytest.param(json.dumps(result(response(body={"value": float("nan")}))), id="nan"),
    ]
    for name, headers in [
        ("headers-not-object", []),
        ("missing-no-store", {}),
        ("wrong-no-store", {"Cache-Control": "public"}),
        ("non-string-header", {"Cache-Control": "no-store", "Retry-After": 35}),
    ]:
        envelope = response()
        envelope["headers"] = headers
        cases.append(pytest.param(result(envelope), id=name))
    for field in ("status_code", "body", "headers"):
        envelope = response()
        del envelope[field]
        cases.append(pytest.param(result(envelope), id=f"missing-{field}"))
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", bad_frames())
async def test_rejects_malformed_result_and_closes_without_retry(
    frame: object, caplog: pytest.LogCaptureFixture
) -> None:
    peer = Peer([{"type": "auth_required"}, {"type": "auth_ok"}, frame])
    failure = await client(peer).get_health_context(ASSERTION)
    assert isinstance(failure, module().HaHealthServiceFailure)
    assert failure.reason == "PEP_HEALTH_UNAVAILABLE"
    assert peer.closed
    assert peer.connections == 1
    assert len(peer.sent) == 2
    assert SENTINEL not in repr(failure) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "frames,sent_count",
    [
        ([{"type": "auth_ok"}], 0),
        ([{"type": "auth_invalid", "message": SENTINEL}], 0),
        ([{"type": "auth_required"}, {"type": "auth_invalid", "message": SENTINEL}], 1),
        ([{"type": "auth_required"}, {"type": "result"}], 1),
    ],
)
async def test_rejects_out_of_sequence_authentication(
    frames: list[object], sent_count: int
) -> None:
    peer = Peer(frames)
    failure = await client(peer).get_health_context(ASSERTION)
    assert failure.reason == "PEP_HEALTH_UNAVAILABLE"
    assert peer.closed
    assert len(peer.sent) == sent_count
    assert peer.connections == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["connect", "recv-0", "send-0", "recv-1", "send-1", "recv-2"])
async def test_transport_exceptions_are_sanitized_without_retry(
    stage: str, caplog: pytest.LogCaptureFixture
) -> None:
    peer = Peer()
    peer.raise_at = stage
    before = asyncio.all_tasks()
    failure = await client(peer).get_health_context(ASSERTION)
    assert failure.reason == "PEP_HEALTH_UNAVAILABLE"
    assert peer.closed == (stage != "connect")
    assert peer.connections == 1
    assert asyncio.all_tasks() == before
    for private in (TOKEN, ASSERTION, SENTINEL):
        assert private not in repr(failure) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["connect", "recv-0", "send-0", "recv-1", "send-1", "recv-2"])
async def test_timeout_bounds_every_stage_without_tasks_or_retry(stage: str) -> None:
    peer = Peer()
    peer.block_at = stage
    before = asyncio.all_tasks()
    failure = await client(peer, timeout_seconds=0.02).get_health_context(ASSERTION)
    assert failure.reason == "PEP_HEALTH_UNAVAILABLE"
    assert peer.closed == (stage != "connect")
    assert peer.connections == 1
    assert asyncio.all_tasks() == before


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["connect", "recv-0", "send-0", "recv-1", "send-1", "recv-2"])
async def test_injected_monotonic_deadline_is_not_reset_between_stages(stage: str) -> None:
    peer = Peer()
    peer.advance_at = stage
    failure = await client(peer).get_health_context(ASSERTION)
    assert failure.reason == "PEP_HEALTH_UNAVAILABLE"
    assert peer.closed
    assert peer.connections == 1
    assert peer.events[-2:] == [stage, "close"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["connect", "recv-0", "send-0", "recv-1", "send-1", "recv-2"])
async def test_cancellation_propagates_after_cleanup_without_retry(stage: str) -> None:
    peer = Peer()
    peer.block_at = stage
    before = asyncio.all_tasks()
    task = asyncio.create_task(client(peer).get_health_context(ASSERTION))
    await peer.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert peer.closed == (stage != "connect")
    assert peer.connections == 1
    assert asyncio.all_tasks() == before


@pytest.mark.asyncio
async def test_cleanup_error_cannot_swallow_request_cancellation() -> None:
    peer = Peer()
    peer.block_at = "recv-2"
    peer.raise_at = "close"
    task = asyncio.create_task(client(peer).get_health_context(ASSERTION))
    await peer.started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert peer.closed
    assert peer.connections == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason,status",
    [
        ("HEALTH_AUTHORITY_DISABLED", 503),
        ("SERVICE_ASSERTION_STARTUP_QUARANTINE", 503),
        ("INVALID_SERVICE_ASSERTION", 401),
        ("PERSON_CONTEXT_UNAVAILABLE", 403),
        ("ASSERTION_RATE_LIMITED", 429),
        (SENTINEL, 503),
    ],
)
async def test_non_200_body_retains_only_a_stable_governed_error(reason: str, status: int) -> None:
    peer = Peer(
        [
            {"type": "auth_required"},
            {"type": "auth_ok"},
            result(response(status_code=status, body={"error": reason, "private": SENTINEL})),
        ]
    )
    envelope = await client(peer).get_health_context(ASSERTION)
    assert envelope.status_code == status
    expected = "PEP_HEALTH_UNAVAILABLE" if reason == SENTINEL else reason
    assert envelope.body == {"error": expected}
    assert SENTINEL not in repr(envelope) + str(envelope.body)
    assert peer.closed
    assert peer.connections == 1


@pytest.mark.parametrize("token", ["", " ", None, True])
def test_invalid_token_configuration_is_rejected_without_echo(token: object) -> None:
    with pytest.raises(ValueError, match="^PEP_HEALTH_CONFIGURATION_INVALID$"):
        module().HaHealthServiceClient(supervisor_token=token)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True])
def test_timeout_configuration_must_be_positive_and_finite(timeout: object) -> None:
    with pytest.raises(ValueError, match="^PEP_HEALTH_CONFIGURATION_INVALID$"):
        module().HaHealthServiceClient(supervisor_token=TOKEN, timeout_seconds=timeout)


def silent_logger() -> logging.Logger:
    logger = logging.Logger("synthetic-loopback-peer")
    logger.disabled = True
    return logger


@asynccontextmanager
async def uncooperative_peer(
    *, stall_response: bool = False
) -> AsyncIterator[tuple[Any, list[ClientConnection], asyncio.Event]]:
    """Actual websockets peers; pausing reads prevents any Close acknowledgement."""
    finish = asyncio.Event()
    closing = asyncio.Event()
    connections: list[ClientConnection] = []

    class TrackedConnection(ClientConnection):
        async def close(self, *args: Any, **kwargs: Any) -> None:
            closing.set()
            await super().close(*args, **kwargs)

    async def handler(socket: ServerConnection) -> None:
        try:
            await socket.send(json.dumps({"type": "auth_required"}))
            assert json.loads(await socket.recv()) == {"type": "auth", "access_token": TOKEN}
            await socket.send(json.dumps({"type": "auth_ok"}))
            command = json.loads(await socket.recv())
            assert command["service_data"] == {"assertion": ASSERTION}
            socket.transport.pause_reading()
            if not stall_response:
                await socket.send(json.dumps(result()))
            await finish.wait()
        finally:
            socket.transport.abort()

    async with serve(handler, "127.0.0.1", 0, logger=silent_logger()) as server:
        port = server.sockets[0].getsockname()[1]

        @asynccontextmanager
        async def connector(endpoint: str, **kwargs: Any) -> AsyncIterator[ClientConnection]:
            assert endpoint == "ws://supervisor/core/websocket"
            async with connect(
                f"ws://127.0.0.1:{port}", create_connection=TrackedConnection, **kwargs
            ) as socket:
                connections.append(socket)
                yield socket

        try:
            yield connector, connections, closing
        finally:
            for socket in connections:
                socket.transport.abort()
                await socket.wait_closed()
            finish.set()


@pytest.mark.asyncio
async def test_real_websocket_cancellation_during_close_aborts_before_propagating(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    before = asyncio.all_tasks()
    async with uncooperative_peer() as (connector, connections, closing):
        transport = module().HaHealthServiceClient(
            supervisor_token=TOKEN, connector=connector, timeout_seconds=1.0
        )
        task = asyncio.create_task(transport.get_health_context(ASSERTION))
        await asyncio.wait_for(closing.wait(), 0.5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(connections) == 1
        assert connections[0].transport.is_closing()
        assert connections[0].protocol.state is CLOSED
        assert connections[0].keepalive_task is None
    assert asyncio.all_tasks() == before
    assert all(private not in caplog.text for private in (TOKEN, ASSERTION, SENTINEL))


@pytest.mark.asyncio
async def test_real_websocket_stalled_response_close_has_no_fresh_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    before = asyncio.all_tasks()
    async with uncooperative_peer(stall_response=True) as (connector, connections, _):
        timeout_seconds = 0.25
        transport = module().HaHealthServiceClient(
            supervisor_token=TOKEN, connector=connector, timeout_seconds=timeout_seconds
        )
        started = time.monotonic()
        failure = await transport.get_health_context(ASSERTION)
        elapsed = time.monotonic() - started
        assert elapsed < timeout_seconds + 0.10, f"Operation consumed {elapsed:.3f}s"
        assert isinstance(failure, module().HaHealthServiceFailure)
        assert len(connections) == 1
        assert connections[0].transport.is_closing()
        assert connections[0].protocol.state is CLOSED
    assert asyncio.all_tasks() == before
    assert all(private not in caplog.text for private in (TOKEN, ASSERTION, SENTINEL))


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [300, 301, 302, 303, 307, 308])
async def test_real_production_connector_rejects_redirect_without_second_connection_or_token(
    status: int, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    before = asyncio.all_tasks()
    source_connections: list[bytes] = []
    redirected_connections: list[object] = []
    redirect_finished = asyncio.Event()

    async def redirected_peer(socket: ServerConnection) -> None:
        redirected_connections.append(None)
        await socket.send(json.dumps({"type": "auth_required"}))
        redirected_connections.append(json.loads(await socket.recv()))
        await socket.send(json.dumps({"type": "auth_ok"}))
        await socket.recv()
        await socket.send(json.dumps(result()))

    async with serve(redirected_peer, "127.0.0.1", 0, logger=silent_logger()) as target:
        target_port = target.sockets[0].getsockname()[1]

        async def redirect(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                source_connections.append(await reader.readuntil(b"\r\n\r\n"))
                writer.write(
                    f"HTTP/1.1 {status} Redirect\r\n"
                    f"Location: ws://127.0.0.1:{target_port}/redirected\r\n"
                    "Content-Length: 0\r\nConnection: close\r\n\r\n".encode()
                )
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()
                redirect_finished.set()

        async with await asyncio.start_server(redirect, "127.0.0.1", 0) as source:
            source_port = source.sockets[0].getsockname()[1]
            monkeypatch.setattr(module(), "_ENDPOINT", f"ws://127.0.0.1:{source_port}")
            transport = module().HaHealthServiceClient(supervisor_token=TOKEN)
            failure = await transport.get_health_context(ASSERTION)
            await redirect_finished.wait()
            assert isinstance(failure, module().HaHealthServiceFailure)
            assert len(source_connections) == 1
            assert redirected_connections == []
            assert TOKEN.encode() not in source_connections[0]
    assert asyncio.all_tasks() == before
    assert all(private not in caplog.text for private in (TOKEN, ASSERTION, SENTINEL))
