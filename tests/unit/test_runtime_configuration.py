import shutil
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

import hwa.runtime as runtime
from hwa.domain.equipment import EquipmentKind
from hwa.domain.identity import PersonContext
from hwa.main import create_app

HEALTH_PERSON = PersonContext("hwa-kris", "person_a", "kris", "person_1", "male", "Kris")


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [None, "false"])
async def test_default_health_disabled_never_loads_key_or_constructs_client(
    monkeypatch, enabled,
) -> None:
    if enabled is None:
        monkeypatch.delenv("HWA_PEP_HEALTH_ENABLED", raising=False)
    else:
        monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", enabled)
    monkeypatch.setenv("HWA_PEP_HEALTH_SIGNING_KEY_FILE", "missing-sensitive-key")
    monkeypatch.setenv("HWA_PEP_HEALTH_SIGNING_KID", "")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "synthetic-supervisor-secret")

    def forbidden(*args, **kwargs):
        pytest.fail("disabled Health attempted secret loading or client construction")

    monkeypatch.setattr(runtime, "load_service_assertion_signer", forbidden, raising=False)
    monkeypatch.setattr(runtime, "HaHealthServiceClient", forbidden, raising=False)
    app = create_app()
    reader = app.state.pep_health_reader
    assert reader is not None, "default production construction must explicitly disable Health"
    context = await reader.read(ha_user_id="synthetic-ha", person=HEALTH_PERSON)
    assert context.status == "UNAVAILABLE"
    assert context.reason == "GETFIT_PEP_HEALTH_DISABLED"
    assert context.body == {}
    assert runtime.os.environ["SUPERVISOR_TOKEN"] == "synthetic-supervisor-secret"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled", "kid", "key", "token"),
    [
        ("true", "synthetic-kid", "missing", "synthetic-token"),
        ("true", "synthetic-kid", "malformed", "synthetic-token"),
        ("true", "", "valid", "synthetic-token"),
        ("true", "   ", "valid", "synthetic-token"),
        ("true", "synthetic-kid", "valid", None),
        ("true", "synthetic-kid", "valid", "   "),
        ("not-a-boolean", "synthetic-kid", "valid", "synthetic-token"),
    ],
)
async def test_invalid_health_configuration_fails_closed_without_exposing_secrets(
    monkeypatch, tmp_path, caplog, enabled, kid, key, token,
) -> None:
    path = tmp_path / "key"
    if key != "missing":
        path.write_text("AA" * 21 + "A" if key == "valid" else "private-invalid-sentinel")
        path.chmod(0o600)
    monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", enabled)
    monkeypatch.setenv("HWA_PEP_HEALTH_SIGNING_KID", kid)
    monkeypatch.setenv("HWA_PEP_HEALTH_SIGNING_KEY_FILE", str(path))
    if token is None:
        monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    else:
        monkeypatch.setenv("SUPERVISOR_TOKEN", token)
    app = create_app()
    assert app.state.pep_health_reader is not None
    context = await app.state.pep_health_reader.read(
        ha_user_id="synthetic-ha", person=HEALTH_PERSON,
    )
    assert context.status == "UNAVAILABLE"
    assert context.reason == "PEP_HEALTH_CONFIGURATION_INVALID"
    assert context.body == {}
    assert "SUPERVISOR_TOKEN" not in runtime.os.environ
    public = repr(app.state._state) + repr(context) + caplog.text
    assert "private-invalid-sentinel" not in public
    assert "synthetic-token" not in public


def test_explicit_health_reader_injection_is_authoritative(monkeypatch) -> None:
    monkeypatch.setenv("HWA_PEP_HEALTH_ENABLED", "true")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "injected-reader-token")
    injected = object()
    app = create_app(pep_health_reader=injected)
    assert app.state.pep_health_reader is injected
    assert runtime.os.environ["SUPERVISOR_TOKEN"] == "injected-reader-token"


@pytest.mark.parametrize("valid_key", [False, True])
def test_importing_application_factory_does_not_consume_supervisor_token(
    tmp_path, valid_key,
) -> None:
    key_file = tmp_path / "synthetic-import.key"
    key_file.write_text("A" * 43 if valid_key else "invalid-synthetic-key")
    key_file.chmod(0o600)
    completed = subprocess.run(
        [sys.executable, "-c", (
            "import os, sys; os.environ['HWA_PEP_HEALTH_ENABLED']='true'; "
            "os.environ['SUPERVISOR_TOKEN']='synthetic-import-token'; "
            "os.environ['HWA_PEP_HEALTH_SIGNING_KEY_FILE']=sys.argv[1]; "
            "os.environ['HWA_PEP_HEALTH_SIGNING_KID']='synthetic-import-kid'; "
            "import hwa.main as main; "
            "assert os.environ['SUPERVISOR_TOKEN']=='synthetic-import-token'; "
            "assert main.app.title=='Home Workout Assistant'; "
            "assert main.app.state.pep_health_configured == (sys.argv[2]=='True'); "
            "assert 'SUPERVISOR_TOKEN' not in os.environ; "
            "assert main.app is main.app"
        ), str(key_file), str(valid_key)], capture_output=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_addon_health_defaults_mask_key_and_grant_only_core_api() -> None:
    root = Path(__file__).resolve().parents[2]
    config = yaml.safe_load((root / "getfit/config.yaml").read_text(encoding="utf-8"))
    assert config["options"].get("pep_health_enabled") is False
    assert config["options"].get("pep_health_signing_kid") == ""
    assert config["options"].get("pep_health_signing_private_key") == ""
    assert config["schema"].get("pep_health_enabled") == "bool"
    assert config["schema"].get("pep_health_signing_kid") == "str"
    assert config["schema"].get("pep_health_signing_private_key") == "password"
    assert config.get("homeassistant_api") is True
    for privilege in ("hassio_api", "hassio_role", "host_network", "full_access", "privileged"):
        assert privilege not in config
    for asset in (root / "src/hwa/web/static").rglob("*"):
        if asset.is_file():
            contents = asset.read_bytes()
            assert b"SUPERVISOR_TOKEN" not in contents
            assert b"HWA_PEP_HEALTH_SIGNING_KEY_FILE" not in contents
            assert b"pep_health_signing_private_key" not in contents


@pytest.mark.parametrize("state", ["disabled", "enabled", "write-failed", "existing-symlink"])
def test_launch_script_materializes_private_key_only_when_enabled(state) -> None:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash unavailable for launch-script execution")
    script = (Path(__file__).resolve().parents[2] / "run.sh").read_text(encoding="utf-8")
    # Remap only the container's /data boundary into isolated POSIX scratch space.
    script = script.replace("/data", "${task_data}")
    enabled = "false" if state == "disabled" else "true"
    wrapper = r'''
task_data=$(mktemp -d)
trap 'rm -rf -- "$task_data"' EXIT
mkdir "$task_data/bin"
export PATH="$task_data/bin:/usr/bin:/bin"
printf '%s\n' '#!/bin/bash' 'exit 0' > "$task_data/bin/alembic"
printf '%s\n' '#!/bin/bash' \
  'set -eu' \
  'test "${HWA_PEP_HEALTH_ENABLED-}" = "EXPECTED_ENABLED"' \
  'test -z "${HWA_PEP_HEALTH_SIGNING_PRIVATE_KEY-}"' \
  'if test "$HWA_PEP_HEALTH_ENABLED" = true; then' \
  '  test "$HWA_PEP_HEALTH_SIGNING_KID" = synthetic-kid' \
  '  if test "EXPECTED_STATE" = write-failed; then' \
  '    test -z "${HWA_PEP_HEALTH_SIGNING_KEY_FILE-}"' \
  '  else' \
  '    test -f "$HWA_PEP_HEALTH_SIGNING_KEY_FILE"' \
  '    test ! -L "$HWA_PEP_HEALTH_SIGNING_KEY_FILE"' \
  '    test "$(stat -c %a "$HWA_PEP_HEALTH_SIGNING_KEY_FILE")" = 600' \
  '    test "$(< "$HWA_PEP_HEALTH_SIGNING_KEY_FILE")" = synthetic-private-key-sentinel' \
  '    test ! -e "$(dirname "$HWA_PEP_HEALTH_SIGNING_KEY_FILE")/victim"' \
  '  fi' \
  'else' \
  '  test -z "${HWA_PEP_HEALTH_SIGNING_KEY_FILE-}"' \
  '  test ! -e pep-health-signing.key' \
  'fi' \
  'printf "launch-ok\n"' > "$task_data/bin/uvicorn"
chmod 700 "$task_data/bin/"*
alembic() { return 0; }
bashio::config() {
  case "$1" in
    pep_health_enabled) printf '%s' 'EXPECTED_ENABLED' ;;
    pep_health_signing_kid) printf '%s' synthetic-kid ;;
    pep_health_signing_private_key)
      test 'EXPECTED_STATE' != disabled || exit 97
      printf '%s' synthetic-private-key-sentinel ;;
    *) printf '%s' false ;;
  esac
}
export HWA_PEP_HEALTH_SIGNING_KEY_FILE=stale-private-key-path
if test 'EXPECTED_STATE' = write-failed; then
  mktemp() { return 1; }
elif test 'EXPECTED_STATE' = existing-symlink; then
  ln -s "$task_data/victim" "$task_data/pep-health-signing.key"
fi
'''.replace("EXPECTED_ENABLED", enabled).replace("EXPECTED_STATE", state)
    completed = subprocess.run(
        [bash, "-s"], input=(wrapper + "\n(\n" + script + "\n)\n").encode(),
        capture_output=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == b"launch-ok\n"
    assert b"synthetic-private-key-sentinel" not in completed.stderr
    assert b"synthetic-supervisor-secret" not in completed.stderr


def test_runtime_equipment_profile_uses_explicit_installation_configuration(monkeypatch) -> None:
    monkeypatch.setenv("HWA_TREADMILL_AVAILABLE", "true")
    monkeypatch.setenv("HWA_TREADMILL_MAX_INCLINE_PERCENT", "20")
    monkeypatch.setenv("HWA_SPIN_BIKE_AVAILABLE", "true")
    monkeypatch.setenv("HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE", "true")

    profile = runtime.build_installation_equipment_profile()
    by_kind = {item.kind: item for item in profile.equipment}

    treadmill = by_kind[EquipmentKind.TREADMILL]
    assert treadmill.available is True
    assert treadmill.supports_speed is True
    assert treadmill.supports_incline is True
    assert treadmill.max_incline_percent == Decimal("20")

    bike = by_kind[EquipmentKind.SPIN_BIKE]
    assert bike.available is True
    assert bike.supports_incline is False
    assert bike.max_incline_percent is None
    assert bike.supports_cadence is True
    assert bike.supports_resistance is True

    dumbbells = by_kind[EquipmentKind.ADJUSTABLE_DUMBBELLS]
    assert dumbbells.available is True


def test_runtime_rejects_invalid_boolean_configuration(monkeypatch) -> None:
    monkeypatch.setenv("HWA_TREADMILL_AVAILABLE", "maybe")

    try:
        runtime.build_installation_equipment_profile()
    except ValueError as exc:
        assert "HWA_TREADMILL_AVAILABLE" in str(exc)
    else:
        raise AssertionError("invalid boolean configuration must fail closed")


def test_runtime_bootstrap_config_normalizes_optional_home_assistant_ids(monkeypatch) -> None:
    monkeypatch.setenv("HWA_KRIS_HA_USER_ID", "  ha-user-kris  ")
    monkeypatch.setenv("HWA_KIRSTY_HA_USER_ID", "   ")

    config = runtime.build_production_bootstrap_config()

    assert config.kris_ha_user_id == "ha-user-kris"
    assert config.kirsty_ha_user_id is None


def test_runtime_bootstrap_config_allows_both_home_assistant_ids_to_be_unconfigured(
    monkeypatch,
) -> None:
    monkeypatch.delenv("HWA_KRIS_HA_USER_ID", raising=False)
    monkeypatch.delenv("HWA_KIRSTY_HA_USER_ID", raising=False)

    config = runtime.build_production_bootstrap_config()

    assert config.kris_ha_user_id is None
    assert config.kirsty_ha_user_id is None


def test_runtime_pep_bridge_token_is_optional_and_validated(monkeypatch) -> None:
    monkeypatch.delenv("HWA_PEP_BRIDGE_TOKEN", raising=False)
    assert runtime.build_pep_bridge_token() is None

    monkeypatch.setenv("HWA_PEP_BRIDGE_TOKEN", "   ")
    assert runtime.build_pep_bridge_token() is None

    monkeypatch.setenv("HWA_PEP_BRIDGE_TOKEN", "  qa-only-machine-credential  ")
    assert runtime.build_pep_bridge_token() == "qa-only-machine-credential"

    monkeypatch.setenv("HWA_PEP_BRIDGE_TOKEN", "too-short")
    try:
        runtime.build_pep_bridge_token()
    except ValueError as exc:
        assert "HWA_PEP_BRIDGE_TOKEN" in str(exc)
    else:
        raise AssertionError("weak Pep bridge credential must fail closed")


def test_addon_masks_pep_bridge_token() -> None:
    config = (Path(__file__).resolve().parents[2] / "getfit" / "config.yaml").read_text(
        encoding="utf-8"
    )
    assert "  pep_bridge_token: password" in config


def test_pep_bridge_person_scope_defaults_to_deny_all(monkeypatch) -> None:
    monkeypatch.delenv("HWA_PEP_BRIDGE_ALLOW_PERSON_A", raising=False)
    monkeypatch.delenv("HWA_PEP_BRIDGE_ALLOW_PERSON_B", raising=False)

    assert runtime.build_pep_bridge_allowed_person_ids() == frozenset()


def test_pep_bridge_person_scope_is_explicit_per_person(monkeypatch) -> None:
    monkeypatch.setenv("HWA_PEP_BRIDGE_ALLOW_PERSON_A", "true")
    monkeypatch.setenv("HWA_PEP_BRIDGE_ALLOW_PERSON_B", "false")

    assert runtime.build_pep_bridge_allowed_person_ids() == frozenset({"person_a"})

    monkeypatch.setenv("HWA_PEP_BRIDGE_ALLOW_PERSON_B", "true")
    assert runtime.build_pep_bridge_allowed_person_ids() == frozenset(
        {"person_a", "person_b"}
    )
