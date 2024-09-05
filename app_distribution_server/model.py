import plistlib
import zipfile
from datetime import datetime
from enum import Enum
from io import BytesIO

from pydantic import BaseModel

from app_distribution_server.errors import InvalidFileTypeError
from app_distribution_server.logger import logger


class AppInfo(BaseModel):
    app_title: str
    bundle_id: str
    bundle_version: str
    file_size: int

    @property
    def display_file_size(self) -> str | None:
        one_kb = 1024
        if self.file_size is None:
            return None

        size = None
        if self.file_size < one_kb:
            size = f"{self.file_size}B"
        elif self.file_size < one_kb * one_kb:
            size = f"{self.file_size / one_kb:.2f}KB"
        elif self.file_size < one_kb * one_kb * one_kb:
            size = f"{self.file_size / one_kb / one_kb:.2f}MB"
        else:
            size = f"{self.file_size / one_kb / one_kb / one_kb:.2f}GB"
        return size


class BuildInfo(BaseModel):
    class Platform(str, Enum):
        ios = "ios"
        android = "android"

        @property
        def display_name(self):
            match = {
                self.ios: "iOS",
                self.android: "Android",
            }
            return match.get(self)

    build_id: str
    created_at: datetime
    app_info: AppInfo

    @property
    def platform(self) -> Platform:
        if self.build_id.startswith("ios"):
            return BuildInfo.Platform.ios
        if self.build_id.startswith("android"):
            return BuildInfo.Platform.android
        raise ValueError("Unknown platform")


def extract_app_info_from_plist_content(plist_file_content):
    info = plistlib.loads(plist_file_content)
    bundle_id = info.get("CFBundleIdentifier")
    app_title = info.get("CFBundleName")
    bundle_version = info.get("CFBundleShortVersionString")

    if bundle_id is None or app_title is None or bundle_version is None:
        logger.error("Failed to extract plist file information")
        raise InvalidFileTypeError()

    return {
        "app_title": app_title,
        "bundle_id": bundle_id,
        "bundle_version": bundle_version,
    }


def extract_ipa_info(ipa_file: BytesIO) -> AppInfo:
    with zipfile.ZipFile(ipa_file, "r") as ipa:
        for file in ipa.namelist():
            if file.endswith(".app/Info.plist"):
                data = ipa.read(file)
                plist_info = extract_app_info_from_plist_content(data)
                return AppInfo(
                    app_title=plist_info["app_title"],
                    bundle_id=plist_info["bundle_id"],
                    bundle_version=plist_info["bundle_version"],
                    file_size=ipa_file.getbuffer().nbytes,
                )

    logger.error("Could not find plist file in bundle")
    raise InvalidFileTypeError()


def extract_android_app_info(apk_file: BytesIO) -> AppInfo:
    # use aapt2 dump badging to get app info
    import os
    import shutil
    import tempfile

    from aapt2 import aapt

    tempdir = tempfile.mkdtemp()
    try:
        with open(os.path.join(tempdir, "app.apk"), "wb") as f:
            f.write(apk_file.read())
        apk_info = aapt.get_apk_info(os.path.join(tempdir, "app.apk"))
        return AppInfo(
            app_title=apk_info["app_name"],
            bundle_id=apk_info["package_name"],
            bundle_version=apk_info["version_name"],
            file_size=apk_file.getbuffer().nbytes,
        )
    finally:
        shutil.rmtree(tempdir)
