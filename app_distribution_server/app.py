from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app_distribution_server.config import (
    APP_TITLE,
    APP_VERSION,
)
from app_distribution_server.router import router

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    summary="Simple, self-hosted iOS/Android app distribution server.",
    description="[Source code, issues and documentation](https://github.com/significa/ios-ipa-app-distribution)",
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
