import json

from fs import errors, open_fs, path

from app_distribution_server.build_info import BuildInfo, LegacyAppInfo, Platform
from app_distribution_server.config import STORAGE_URL
from app_distribution_server.errors import NotFoundError
from app_distribution_server.logger import logger

PLIST_FILE_NAME = "info.plist"
BUILD_INFO_JSON_FILE_NAME = "build_info.json"
LEGACY_BUILD_INFO_JSON_FILE_NAME = "app_info.json"
INDEXES_DIRECTORY = "_indexes"


filesystem = open_fs(STORAGE_URL, create=True)


def create_parent_directories(upload_id: str):
    filesystem.makedirs(upload_id, recreate=True)


def save_upload(build_info: BuildInfo, app_file_content: bytes):
    create_parent_directories(build_info.upload_id)
    save_build_info(build_info)
    save_app_file(build_info, app_file_content)
    set_latest_build(build_info)


def get_upload_platform(upload_id: str) -> Platform | None:
    for platform in Platform:
        if filesystem.exists(path.join(upload_id, platform.app_file_name)):
            return platform

    return None


def get_upload_asserted_platform(
    upload_id: str,
    expected_platform: Platform | None = None,
) -> Platform:
    upload_platform = get_upload_platform(upload_id)

    if upload_platform is None:
        raise NotFoundError()

    if expected_platform is None:
        return upload_platform

    if upload_platform == expected_platform:
        return upload_platform

    raise NotFoundError()


def save_build_info(build_info: BuildInfo):
    upload_id = build_info.upload_id
    filepath = f"{upload_id}/{BUILD_INFO_JSON_FILE_NAME}"

    with filesystem.open(filepath, "w") as app_info_file:
        app_info_file.write(
            build_info.model_dump_json(indent=2),
        )


def load_build_info(upload_id: str) -> BuildInfo:
    try:
        filepath = path.join(upload_id, BUILD_INFO_JSON_FILE_NAME)
        with filesystem.open(filepath, "r") as app_info_file:
            build_info_json = json.load(app_info_file)
            return BuildInfo.model_validate(build_info_json)

    except errors.ResourceNotFound:
        return migrate_legacy_app_info(upload_id)


def migrate_legacy_app_info(upload_id: str) -> BuildInfo:
    logger.info(f"Migrating legacy upload {upload_id!r} to v2")

    filepath = path.join(upload_id, LEGACY_BUILD_INFO_JSON_FILE_NAME)
    with filesystem.open(filepath, "r") as app_info_file:
        legacy_info_json = json.load(app_info_file)
        legacy_app_info = LegacyAppInfo.model_validate(legacy_info_json)

    file_size = filesystem.getsize(
        path.join(upload_id, Platform.ios.app_file_name),
    )

    build_info = BuildInfo(
        app_title=legacy_app_info.app_title,
        bundle_id=legacy_app_info.bundle_id,
        bundle_version=legacy_app_info.bundle_version,
        upload_id=upload_id,
        file_size=file_size,
        created_at=None,
        platform=Platform.ios,
    )

    save_build_info(build_info)
    logger.info(f"Successfully migrated legacy upload {upload_id!r} to v2")

    return build_info


def get_app_file_path(
    build_info: BuildInfo,
):
    return path.join(
        build_info.upload_id,
        build_info.platform.app_file_name,
    )


def save_app_file(
    build_info: BuildInfo,
    app_file: bytes,
):
    with filesystem.open(get_app_file_path(build_info), "wb+") as writable_app_file:
        writable_app_file.write(app_file)


def load_app_file(
    build_info: BuildInfo,
) -> bytes:
    with filesystem.open(get_app_file_path(build_info), "rb") as app_file:
        return app_file.read()


def delete_upload(upload_id: str):
    try:
        filesystem.removetree(upload_id)
        logger.info(f"Upload directory {upload_id!r} deleted successfully")
    except Exception as e:
        logger.error(f"Failed to delete upload directory {upload_id!r}: {e}")
        raise


def get_latest_upload_by_bundle_id_filepath(bundle_id):
    return path.join(INDEXES_DIRECTORY, "latest_upload_by_bundle_id", f"{bundle_id}.txt")


def set_latest_build(build_info: BuildInfo):
    filepath = get_latest_upload_by_bundle_id_filepath(build_info.bundle_id)
    filesystem.makedirs(path.dirname(filepath), recreate=True)

    with filesystem.open(filepath, "w") as file:
        file.write(build_info.upload_id)


def get_latest_upload_id_by_bundle_id(bundle_id: str) -> str | None:
    filepath = get_latest_upload_by_bundle_id_filepath(bundle_id)

    logger.info(f"Retrieving latest upload id from bundle {bundle_id!r} ({filepath!r})")

    if not filesystem.exists(filepath):
        return None

    with filesystem.open(filepath, "r") as file:
        return file.readline().strip()
