from fastapi import FastAPI

from ipa_app_distribution_server.config import (
    APP_TITLE,
    APP_VERSION,
)
from ipa_app_distribution_server.router import router

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    summary="Simple, self-hosted IPA app distribution server.",
    description="[Source code, issues and documentation](https://github.com/significa/ios-ipa-app-distribution)",
)


app.include_router(router)
