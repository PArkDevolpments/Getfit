"""Production runtime wiring for the Home Assistant app."""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.orm import Session

from hwa.db.engine import create_engine
from hwa.domain.equipment import (
    EquipmentCapability,
    EquipmentKind,
    InstallationEquipmentProfile,
)
from hwa.domain.identity import PersonContext
from hwa.integrations.pep.ha_health_service import HaHealthServiceClient
from hwa.integrations.pep.health_reader import PepHealthContext, PepHealthReader
from hwa.integrations.pep.service_assertion import load_service_assertion_signer
from hwa.services.production_bootstrap import (
    ProductionBootstrapConfig,
    bootstrap_production,
)


class _UnavailablePepHealthReader(PepHealthReader):
    """An explicit activation/configuration state with no signing or transport."""

    configured = False

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def read(self, *, ha_user_id: str, person: PersonContext) -> PepHealthContext:
        return PepHealthContext(
            status="UNAVAILABLE", reason=self._reason, pep_person_id=person.pep_person_id,
        )


def build_pep_health_reader() -> PepHealthReader:
    """Load one signer and private HA client only for explicit Health activation."""

    try:
        enabled = _bool_env("HWA_PEP_HEALTH_ENABLED", False)
    except ValueError:
        os.environ.pop("SUPERVISOR_TOKEN", None)
        return _UnavailablePepHealthReader("PEP_HEALTH_CONFIGURATION_INVALID")
    if not enabled:
        return _UnavailablePepHealthReader("GETFIT_PEP_HEALTH_DISABLED")

    # Consume the credential even when another enabled configuration value is invalid.
    # Only the client's private field retains it after this construction returns.
    token = os.environ.pop("SUPERVISOR_TOKEN", "")
    try:
        signer = load_service_assertion_signer(
            os.getenv("HWA_PEP_HEALTH_SIGNING_KEY_FILE", ""),
            kid=os.getenv("HWA_PEP_HEALTH_SIGNING_KID", "").strip(),
        )
        client = HaHealthServiceClient(supervisor_token=token, timeout_seconds=5.0)
        return PepHealthReader(service_client=client, signer=signer)
    except Exception:
        # Never disclose exception text, secrets, paths or raw dependency state.
        return _UnavailablePepHealthReader("PEP_HEALTH_CONFIGURATION_INVALID")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _decimal_env(name: str, default: Decimal) -> Decimal:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal value") from exc
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def build_installation_equipment_profile() -> InstallationEquipmentProfile:
    """Build explicit installation capabilities from validated runtime configuration."""

    treadmill_max_incline = _decimal_env(
        "HWA_TREADMILL_MAX_INCLINE_PERCENT",
        Decimal("20"),
    )
    return InstallationEquipmentProfile(
        equipment=(
            EquipmentCapability(
                kind=EquipmentKind.TREADMILL,
                label="Treadmill",
                available=_bool_env("HWA_TREADMILL_AVAILABLE", True),
                supports_speed=True,
                supports_incline=True,
                max_incline_percent=treadmill_max_incline,
            ),
            EquipmentCapability(
                kind=EquipmentKind.SPIN_BIKE,
                label="Spin bike",
                available=_bool_env("HWA_SPIN_BIKE_AVAILABLE", True),
                supports_cadence=True,
                supports_resistance=True,
            ),
            EquipmentCapability(
                kind=EquipmentKind.ADJUSTABLE_DUMBBELLS,
                label="Adjustable dumbbells",
                available=_bool_env("HWA_ADJUSTABLE_DUMBBELLS_AVAILABLE", True),
            ),
        )
    )


def build_production_bootstrap_config() -> ProductionBootstrapConfig:
    """Read admin-owned Home Assistant identity mappings from runtime configuration."""

    return ProductionBootstrapConfig.from_raw(
        os.getenv("HWA_KRIS_HA_USER_ID"),
        os.getenv("HWA_KIRSTY_HA_USER_ID"),
    )


def build_pep_bridge_token() -> str | None:
    """Read the private Pep machine credential or leave the transport disabled."""

    raw = os.getenv("HWA_PEP_BRIDGE_TOKEN")
    if raw is None or not raw.strip():
        return None
    token = raw.strip()
    if len(token) < 24:
        raise ValueError("HWA_PEP_BRIDGE_TOKEN must be at least 24 characters")
    return token


def build_pep_bridge_allowed_person_ids() -> frozenset[str]:
    """Build the explicit service-level Pep person allow-list; default deny all."""

    allowed: set[str] = set()
    if _bool_env("HWA_PEP_BRIDGE_ALLOW_PERSON_A", False):
        allowed.add("person_a")
    if _bool_env("HWA_PEP_BRIDGE_ALLOW_PERSON_B", False):
        allowed.add("person_b")
    return frozenset(allowed)


def _programme_seed_root() -> Path:
    configured = os.getenv("HWA_PROGRAMME_SEED_ROOT")
    if configured is not None and configured.strip():
        return Path(configured.strip())

    container_root = Path("/app/programme_seed")
    if container_root.is_dir():
        return container_root

    return Path(__file__).resolve().parents[2] / "programme_seed"


def build_production_app() -> FastAPI:
    """Bootstrap the migrated production database, then construct the serving app."""

    from hwa.main import create_app

    engine = create_engine()
    seed_root = _programme_seed_root() / "home-workout-12m-v1"
    try:
        with Session(engine) as session:
            bootstrap_production(
                session,
                build_production_bootstrap_config(),
                seed_root / "programme.json",
                seed_root / "week-01.json",
            )
        return create_app(
            engine=engine,
            equipment_profile=build_installation_equipment_profile(),
            pep_bridge_token=build_pep_bridge_token(),
            pep_bridge_allowed_person_ids=build_pep_bridge_allowed_person_ids(),
        )
    except Exception:
        engine.dispose()
        raise
