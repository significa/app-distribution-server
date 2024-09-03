import plistlib
import zipfile
from datetime import datetime
from typing import IO

from pydantic import BaseModel

from ipa_app_distribution_server.errors import InvalidFileTypeError
from ipa_app_distribution_server.logger import logger


class AppInfo(BaseModel):
    app_title: str
    bundle_id: str
    bundle_version: str
    created_at: datetime = datetime.now()


def extract_app_info_from_plist_content(plist_file_content):
    info = plistlib.loads(plist_file_content)
    bundle_id = info.get("CFBundleIdentifier")
    app_title = info.get("CFBundleName")
    bundle_version = info.get("CFBundleShortVersionString")

    if bundle_id is None or app_title is None or bundle_version is None:
        logger.error("Failed to extract plist file information")
        raise InvalidFileTypeError()

    return AppInfo(
        app_title=app_title,
        bundle_id=bundle_id,
        bundle_version=bundle_version,
    )


def extract_app_info(ipa_file: IO[bytes]) -> AppInfo:
    with zipfile.ZipFile(ipa_file, "r") as ipa:
        for file in ipa.namelist():
            if file.endswith(".app/Info.plist"):
                data = ipa.read(file)
                return extract_app_info_from_plist_content(data)

    logger.error("Could not find plist file in bundle")
    raise InvalidFileTypeError()
