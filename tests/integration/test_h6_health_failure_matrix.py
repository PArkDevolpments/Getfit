"""Permanent H6 failure QA through the real signer, transport and closed reader.

Only the external HA peer is synthetic. Reusing a successful projection, retrying
the peer, logging private frames or invoking workout export must fail these tests.
"""

import asyncio
import base64
import importlib.util
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.protocol import CLOSED

from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceClient
from hwa.integrations.pep.health_reader import PepHealthReader
from hwa.integrations.pep.service_assertion import ServiceAssertionSigner
from hwa.runtime import build_pep_health_reader


def load_test_module(name, path):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


responses = load_test_module("h6_matrix_responses", "fixtures/pep_health_service_responses.py")
FAILURES = (
    "getfit-disabled",
    "authority-disabled",
    "quarantine",
    "invalid-assertion",
    "person-unavailable",
    "rate-limit",
    "rebuild-timeout",
    "overload",
    "compute-failure",
    "integrity-failure",
    "socket-refusal",
    "auth-failure",
    "malformed-frame",
    "operation-timeout",
    "cancellation",
)
ERRORS = {
    "authority-disabled": (503, "HEALTH_AUTHORITY_DISABLED"),
    "quarantine": (503, "SERVICE_ASSERTION_STARTUP_QUARANTINE"),
    "invalid-assertion": (401, "INVALID_SERVICE_ASSERTION"),
    "person-unavailable": (403, "PERSON_CONTEXT_UNAVAILABLE"),
    "rate-limit": (429, "ASSERTION_RATE_LIMITED"),
    "rebuild-timeout": (503, "REBUILD_TIMEOUT"),
    "overload": (503, "OVERLOADED"),
    "compute-failure": (500, "COMPUTE_FAILED"),
    "integrity-failure": (500, "INTEGRITY_FAILED"),
}


def person(suffix="a"):
    return PersonContext(
        hwa_person_id=f"synthetic-local-{suffix}",
        pep_person_id=f"synthetic-pep-{suffix}",
        health_profile_id=f"synthetic-profile-{suffix}",
        menu_person_id=f"synthetic-menu-{suffix}",
        presentation_profile="male" if suffix == "a" else "female",
        display_name=f"Synthetic {suffix.upper()}",
    )


class HealthHarness:
    """Verify real signatures and record the actual selector-free HA wire boundary."""

    token = "synthetic-supervisor-token-secret"
    payload_secret = "synthetic-health-payload-secret"

    def __init__(self, *, key=None, persons=None):
        self.key = key or Ed25519PrivateKey.generate()
        self.persons = persons or {
            "synthetic-ha-a": ("synthetic-pep-a", "synthetic-profile-a", 81.3),
            "synthetic-ha-b": ("synthetic-pep-b", "synthetic-profile-b", 62.4),
        }
        self.failure = None
        self.retry_after = "35"
        self.connections = []
        self.commands = []
        counter = iter(range(1000))
        self.signer = RecordingSigner(
            ServiceAssertionSigner(
                "synthetic-key",
                self.key,
                lambda: 1790841600.0,
                lambda: f"synthetic-private-jti-{next(counter)}",
            ),
            self.key.public_key(),
        )
        self.assertions = self.signer.assertions
        self.subjects = self.signer.subjects
        self.jtis = self.signer.jtis
        self.transport = HaHealthServiceClient(
            supervisor_token=self.token,
            connector=self.connector,
            timeout_seconds=0.03,
        )
        self.reader = PepHealthReader(service_client=self.transport, signer=self.signer)

    @asynccontextmanager
    async def connector(self, endpoint, **options):
        assert endpoint == "ws://supervisor/core/websocket"
        assert options["proxy"] is None and options["ping_interval"] is None
        peer = HealthPeer(self)
        self.connections.append(peer)
        try:
            if self.failure == "socket-refusal":
                raise ConnectionRefusedError(self.payload_secret + self.token)
            yield peer
        finally:
            peer.closed = True

    def assert_private_logs(self, caplog):
        private = [
            self.token,
            self.payload_secret,
            base64.b64encode(self.key.private_bytes_raw()).decode(),
            base64.b64encode(self.key.public_key().public_bytes_raw()).decode(),
            self.key.private_bytes_raw().hex(),
            self.key.public_key().public_bytes_raw().hex(),
            *self.assertions,
            *self.subjects,
            *self.jtis,
        ]
        for assertion in self.assertions:
            private.extend(assertion.split("."))
        for pep_id, profile, value in self.persons.values():
            private.extend((pep_id, profile, str(value)))
        assert all(value not in caplog.text for value in private)


class RecordingSigner:
    """Observe the real signer's output before connection/authentication can fail."""

    def __init__(self, signer, public_key):
        self.signer = signer
        self.public_key = public_key
        self.assertions = []
        self.subjects = []
        self.jtis = []

    def sign(self, subject):
        assertion = self.signer.sign(subject)
        header, payload, signature = assertion.split(".")
        self.public_key.verify(
            base64.urlsafe_b64decode(signature + "=="),
            f"{header}.{payload}".encode("ascii"),
        )
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        assert claims["sub"] == subject
        self.assertions.append(assertion)
        self.subjects.append(claims["sub"])
        self.jtis.append(claims["jti"])
        return assertion


class HealthPeer:
    def __init__(self, harness):
        self.harness = harness
        self.closed = False
        self.receives = 0
        self.projection = None

    async def send(self, raw):
        message = json.loads(raw)
        harness = self.harness
        if message["type"] == "auth":
            assert message == {"type": "auth", "access_token": harness.token}
            return
        assert set(message) == {
            "id",
            "type",
            "domain",
            "service",
            "service_data",
            "return_response",
        }
        assert message["id"] == 1 and message["return_response"] is True
        assert message["domain"] == "peptide_site"
        assert message["type"] == "call_service" and message["service"] == "get_health_context"
        assert set(message["service_data"]) == {"assertion"}
        assertion = message["service_data"]["assertion"]
        header, payload, signature = assertion.split(".")
        harness.key.public_key().verify(
            base64.urlsafe_b64decode(signature + "=="),
            f"{header}.{payload}".encode("ascii"),
        )
        claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
        harness.commands.append(message)
        assert assertion in harness.assertions
        pep_id, profile, value = harness.persons[claims["sub"]]
        self.projection = responses.ready_projection(person_id=pep_id, health_profile_id=profile)
        self.projection["body"]["body_mass"]["value"] = value
        self.projection["journey"]["flags"] = [harness.payload_secret]
        self.projection["body"]["body_mass"]["reason"] = harness.payload_secret

    async def recv(self):
        self.receives += 1
        if self.receives == 1:
            return '{"type":"auth_required"}'
        if self.receives == 2:
            kind = "auth_invalid" if self.harness.failure == "auth-failure" else "auth_ok"
            return json.dumps({"type": kind, "message": self.harness.payload_secret})
        failure = self.harness.failure
        if failure == "operation-timeout":
            await asyncio.Event().wait()
        if failure == "cancellation":
            raise asyncio.CancelledError
        if failure == "malformed-frame":
            return '{"private":"' + self.harness.payload_secret + '"'
        response = responses.service_response(self.projection)
        if failure in ERRORS:
            status, error = ERRORS[failure]
            response = responses.service_response(
                {"error": error, "private": self.harness.payload_secret},
                status_code=status,
            )
            response["headers"]["Retry-After"] = self.harness.retry_after
        return json.dumps(responses.websocket_result(response))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", FAILURES)
async def test_failure_is_request_scoped_and_never_falls_back_or_retries(
    failure,
    monkeypatch,
    caplog,
):
    # A cache, fallback export, retry, or swallowed cancellation breaks this test.
    caplog.set_level(logging.DEBUG)
    import httpx

    import hwa.api.pep_export as export_api
    import hwa.integrations.pep.workout_export as export_module
    import hwa.services.workout_drafts as drafts
    import hwa.services.workout_evidence as evidence

    def forbidden(*args, **kwargs):
        pytest.fail("Health read recursively invoked workout export")

    monkeypatch.setattr(export_api.PepWorkoutSourceProvider, "records", forbidden)
    monkeypatch.setattr(export_api, "export_workouts_for_pep", forbidden)
    monkeypatch.setattr(export_module, "export_workouts_for_pep", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "get", forbidden)
    monkeypatch.setattr(httpx.Client, "get", forbidden)
    monkeypatch.setattr(drafts, "create_draft", forbidden)
    monkeypatch.setattr(evidence, "complete_workout", forbidden)
    harness = HealthHarness()
    before = asyncio.all_tasks()
    first = await harness.reader.read(ha_user_id="synthetic-ha-a", person=person())
    assert first.status == "READY" and first.body["body_mass"].value == 81.3
    # Height and mass are available, but Getfit must not calculate missing Pep BMI.
    assert first.body["bmi"].status == "unavailable" and first.body["bmi"].value is None
    assert first.progress.total_weight_loss_28d_kg == 1.0
    harness.failure = failure
    reader = harness.reader
    if failure == "getfit-disabled":
        monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", "false")
        monkeypatch.setattr("hwa.runtime.load_service_assertion_signer", forbidden)
        monkeypatch.setattr("hwa.runtime.HaHealthServiceClient", forbidden)
        reader = build_pep_health_reader()
    if failure == "cancellation":
        with pytest.raises(asyncio.CancelledError):
            await reader.read(ha_user_id="synthetic-ha-b", person=person("b"))
    else:
        failed = await reader.read(ha_user_id="synthetic-ha-b", person=person("b"))
        assert failed.status == "UNAVAILABLE"
        expected = (
            "GETFIT_PEP_HEALTH_DISABLED"
            if failure == "getfit-disabled"
            else ERRORS[failure][1]
            if failure
            in {
                "authority-disabled",
                "quarantine",
                "invalid-assertion",
                "person-unavailable",
                "rate-limit",
            }
            else "PEP_HEALTH_UNAVAILABLE"
        )
        assert failed.reason == expected
        assert failed.body == failed.recovery == failed.sleep == {}
        assert failed.progress is None and failed.health_profile_id is None
        assert failed.exported_at is None and failed.latest_recorded_at is None
        assert (
            "Retry-After" not in failed.model_dump_json() and "81.3" not in failed.model_dump_json()
        )
    expected_calls = 1 if failure in {"getfit-disabled", "socket-refusal", "auth-failure"} else 2
    assert len(harness.assertions) == (1 if failure == "getfit-disabled" else 2)
    assert harness.subjects == (
        ["synthetic-ha-a"] if failure == "getfit-disabled" else ["synthetic-ha-a", "synthetic-ha-b"]
    )
    assert len(harness.commands) == expected_calls
    assert len(harness.connections) == (1 if failure == "getfit-disabled" else 2)
    assert all(peer.closed for peer in harness.connections)
    assert asyncio.all_tasks() == before
    harness.failure = None
    recovered = await harness.reader.read(ha_user_id="synthetic-ha-b", person=person("b"))
    assert recovered.status == "READY" and recovered.body["body_mass"].value == 62.4
    assert "81.3" not in recovered.model_dump_json()
    assert harness.subjects[-1] == "synthetic-ha-b"
    assert len(set(harness.assertions)) == len(harness.assertions)
    assert len(harness.commands) == expected_calls + 1
    assert all(peer.closed for peer in harness.connections)
    assert asyncio.all_tasks() == before
    harness.assert_private_logs(caplog)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["socket-refusal", "auth-failure"])
@pytest.mark.parametrize("component", ["assertion", "signature", "jti", "subject"])
async def test_privacy_probe_rejects_failed_assertion_component_log(failure, component, caplog):
    # Inject a logging regression after real signing but before any service command.
    caplog.set_level(logging.DEBUG)
    harness = HealthHarness()
    harness.failure = failure
    result = await harness.reader.read(ha_user_id="synthetic-ha-b", person=person("b"))
    assert result.status == "UNAVAILABLE"
    assert len(harness.assertions) == 1 and harness.commands == []
    private = {
        "assertion": harness.assertions[0],
        "signature": harness.assertions[0].split(".")[2],
        "jti": harness.jtis[0],
        "subject": harness.subjects[0],
    }[component]
    harness.assert_private_logs(caplog)
    # Disable live/stderr logging while retaining caplog's handler for this mutation.
    record = logging.LogRecord(
        "h6.private-log-mutation", logging.DEBUG, "", 0, "%s", (private,), None
    )
    caplog.handler.handle(record)
    with pytest.raises(AssertionError):
        harness.assert_private_logs(caplog)
    caplog.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["authority-disabled", "quarantine", "rate-limit"])
@pytest.mark.parametrize(
    "retry_after",
    [
        "35",
        "9999999999999999999999999",
        "-1",
        "NaN",
        "synthetic-health-payload-secret\r\nSet-Cookie: private",
    ],
)
async def test_untrusted_retry_metadata_cannot_delay_or_escape(failure, retry_after, caplog):
    caplog.set_level(logging.DEBUG)
    harness = HealthHarness()
    harness.failure, harness.retry_after = failure, retry_after
    # Enforced outer deadline detects sleeping on even valid quarantine metadata.
    result = await asyncio.wait_for(
        harness.reader.read(ha_user_id="synthetic-ha-a", person=person()),
        0.3,
    )
    assert result.status == "UNAVAILABLE" and result.reason == ERRORS[failure][1]
    assert len(harness.connections) == len(harness.commands) == 1
    assert result.body == {} and "retry" not in result.model_dump_json().lower()
    assert retry_after not in result.model_dump_json()
    assert retry_after not in caplog.text
    harness.assert_private_logs(caplog)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome", ["valid-response-stalled-close", "malformed", "timeout", "cancel"]
)
async def test_real_websocket_lifecycle_has_no_surviving_socket_or_task(outcome, caplog):
    # Task 3's real websockets seam includes peers that refuse Close acknowledgement.
    seam = load_test_module("h6_real_lifecycle", "unit/integrations/pep/test_ha_health_service.py")
    caplog.set_level(logging.DEBUG)
    before = asyncio.all_tasks()
    async with seam.uncooperative_peer(stall_response=outcome == "timeout") as (
        connector,
        connections,
        closing,
    ):
        transport = HaHealthServiceClient(
            supervisor_token=seam.TOKEN,
            connector=connector,
            timeout_seconds=0.25 if outcome != "cancel" else 1.0,
        )
        if outcome == "malformed":
            original = seam.result
            seam.result = lambda: {**original(), "id": 99}
        task = asyncio.create_task(transport.get_health_context(seam.ASSERTION))
        if outcome == "cancel":
            await asyncio.wait_for(closing.wait(), 0.5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await task
            # Even a valid response becomes unavailable if Close exhausts its budget.
            assert result.reason == "PEP_HEALTH_UNAVAILABLE"
        assert len(connections) == 1
        assert connections[0].transport.is_closing()
        assert connections[0].protocol.state is CLOSED
        assert connections[0].keepalive_task is None
    assert asyncio.all_tasks() == before
    assert all(value not in caplog.text for value in (seam.TOKEN, seam.ASSERTION, seam.SENTINEL))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "malformed-frame", "auth-failure"])
async def test_real_websocket_success_and_failure_release_request_resources(failure, caplog):
    seam = load_test_module(
        "h6_cooperative_lifecycle", "unit/integrations/pep/test_ha_health_service.py"
    )
    harness = HealthHarness()
    harness.failure = failure
    connections = []
    caplog.set_level(logging.DEBUG)
    before = asyncio.all_tasks()

    async def handler(socket):
        peer = HealthPeer(harness)
        await socket.send(await peer.recv())
        await peer.send(await socket.recv())
        await socket.send(await peer.recv())
        if failure != "auth-failure":
            await peer.send(await socket.recv())
            await socket.send(await peer.recv())
        await socket.wait_closed()

    async with serve(handler, "127.0.0.1", 0, logger=seam.silent_logger()) as server:
        port = server.sockets[0].getsockname()[1]

        @asynccontextmanager
        async def connector(endpoint, **kwargs):
            assert endpoint == "ws://supervisor/core/websocket"
            async with connect(f"ws://127.0.0.1:{port}", **kwargs) as socket:
                connections.append(socket)
                yield socket

        transport = HaHealthServiceClient(
            supervisor_token=harness.token,
            connector=connector,
            timeout_seconds=1.0,
        )
        reader = PepHealthReader(service_client=transport, signer=harness.signer)
        result = await reader.read(ha_user_id="synthetic-ha-a", person=person())
        assert result.status == ("READY" if failure is None else "UNAVAILABLE")
        if failure is None:
            assert result.body["body_mass"].value == 81.3
        else:
            assert result.body == {}
        assert len(connections) == 1
        assert connections[0].protocol.state is CLOSED
        assert connections[0].transport.is_closing()
        assert connections[0].keepalive_task is None
    assert asyncio.all_tasks() == before
    harness.assert_private_logs(caplog)
