"""Real H6 wire reads remain private through the trusted web/person boundary."""

import asyncio
import base64
import importlib.util
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from types import (
    BuiltinFunctionType,
    FunctionType,
    MemberDescriptorType,
    MethodType,
    ModuleType,
    SimpleNamespace,
)

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker
from websockets.asyncio.client import ClientConnection

from hwa.integrations.pep.health_reader import PepHealthContext, PepHealthContractV1
from hwa.runtime import build_pep_health_reader

_spec = importlib.util.spec_from_file_location(
    "h6_e2e_matrix",
    Path(__file__).parents[1] / "integration/test_h6_health_failure_matrix.py",
)
assert _spec is not None and _spec.loader is not None
matrix = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(matrix)
identity = matrix.load_test_module("h6_e2e_identity", "integration/web/test_h6_health_identity.py")


@pytest.fixture
def wire_app(tmp_path):
    existing = identity.bound_app.__wrapped__(tmp_path)
    client, app, service = next(existing)
    harness = matrix.HealthHarness(key=service.key)
    harness.day_id = service.day_id
    app.state.pep_health_reader = harness.reader
    try:
        yield client, app, harness
    finally:
        existing.close()


def assert_browser_private(response, harness):
    assert response.status_code == 200
    identity._private_absent(response)
    for sentinel in (
        matrix.HealthHarness.token,
        matrix.HealthHarness.payload_secret,
        "Retry-After",
        "HEALTH_AUTHORITY_DISABLED",
        "ASSERTION_RATE_LIMITED",
        "SERVICE_ASSERTION_STARTUP_QUARANTINE",
        "synthetic-private-jti-",
    ):
        assert sentinel not in response.text
        assert sentinel not in json.dumps(dict(response.headers))
    for assertion in harness.assertions:
        for private in (assertion, *assertion.split(".")):
            assert private not in response.text
            assert private not in json.dumps(dict(response.headers))


def assert_no_health_in_application_state(app, harness):
    """Follow owned state and arbitrary wrappers; never repr/serialize dependencies.

    Only exact immutable Health dependencies and external test instrumentation are
    excluded by identity. Crypto, database factories, sockets and executable code
    are opaque infrastructure, not request projection storage. Readers themselves
    (including a disabled replacement and the original reader) are always walked.
    """
    visited = set()
    excluded_ids = {id(harness), id(harness.transport), id(harness.signer)}
    opaque_types = (
        Engine,
        sessionmaker,
        Ed25519PrivateKey,
        Ed25519PublicKey,
        ClientConnection,
        asyncio.BaseTransport,
        asyncio.Future,
        logging.Logger,
        FunctionType,
        BuiltinFunctionType,
        MethodType,
        ModuleType,
        type,
    )
    private_strings = (
        "81.3",
        "62.4",
        "synthetic-pep-",
        "synthetic-profile-",
        "synthetic-ha-",
        "synthetic-local-",
        harness.payload_secret,
        "synthetic-private-jti-",
        *harness.assertions,
    )

    def walk(value):
        if id(value) in visited or id(value) in excluded_ids:
            return
        visited.add(id(value))
        if isinstance(value, (PepHealthContext, PepHealthContractV1)):
            raise AssertionError("Retained Health context in application state")
        if isinstance(value, str):
            if any(private in value for private in private_strings):
                raise AssertionError("Retained Health or identity sentinel in application state")
            return
        if isinstance(value, bytes):
            if any(private.encode() in value for private in private_strings):
                raise AssertionError("Retained Health or identity bytes in application state")
            return
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value in (81.3, 62.4):
                raise AssertionError("Retained Health metric in application state")
            return
        if value is None or isinstance(value, (bool, *opaque_types)):
            return
        if isinstance(value, Mapping):
            for key, item in value.items():
                walk(key)
                walk(item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                walk(item)
        else:
            # Read storage only; never execute properties or repr hooks.
            attributes = getattr(value, "__dict__", {})
            for item in attributes.values():
                walk(item)
            for cls in type(value).__mro__:
                for descriptor in cls.__dict__.values():
                    if isinstance(descriptor, MemberDescriptorType):
                        try:
                            # Actual storage descriptors include mangled private names
                            # and directly read inherited slots without property lookup.
                            walk(descriptor.__get__(value, type(value)))
                        except AttributeError:
                            pass

    walk(app.state._state)
    walk(harness.reader)


@pytest.mark.asyncio
@pytest.mark.parametrize("location", ["reader", "app-state"])
@pytest.mark.parametrize("suffix", ["a", "b"])
@pytest.mark.parametrize("wrapper_kind", ["namespace", "private-slot"])
async def test_recursive_state_probe_rejects_wrapped_prior_success_after_failed_read(
    wire_app,
    location,
    suffix,
    wrapper_kind,
):
    _, app, harness = wire_app
    first = await harness.reader.read(ha_user_id="synthetic-ha-a", person=matrix.person())
    assert first.status == "READY"
    harness.failure = "authority-disabled"
    failed = await harness.reader.read(
        ha_user_id=f"synthetic-ha-{suffix}", person=matrix.person(suffix)
    )
    assert failed.status == "UNAVAILABLE"
    assert_no_health_in_application_state(app, harness)
    wrapper = SimpleNamespace()
    wrapper.cycle = wrapper
    wrapper.nested = [{"context": SimpleNamespace(context=first)}]
    if wrapper_kind == "private-slot":

        class PrivateCache:
            __slots__ = ("__context", "cycle")

            def __init__(self, context):
                self.__context = context
                self.cycle = self

            @property
            def context(self):
                pytest.fail("State probe executed a property")

        wrapper = PrivateCache(first)
    owner = harness.reader if location == "reader" else app.state
    owner._cache = wrapper
    try:
        with pytest.raises(AssertionError, match="Retained Health context"):
            assert_no_health_in_application_state(app, harness)
    finally:
        del owner._cache
    assert_no_health_in_application_state(app, harness)


@pytest.mark.parametrize("failure", [value for value in matrix.FAILURES if value != "cancellation"])
def test_success_failure_person_switch_and_recovery_never_retain_health(
    wire_app,
    failure,
    monkeypatch,
    caplog,
):
    # A retained projection in app state, browser JSON or the next command breaks this sequence.
    client, app, harness = wire_app
    caplog.set_level(logging.DEBUG)
    first = client.get("/", headers=identity._headers())
    assert "81.3 kg" in first.text and "62.4 kg" not in first.text
    assert_browser_private(first, harness)
    assert_no_health_in_application_state(app, harness)
    harness.failure = failure
    harness.retry_after = "99999999999999999999\r\nprivate-retry-secret"
    if failure == "getfit-disabled":
        monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", "false")
        app.state.pep_health_reader = build_pep_health_reader()
    for suffix in ("a", "b"):
        failed = client.get("/", headers=identity._headers(suffix))
        assert_browser_private(failed, harness)
        assert 'class="home-context-rail"' not in failed.text
        assert "81.3" not in failed.text and "62.4" not in failed.text
        assert "private-retry-secret" not in failed.text
        if suffix == "b":
            assert "Synthetic A" not in failed.text
        assert_no_health_in_application_state(app, harness)
    harness.failure = None
    app.state.pep_health_reader = harness.reader
    second = client.get("/", headers=identity._headers("b"))
    assert_browser_private(second, harness)
    assert "62.4 kg" in second.text and "81.3" not in second.text
    assert "Synthetic A" not in second.text
    last = harness.commands[-1]
    assert set(last["service_data"]) == {"assertion"}
    assert harness.subjects[-1] == "synthetic-ha-b"
    claims = json.loads(
        base64.urlsafe_b64decode(last["service_data"]["assertion"].split(".")[1] + "==")
    )
    assert claims["sub"] == "synthetic-ha-b"
    assert len(harness.assertions) == len(set(harness.assertions))
    assert_no_health_in_application_state(app, harness)
    assert all(peer.closed for peer in harness.connections)
    assert "private-retry-secret" not in caplog.text
    harness.assert_private_logs(caplog)


@pytest.mark.asyncio
async def test_cancelled_person_switch_leaves_no_prior_context_and_next_request_works(
    wire_app, caplog
):
    client, app, harness = wire_app
    caplog.set_level(logging.DEBUG)
    first = client.get("/", headers=identity._headers())
    assert "81.3 kg" in first.text
    before = asyncio.all_tasks()
    harness.failure = "cancellation"
    with pytest.raises(asyncio.CancelledError):
        await harness.reader.read(ha_user_id="synthetic-ha-b", person=matrix.person("b"))
    assert asyncio.all_tasks() == before
    assert all(peer.closed for peer in harness.connections)
    assert_no_health_in_application_state(app, harness)
    harness.failure = None
    second = client.get("/", headers=identity._headers("b"))
    assert_browser_private(second, harness)
    assert "62.4 kg" in second.text and "81.3" not in second.text
    assert "Synthetic A" not in second.text
    for path in ("/plan", "/workout", "/progress", "/more"):
        assert client.get(path, headers=identity._headers("b")).status_code == 200
    headers = identity._headers("b")
    created = client.post(
        "/api/v1/workouts/drafts",
        headers=headers,
        json={
            "programme_day_id": harness.day_id,
            "snapshot": {"phase": "WORKOUT_READY", "state_data": {}},
            "started_at": "2026-10-01T07:00:00Z",
        },
    )
    assert created.status_code == 201
    draft = created.json()
    assert 'data-primary-action="resume"' in client.get("/", headers=headers).text
    journey = matrix.load_test_module("h6_cancel_journey", "e2e/test_full_training_journey.py")
    completed = client.post(
        f"/api/v1/workouts/drafts/{draft['draft_id']}/complete",
        headers=headers,
        json={
            "idempotency_key": "h6-cancel-complete",
            "completed_at": "2026-10-01T07:42:00Z",
            "event": journey._event_payload(),
        },
    )
    assert completed.status_code == 201 and completed.json()["revision_number"] == 1
    assert completed.json()["event"]["person_id"] == "synthetic-local-b"
    assert client.get("/api/v1/workouts/drafts/active", headers=headers).status_code == 404
    assert_no_health_in_application_state(app, harness)
    harness.assert_private_logs(caplog)
