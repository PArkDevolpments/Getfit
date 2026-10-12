"""Permanent H6 authority, identity and transport boundary tests.

Signer and service doubles replace external signing/HA I/O only. Assertions
observe reader output and the assertion-only request boundary, never fake output.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest

from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceEnvelope
from hwa.integrations.pep.health_reader import PepHealthReader

# The repository's tests directory is not a Python package. Load the standalone
# fixture module without changing global import paths or production packaging.
_spec = importlib.util.spec_from_file_location(
    "pep_health_service_responses",
    Path(__file__).parents[1] / "fixtures" / "pep_health_service_responses.py",
)
assert _spec is not None and _spec.loader is not None
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)
governed_error = _fixtures.governed_error
ready_projection = _fixtures.ready_projection
service_response = _fixtures.service_response
websocket_result = _fixtures.websocket_result


def person() -> PersonContext:
    return PersonContext(
        hwa_person_id="synthetic-local-a",
        pep_person_id="synthetic-person-a",
        health_profile_id="synthetic-profile-a",
        menu_person_id="synthetic-menu-a",
        presentation_profile="synthetic",
        display_name="Synthetic A",
    )


class AssertionSigner:
    def __init__(self) -> None:
        self.subjects: list[str] = []

    def sign(self, subject: str) -> str:
        self.subjects.append(subject)
        return f"synthetic-assertion-{len(self.subjects)}"


class HealthService:
    def __init__(self, response: object) -> None:
        # Mirror the Task 3 seam: the reader receives a typed service envelope,
        # while the real transport below still validates complete raw frames.
        if isinstance(response, dict):
            self.response = HaHealthServiceEnvelope(
                status_code=response["status_code"],
                body=response["body"],
                headers=response["headers"],
            )
        else:
            self.response = response
        self.assertions: list[str] = []

    async def get_health_context(self, assertion: str) -> object:
        # A single assertion argument deliberately forbids person/profile selectors.
        self.assertions.append(assertion)
        return self.response


def bound_reader(service: HealthService, signer: AssertionSigner) -> Any:
    try:
        return PepHealthReader(service_client=service, signer=signer)  # type: ignore[arg-type]
    except TypeError:
        pytest.fail("Missing H6 PepHealthReader(service_client=..., signer=...) boundary")


def assert_closed(result: Any, reason: str) -> None:
    assert result.status == "UNAVAILABLE"
    assert result.reason == reason
    assert result.pep_person_id == "synthetic-person-a"
    assert result.body == {}
    assert result.recovery == {}
    assert result.sleep == {}
    assert result.progress is None


@pytest.mark.asyncio
async def test_trusted_subject_is_signed_and_only_fresh_assertion_reaches_service() -> None:
    signer = AssertionSigner()
    service = HealthService(service_response())
    reader = bound_reader(service, signer)
    first = await reader.read(ha_user_id="synthetic-ha-subject-a", person=person())
    second = await reader.read(ha_user_id="synthetic-ha-subject-a", person=person())

    assert first.status == second.status == "READY"
    assert first.body["body_mass"].value == 80.0
    assert first.health_profile_id == "synthetic-profile-a"
    assert signer.subjects == ["synthetic-ha-subject-a", "synthetic-ha-subject-a"]
    assert service.assertions == ["synthetic-assertion-1", "synthetic-assertion-2"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason", ["HEALTH_AUTHORITY_DISABLED", "SERVICE_ASSERTION_STARTUP_QUARANTINE"]
)
async def test_governed_service_errors_preserve_only_allowlisted_reason(reason: str) -> None:
    reader = bound_reader(
        HealthService(service_response({"error": reason}, status_code=503)), AssertionSigner()
    )
    result = await reader.read(ha_user_id="synthetic-ha-subject-a", person=person())
    assert_closed(result, reason)


def invalid_responses() -> list[Any]:
    cases: list[Any] = []
    for field, value, reason in [
        ("schema", "wrong-schema", "CONTRACT_SCHEMA_MISMATCH"),
        ("authority", "OTHER_HEALTH", "CONTRACT_SCHEMA_MISMATCH"),
        ("schema_version", True, "CONTRACT_SCHEMA_MISMATCH"),
        ("person_id", "synthetic-person-b", "PERSON_CONTEXT_MISMATCH"),
        ("health_profile_id", "synthetic-profile-b", "HEALTH_PROFILE_MISMATCH"),
        ("private_notes", "synthetic-private-sentinel", "INVALID_CONTRACT"),
        ("automatic_action", True, "INVALID_CONTRACT"),
        ("causation_asserted", True, "INVALID_CONTRACT"),
    ]:
        body = ready_projection()
        body[field] = value
        cases.append(pytest.param(service_response(body), reason, id=field))
    body = ready_projection()
    body["body"]["body_mass"]["value"] = True
    cases.append(pytest.param(service_response(body), "INVALID_CONTRACT", id="boolean-metric"))
    cases.append(
        pytest.param(
            service_response({"error": "synthetic-private-sentinel"}, status_code=503),
            "PEP_HEALTH_UNAVAILABLE",
            id="unknown-error",
        )
    )
    return cases


def invalid_frames() -> list[Any]:
    cases: list[Any] = []
    for name, envelope in [
        ("not-object", []),
        ("wrong-id", {**websocket_result(), "id": 2}),
        ("wrong-frame-type", {**websocket_result(), "type": "event"}),
        ("numeric-success", {**websocket_result(), "success": 1}),
        ("missing-response", {"id": 1, "type": "result", "success": True, "result": {}}),
        (
            "ha-failure",
            {
                "id": 1,
                "type": "result",
                "success": False,
                "error": {"message": "synthetic-private-sentinel"},
            },
        ),
        (
            "missing-no-store",
            websocket_result({"status_code": 200, "body": ready_projection(), "headers": {}}),
        ),
        (
            "boolean-status",
            websocket_result(
                {
                    "status_code": True,
                    "body": ready_projection(),
                    "headers": {"Cache-Control": "no-store"},
                }
            ),
        ),
    ]:
        cases.append(pytest.param(envelope, id=name))
    return cases


@pytest.mark.asyncio
@pytest.mark.parametrize(("response", "reason"), invalid_responses())
async def test_service_read_discards_invalid_or_cross_person_context(
    response: object, reason: str
) -> None:
    reader = bound_reader(HealthService(response), AssertionSigner())
    result = await reader.read(ha_user_id="synthetic-ha-subject-a", person=person())
    assert_closed(result, reason)


class WebSocketPeer:
    """External HA peer; production client owns authentication and frame parsing."""

    def __init__(self, response: object) -> None:
        self.frames = iter(
            [
                {"type": "auth_required", "ha_version": "synthetic"},
                {"type": "auth_ok", "ha_version": "synthetic"},
                response,
            ]
        )
        self.sent: list[dict[str, Any]] = []

    async def send(self, frame: str) -> None:
        self.sent.append(json.loads(frame))

    async def recv(self) -> str:
        return json.dumps(next(self.frames))


def service_client(peer: WebSocketPeer) -> Any:
    @asynccontextmanager
    async def connector(endpoint: str, **kwargs: Any) -> Any:
        yield peer

    spec = importlib.util.find_spec("hwa.integrations.pep.ha_health_service")
    assert spec is not None, "Missing H6 HaHealthServiceClient transport boundary"
    module = importlib.import_module("hwa.integrations.pep.ha_health_service")
    return module.HaHealthServiceClient(
        supervisor_token="synthetic-supervisor-token", connector=connector
    )


@pytest.mark.asyncio
async def test_ha_client_emits_exact_selector_free_service_command() -> None:
    peer = WebSocketPeer(websocket_result())
    reader = bound_reader(service_client(peer), AssertionSigner())
    result = await reader.read(ha_user_id="synthetic-ha-subject-a", person=person())
    assert result.status == "READY"
    assert peer.sent == [
        {"type": "auth", "access_token": "synthetic-supervisor-token"},
        {
            "id": 1,
            "type": "call_service",
            "domain": "peptide_site",
            "service": "get_health_context",
            "service_data": {"assertion": "synthetic-assertion-1"},
            "return_response": True,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", invalid_frames())
async def test_ha_client_rejects_invalid_frames_before_reader_sees_payload(frame: object) -> None:
    reader = bound_reader(service_client(WebSocketPeer(frame)), AssertionSigner())
    result = await reader.read(ha_user_id="synthetic-ha-subject-a", person=person())
    assert_closed(result, "PEP_HEALTH_UNAVAILABLE")


@pytest.mark.asyncio
async def test_legacy_direct_http_reader_cannot_consume_ha_service_envelope() -> None:
    requests: list[httpx.Request] = []

    def handler(_: httpx.Request) -> httpx.Response:
        requests.append(_)
        return httpx.Response(200, json=websocket_result())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TypeError):
            PepHealthReader(client)  # type: ignore[call-arg]
    assert requests == []
