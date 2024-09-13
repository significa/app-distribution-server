from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app_distribution_server.build_info import (
    Platform,
)
from app_distribution_server.config import (
    APP_TITLE,
    LOGO_URL,
    get_absolute_url,
)
from app_distribution_server.errors import (
    UserError,
)
from app_distribution_server.qrcode import get_qr_code_svg
from app_distribution_server.storage import (
    get_upload_asserted_platform,
    load_build_info,
)

router = APIRouter(tags=["HTML page handling"])

templates = Jinja2Templates(directory="templates")


@router.get(
    "/get/{upload_id}",
    response_class=HTMLResponse,
    summary="Render the HTML installation page for the specified item ID",
)
async def render_get_item_installation_page(
    request: Request,
    upload_id: str,
) -> HTMLResponse:
    platform = get_upload_asserted_platform(upload_id)

    if platform == Platform.ios:
        plist_url = get_absolute_url(f"/get/{upload_id}/app.plist")
        install_url = f"itms-services://?action=download-manifest&url={plist_url}"
    else:
        install_url = get_absolute_url(f"/get/{upload_id}/app.apk")

    build_info = load_build_info(upload_id)

    return templates.TemplateResponse(
        request=request,
        name="download-page.jinja.html",
        context={
            "page_title": f"{build_info.app_title} @{build_info.bundle_version} - {APP_TITLE}",
            "build_info": build_info,
            "install_url": install_url,
            "qr_code_svg": get_qr_code_svg(install_url),
            "logo_url": LOGO_URL,
        },
    )


async def render_error_page(
    request: Request,
    user_error: UserError,
) -> Response:
    return templates.TemplateResponse(
        request=request,
        status_code=user_error.STATUS_CODE,
        name="error.jinja.html",
        context={
            "page_title": user_error.ERROR_MESSAGE,
            "error_message": f"{user_error.STATUS_CODE} - {user_error.ERROR_MESSAGE}",
        },
    )
