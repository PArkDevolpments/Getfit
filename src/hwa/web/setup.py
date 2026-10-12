"""Setup-page rendering for authenticated but unmapped browser users."""

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from hwa.web.dependencies import WebIdentitySetupRequired
from hwa.web.urls import ingress_url

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals["ingress_url"] = ingress_url


async def setup_required_exception_handler(
    request: Request,
    exc: Exception,
) -> HTMLResponse:
    """Render mapping guidance without exposing the authenticated principal."""

    if not isinstance(exc, WebIdentitySetupRequired):
        raise exc
    return templates.TemplateResponse(
        request=request,
        name="setup_required.html",
        context={},
        status_code=403,
    )
