"""Setup-page rendering for authenticated but unmapped browser users."""

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from hwa.web.dependencies import WebIdentitySetupRequired

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


async def setup_required_exception_handler(
    request: Request,
    exc: Exception,
) -> HTMLResponse:
    """Render only the authenticated subject needed for administrator mapping."""

    if not isinstance(exc, WebIdentitySetupRequired):
        raise exc
    return templates.TemplateResponse(
        request=request,
        name="setup_required.html",
        context={"subject_id": exc.subject_id},
        status_code=403,
    )
