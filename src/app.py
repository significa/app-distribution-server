import io
import os
import secrets
from uuid import uuid4

from fastapi import FastAPI, File, Header, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.apple_ipa import extract_app_info
from src.errors import InvalidFileTypeError, NotFoundError, UnauthorizedError
from src.qrcode import get_qr_code_svg
from src.storage import (
    create_parent_directories, load_app_info, load_ipa_app_file, save_app_info, save_ipa_app_file,
    upload_exists,
)

UPLOADS_SECRET_AUTH_TOKEN = os.getenv("UPLOADS_SECRET_AUTH_TOKEN", "secret")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
APP_VERSION = os.getenv("APP_VERSION") or "0.0.1-development"
APP_TITLE = os.getenv("APP_TITLE") or "Significa IOS app distribution"

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
)

templates = Jinja2Templates(directory="templates")


def get_absolute_url(path: str) -> str:
    return f"{APP_BASE_URL}{path}"


def assert_upload_exists(upload_id: str):
    if not upload_exists(upload_id):
        raise NotFoundError()


@app.get("/healthz")
async def healthz():
    return Response(content="OK", media_type="text/plain")


@app.get("/get/{id}", response_class=HTMLResponse)
async def get_item_installation_page(
    request: Request,
    id: str,
) -> HTMLResponse:
    assert_upload_exists(id)

    plist_url = get_absolute_url(f"/get/{id}/app.plist")
    install_url = f"itms-services://?action=download-manifest&url={plist_url}"

    app_info = load_app_info(id)

    return templates.TemplateResponse(
        request=request,
        name="download-page.html",
        context={
            "page_title": f"{app_info.app_title} @{app_info.bundle_version} - {APP_TITLE}",
            "app_title": app_info.app_title,
            "bundle_id": app_info.bundle_id,
            "bundle_version": app_info.bundle_version,
            "install_url": install_url,
            "qr_code_svg": get_qr_code_svg(install_url),
        },
    )


@app.get("/get/{id}/app.plist", response_class=HTMLResponse)
async def get_item_plist(
    request: Request,
    id: str,
) -> HTMLResponse:
    print(id)
    assert_upload_exists(id)

    app_info = load_app_info(id)

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


@app.get("/get/{id}/app.ipa", response_class=HTMLResponse)
async def get_app_ipa(
    id: str,
) -> Response:
    assert_upload_exists(id)

    app_ipa_file_content = load_ipa_app_file(id)

    return Response(
        content=app_ipa_file_content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=app.ipa"},
    )


@app.post(
    "/upload",
    responses={
        InvalidFileTypeError.STATUS_CODE: {
            "description": InvalidFileTypeError.ERROR_MESSAGE
        },
        UnauthorizedError.STATUS_CODE: {
            "description": UnauthorizedError.ERROR_MESSAGE
        }
    }
)
async def upload_ipa(
    ipa_file: UploadFile = File(),
    x_auth_token: str = Header(),
) -> Response:
    if not secrets.compare_digest(x_auth_token, UPLOADS_SECRET_AUTH_TOKEN):
        raise UnauthorizedError()

    if ipa_file.filename is None or not ipa_file.filename.endswith(".ipa"):
        raise InvalidFileTypeError()

    upload_id = str(uuid4())

    ipa_file_content = ipa_file.file.read()
    app_info = extract_app_info(io.BytesIO(ipa_file_content))

    create_parent_directories(upload_id)

    save_app_info(upload_id, app_info)
    save_ipa_app_file(upload_id, ipa_file_content)

    return Response(
        content=get_absolute_url(f"/get/{upload_id}"),
        media_type="text/plain"
    )
