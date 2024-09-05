import json

from fs import open_fs

from app_distribution_server.config import STORAGE_URL
from app_distribution_server.model import BuildInfo

PLIST_FILE_NAME = "info.plist"
IPA_FILE_NAME = "app.ipa"
APK_FILE_NAME = "app.apk"
BUILD_INFO_JSON_FILE_NAME = "build_info.json"

filesystem = open_fs(STORAGE_URL, create=True)


def create_parent_directories(build_id: str):
    filesystem.makedirs(build_id, recreate=True)


def build_exists(build_id: str) -> bool:
    is_ios = build_id.startswith("ios-")
    file_name = IPA_FILE_NAME if is_ios else APK_FILE_NAME
    return (
        filesystem.exists(f"{build_id}/{file_name}")  # fmt: skip
        and filesystem.exists(f"{build_id}/{BUILD_INFO_JSON_FILE_NAME}")
    )


def save_build_info(build_info: BuildInfo):
    build_id = build_info.build_id
    filepath = f"{build_id}/{BUILD_INFO_JSON_FILE_NAME}"

    with filesystem.open(filepath, "w") as app_info_file:
        app_info_file.write(build_info.model_dump_json())


def list_all_build_info() -> list[BuildInfo]:
    app_info_list = []
    for build_id in filesystem.listdir(""):
        app_info_list.append(load_build_info(build_id))
    return app_info_list


def load_build_info(build_id: str) -> BuildInfo:
    filepath = f"{build_id}/{BUILD_INFO_JSON_FILE_NAME}"

    with filesystem.open(filepath, "r") as app_info_file:
        app_info_json = json.load(app_info_file)

    return BuildInfo(**app_info_json)


def save_app_file(build_id: str, app_file):
    is_ios = build_id.startswith("ios-")
    file_name = IPA_FILE_NAME if is_ios else APK_FILE_NAME
    app_file_path = f"{build_id}/{file_name}"

    with filesystem.open(app_file_path, "wb+") as writable_app_file:
        writable_app_file.write(app_file)


def load_app_file(build_id: str) -> bytes:
    is_ios = build_id.startswith("ios-")
    file_name = IPA_FILE_NAME if is_ios else APK_FILE_NAME
    filepath = f"{build_id}/{file_name}"

    with filesystem.open(filepath, "rb") as app_file:
        return app_file.read()
