import os

from app_distribution_server.logger import logger

STORAGE_URL = os.getenv("STORAGE_URL", "osfs://./uploads")

UPLOAD_SECRET_AUTH_TOKEN = os.getenv("UPLOAD_SECRET_AUTH_TOKEN")

if not UPLOAD_SECRET_AUTH_TOKEN:
    UPLOAD_SECRET_AUTH_TOKEN = "secret"  # noqa: S105
    logger.warn(
        "SECURITY WARNING: Using default auth token!"
        " For security reasons override it with the 'UPLOAD_SECRET_AUTH_TOKEN' env var.",
    )


APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
APP_VERSION = os.getenv("APP_VERSION") or "0.0.1-development"
APP_TITLE = os.getenv("APP_TITLE") or "iOS/Android app distribution server"
LOGO_URL = os.getenv("LOGO_URL", "/static/logo.svg")
