import io
import secrets
from datetime import datetime, timezone
from uuid import uuid4
from venv import logger

from fastapi import APIRouter, File, Header, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app_distribution_server.config import (
    APP_BASE_URL,
    APP_TITLE,
    LOGO_URL,
    UPLOAD_SECRET_AUTH_TOKEN,
)
from app_distribution_server.errors import (
    InvalidFileTypeError,
    NotFoundError,
    UnauthorizedError,
)
from app_distribution_server.model import (
    BuildInfo,
    Platform,
    extract_android_app_info,
    extract_ipa_info,
)
from app_distribution_server.qrcode import get_qr_code_svg
from app_distribution_server.storage import (
    build_exists,
    create_parent_directories,
    list_all_build_info,
    load_app_file,
    load_build_info,
    save_app_file,
    save_build_info,
)

router = APIRouter()

templates = Jinja2Templates(directory="templates")


def get_absolute_url(path: str) -> str:
    return f"{APP_BASE_URL}{path}"


def assert_build_exists(build_id: str):
    if not build_exists(build_id):
        raise NotFoundError()


@router.post(
    "/upload",
    responses={
        InvalidFileTypeError.STATUS_CODE: {
            "description": InvalidFileTypeError.ERROR_MESSAGE,
        },
        UnauthorizedError.STATUS_CODE: {
            "description": UnauthorizedError.ERROR_MESSAGE,
        },
    },
    tags=["Upload API"],
    summary="Upload an iOS/Android app Build",
)
async def upload_app(
    app_file: UploadFile = File(),
    x_auth_token: str = Header(),
) -> Response:
    if not secrets.compare_digest(x_auth_token, UPLOAD_SECRET_AUTH_TOKEN):
        raise UnauthorizedError()

    platform: Platform

    if app_file.filename is None:
        raise InvalidFileTypeError()

    if app_file.filename.endswith(".ipa"):
        platform = Platform.ios

    elif app_file.filename.endswith(".apk"):
        platform = Platform.android

    else:
        raise InvalidFileTypeError()

    build_id = f"{platform.value}-{uuid4()}"
    logger.debug(f"Starting upload {build_id!r}")

    app_file_content = app_file.file.read()

    if platform == Platform.ios:
        app_info = extract_ipa_info(io.BytesIO(app_file_content))
    else:
        app_info = extract_android_app_info(io.BytesIO(app_file_content))

    create_parent_directories(build_id)
    build_info = BuildInfo(
        build_id=build_id,
        created_at=datetime.now(timezone.utc),
        app_info=app_info,
    )
    save_build_info(build_info)
    save_app_file(build_id, app_file_content)

    logger.info(f"Upload {app_info.bundle_id!r} ({build_id!r}) complete")

    return Response(
        content=get_absolute_url(f"/get/{build_id}"),
        media_type="text/plain",
    )


@router.get(
    "/get/{id}",
    response_class=HTMLResponse,
    tags=["Static page handling"],
    summary="Render the HTML installation page for the specified item ID.",
)
async def get_item_installation_page(
    request: Request,
    id: str,
) -> HTMLResponse:
    assert_build_exists(id)

    is_ios = id.startswith("ios-")
    if is_ios:
        plist_url = get_absolute_url(f"/get/{id}/app.plist")
        install_url = f"itms-services://?action=download-manifest&url={plist_url}"
    else:
        install_url = get_absolute_url(f"/get/{id}/app.apk")

    build_info = load_build_info(id)
    app_info = build_info.app_info

    return templates.TemplateResponse(
        request=request,
        name="download-page.html",
        context={
            "page_title": f"{app_info.app_title} @{app_info.bundle_version} - {APP_TITLE}",
            "app_title": app_info.app_title,
            "created_at": build_info.created_at,
            "bundle_id": app_info.bundle_id,
            "bundle_version": app_info.bundle_version,
            "install_url": install_url,
            "qr_code_svg": get_qr_code_svg(install_url),
            "logo_url": LOGO_URL,
            "file_size": app_info.display_file_size,
            "platform": build_info.platform.display_name,
        },
    )


@router.get(
    "/get/{id}/app.plist",
    response_class=HTMLResponse,
    tags=["Static page handling"],
)
async def get_item_plist(
    request: Request,
    id: str,
) -> HTMLResponse:
    assert_build_exists(id)

    app_info = load_build_info(id).app_info

    return templates.TemplateResponse(
        request=request,
        name="plist.xml",
        context={
            "ipa_file_url": get_absolute_url(f"/get/{id}/app.ipa"),
            "app_title": app_info.app_title,
            "bundle_id": app_info.bundle_id,
            "bundle_version": app_info.bundle_version,
        },
    )


@router.get(
    "/get/{id}/app.{file_type}",
    response_class=HTMLResponse,
    tags=["Static page handling"],
)
async def get_app_file(
    id: str,
    file_type: str,
) -> Response:
    assert_build_exists(id)
    allowed_file_types = ["ipa", "apk"]
    if file_type not in allowed_file_types:
        raise InvalidFileTypeError()

    app_ipa_file_content = load_app_file(id)
    build_info = load_build_info(id)

    created_at = build_info.created_at.strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"{build_info.app_info.app_title} {build_info.app_info.bundle_version} {created_at}"

    return Response(
        content=app_ipa_file_content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={file_name}.{file_type}"},
    )


@router.get(
    "/{bundle_id}/latest",
    response_class=HTMLResponse,
    tags=["Static page handling"],
)
async def get_latest_installation_page(
    bundle_id: str,
    request: Request,
) -> HTMLResponse:
    build_id = await load_latest_build_id(bundle_id)
    return await get_item_installation_page(request, build_id)


async def load_latest_build_id(bundle_id: str) -> str:
    all_builds = list_all_build_info()
    all_builds = list(filter(lambda x: x.app_info.bundle_id == bundle_id, all_builds))
    all_builds.sort(key=lambda x: x.created_at)
    if not all_builds:
        raise NotFoundError()
    return all_builds[-1].build_id


@router.get(
    "/healthz",
    tags=["Healthz"],
)
async def healthz():
    return Response(
        content="OK",
        media_type="text/plain",
    )
