"""Home Assistant Supervisor Ingress authentication boundary."""

from collections.abc import Collection

from starlette.requests import Request

from hwa.auth.models import AuthenticatedPrincipal
from hwa.auth.principal import AuthenticationError

SUPERVISOR_INGRESS_SOURCE = "172.30.32.2"


class HomeAssistantIngressPrincipalProvider:
    """Trust Home Assistant identity headers only from Supervisor Ingress."""

    def __init__(self, trusted_hosts: Collection[str] | None = None) -> None:
        self._trusted_hosts = frozenset(
            trusted_hosts or {SUPERVISOR_INGRESS_SOURCE}
        )

    def resolve(self, request: Request) -> AuthenticatedPrincipal:
        client_host = request.client.host if request.client is not None else None
        if client_host not in self._trusted_hosts:
            raise AuthenticationError("UNAUTHENTICATED_INGRESS")

        subject_id = request.headers.get("X-Remote-User-Id", "").strip()
        if not subject_id:
            raise AuthenticationError("UNAUTHENTICATED_INGRESS")

        display_name = request.headers.get("X-Remote-User-Display-Name")
        return AuthenticatedPrincipal(
            subject_id=subject_id,
            display_name=display_name.strip() if display_name else None,
        )
