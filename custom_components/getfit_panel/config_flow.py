"""Config flow for the Getfit full-canvas panel companion."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN


class GetfitPanelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Install the local Getfit panel companion."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Create the single local panel entry."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Getfit Full-Canvas Panel", data={})

        return self.async_show_form(step_id="user")
