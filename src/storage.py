import json
import os

from fs import open_fs

from src.apple_ipa import AppInfo

STORAGE_URL = os.getenv("STORAGE_URL", "osfs://./uploads")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
UPLOADS_SECRET_AUTH_TOKEN = os.getenv("UPLOADS_SECRET_AUTH_TOKEN", "password")
UPLOADS_DIRECTORY = os.getenv("UPLOADS_DIRECTORY", "./uploads")
UPLOADS_ROUTE_PATH = "uploads"
APP_TITLE = "Significa IOS app distribution"
PLIST_FILE_NAME = "info.plist"
APP_IPA_FILE_NAME = "app.ipa"
APP_INFO_JSON_FILE_NAME = "app_info.json"

filesystem = open_fs(STORAGE_URL)


def create_parent_directories(upload_id: str):
    filesystem.makedirs(upload_id, recreate=True)


def upload_exists(upload_id: str):
    return (
        filesystem.exists(f"{upload_id}/{APP_IPA_FILE_NAME}")
        and filesystem.exists(f"{upload_id}/{APP_INFO_JSON_FILE_NAME}")
    )


def save_plist_file(upload_id: str, content: str):
    filepath = f"{upload_id}/{PLIST_FILE_NAME}"

    with filesystem.open(filepath, "w") as plist_file:
        plist_file.write(content)


def save_app_info(upload_id: str, app_info: AppInfo):
    filepath = f"{upload_id}/{APP_INFO_JSON_FILE_NAME}"

    with filesystem.open(filepath, "w") as app_info_file:
        app_info_file.write(app_info.model_dump_json())


def load_app_info(upload_id: str) -> AppInfo:
    filepath = f"{upload_id}/{APP_INFO_JSON_FILE_NAME}"

    with filesystem.open(filepath, "r") as app_info_file:
        app_info_json = json.load(app_info_file)

    return AppInfo(**app_info_json)


def save_ipa_app_file(upload_id: str, ipa_file):
    ipa_app_file_path = f"{upload_id}/{APP_IPA_FILE_NAME}"

    with filesystem.open(ipa_app_file_path, "wb+") as writable_ipa_file:
        writable_ipa_file.write(ipa_file)


def load_ipa_app_file(upload_id: str) -> bytes:
    filepath = f"{upload_id}/{APP_IPA_FILE_NAME}"

    with filesystem.open(filepath, "rb") as ipa_file:
        return ipa_file.read()
