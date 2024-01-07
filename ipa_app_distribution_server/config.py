import os

from ipa_app_distribution_server.logger import logger

STORAGE_URL = os.getenv("STORAGE_URL", "osfs://./uploads")

UPLOADS_SECRET_AUTH_TOKEN = os.getenv("UPLOADS_SECRET_AUTH_TOKEN")

if not UPLOADS_SECRET_AUTH_TOKEN:
    UPLOADS_SECRET_AUTH_TOKEN = "secret"
    logger.warn(
        "SECURITY WARNING: Using default auth token!"
        " For security reasons override it with the 'UPLOADS_SECRET_AUTH_TOKEN' env var.",
    )


APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")
APP_VERSION = os.getenv("APP_VERSION") or "0.0.1-development"
APP_TITLE = os.getenv("APP_TITLE") or "Significa IOS app distribution"
