import json

from fs import errors, open_fs, path

from app_distribution_server.config import STORAGE_URL
from app_distribution_server.mobile_builds import BuildInfo, LegacyAppInfo, Platform

PLIST_FILE_NAME = "info.plist"

IPA_FILE_NAME = "app.ipa"
APK_FILE_NAME = "app.apk"

BUILD_INFO_JSON_FILE_NAME = "build_info.json"
LEGACY_BUILD_INFO_JSON_FILE_NAME = "app_info.json"

filesystem = open_fs(STORAGE_URL, create=True)


def create_parent_directories(upload_id: str):
    filesystem.makedirs(upload_id, recreate=True)


def get_upload_platform(upload_id: str) -> Platform | None:
    if filesystem.exists(path.join(upload_id, IPA_FILE_NAME)):
        return Platform.ios

    if filesystem.exists(path.join(upload_id, APK_FILE_NAME)):
        return Platform.android

    return None


def save_build_info(build_info: BuildInfo):
    upload_id = build_info.upload_id
    filepath = f"{upload_id}/{BUILD_INFO_JSON_FILE_NAME}"

    with filesystem.open(filepath, "w") as app_info_file:
        app_info_file.write(build_info.model_dump_json())


def load_build_info(upload_id: str) -> BuildInfo:
    try:
        filepath = path.join(upload_id, BUILD_INFO_JSON_FILE_NAME)
        with filesystem.open(filepath, "r") as app_info_file:
            build_info_json = json.load(app_info_file)
            return BuildInfo.model_validate(build_info_json)

    except errors.ResourceNotFound:
        return migrate_legacy_app_info(upload_id)


def migrate_legacy_app_info(upload_id: str) -> BuildInfo:
    filepath = path.join(upload_id, LEGACY_BUILD_INFO_JSON_FILE_NAME)
    with filesystem.open(filepath, "r") as app_info_file:
        legacy_info_json = json.load(app_info_file)
        legacy_app_info = LegacyAppInfo.model_validate(legacy_info_json)

    build_info = BuildInfo(
        app_title=legacy_app_info.app_title,
        bundle_id=legacy_app_info.bundle_id,
        bundle_version=legacy_app_info.bundle_version,
        upload_id=upload_id,
        file_size=0,
        created_at=None,
        platform=Platform.ios,
    )

    save_build_info(build_info)

    return build_info


def get_file_path(
    build_info: BuildInfo,
):
    file_name = IPA_FILE_NAME if build_info.platform == Platform.ios else APK_FILE_NAME
    return path.join(build_info.upload_id, file_name)


def save_app_file(
    build_info: BuildInfo,
    app_file: bytes,
):
    with filesystem.open(get_file_path(build_info), "wb+") as writable_app_file:
        writable_app_file.write(app_file)


def load_app_file(
    build_info: BuildInfo,
) -> bytes:
    with filesystem.open(get_file_path(build_info), "rb") as app_file:
        return app_file.read()
