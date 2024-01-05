import json
import os
import secrets
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Header, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.apple_ipa import get_app_info
from src.errors import InvalidFileTypeError, NotFoundError, UnauthorizedError
from src.qrcode import get_qr_code_svg

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
UPLOADS_SECRET_AUTH_TOKEN = os.getenv("UPLOADS_SECRET_AUTH_TOKEN", "password")
UPLOADS_DIRECTORY = os.getenv("UPLOADS_DIRECTORY", "./uploads")
UPLOADS_ROUTE_PATH = "uploads"
APP_TITLE = "Significa IOS app distribution"
PLIST_FILE_NAME = "info.plist"
APP_IPA_FILE_NAME = "app.ipa"
APP_INFO_JSON_FILE_NAME = "app_info.json"

app = FastAPI(title=APP_TITLE)

app.mount(
    f"/{UPLOADS_ROUTE_PATH}",
    StaticFiles(directory=UPLOADS_DIRECTORY),
    name="uploads",
)

templates = Jinja2Templates(directory="templates")


def get_absolute_url(path: str) -> str:
    return f"{APP_BASE_URL}{path}"


@app.get("/healthz")
async def healthz() -> Literal["OK"]:
    return Response(content="OK", media_type="text/plain")


@app.get("/get/{id}", response_class=HTMLResponse)
async def installation_page(
    request: Request,
    id: str,
) -> HTMLResponse:
    item_directory_path = f"{UPLOADS_DIRECTORY}/{id}"
    plist_file_path = f"{item_directory_path}/{PLIST_FILE_NAME}"
    plist_url = get_absolute_url(f"/{UPLOADS_ROUTE_PATH}/{id}/{PLIST_FILE_NAME}")

    if not os.path.exists(plist_file_path):
        raise NotFoundError()

    install_url = f"itms-services://?action=download-manifest&url={plist_url}"

    with open(f"{item_directory_path}/{APP_INFO_JSON_FILE_NAME}", "r") as json_file:
        app_info = json.load(json_file)

    app_title = app_info["app_title"]
    bundle_id = app_info["bundle_id"]
    bundle_version = app_info["bundle_version"]

    return templates.TemplateResponse(
        request=request,
        name="download-page.html",
        context={
            "page_title": f"{app_title}: {app_title} @{bundle_version}",
            "app_title": app_title,
            "bundle_id": bundle_id,
            "bundle_version": bundle_version,
            "install_url": install_url,
            "qr_code_svg": get_qr_code_svg(install_url),
        },
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
    x_auth_token: str = Header()
) -> str:
    if not secrets.compare_digest(x_auth_token, UPLOADS_SECRET_AUTH_TOKEN):
        raise UnauthorizedError()

    if not ipa_file.filename.endswith(".ipa"):
        raise InvalidFileTypeError()

    # TODO: add a timestamp/date prefix to the id
    # later would be nice if we could delete old entries
    upload_id = uuid4()
    item_directory_path = f"{UPLOADS_DIRECTORY}/{upload_id}"
    ipa_app_file_path = f"{item_directory_path}/{APP_IPA_FILE_NAME}"

    os.makedirs(item_directory_path, exist_ok=True)

    with open(ipa_app_file_path, "wb+") as writable_ipa_file:
        writable_ipa_file.write(
            ipa_file.file.read()
        )

    app_title, bundle_id, bundle_version = get_app_info(ipa_app_file_path)

    with open(f"{item_directory_path}/{APP_INFO_JSON_FILE_NAME}", "w") as json_file:
        json.dump(
            {
                "app_title": app_title,
                "bundle_id": bundle_id,
                "bundle_version": bundle_version,
            },
            json_file
        )

    ipa_file_url = get_absolute_url(f"/{UPLOADS_ROUTE_PATH}/{upload_id}/{APP_IPA_FILE_NAME}")

    plist_content = templates.get_template("plist.xml").render(
        ipa_file_url=ipa_file_url,
        app_title=app_title,
        bundle_id=bundle_id,
        bundle_version=bundle_version,
    )

    with open(f"{item_directory_path}/{PLIST_FILE_NAME}", "w") as plist_file:
        plist_file.write(plist_content)

    return Response(
        content=get_absolute_url(f"/get/{upload_id}"),
        media_type="text/plain"
    )
