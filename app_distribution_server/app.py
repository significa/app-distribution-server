from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app_distribution_server.config import (
    APP_TITLE,
    APP_VERSION,
)
from app_distribution_server.errors import NotFoundError
from app_distribution_server.router import render_404_page, router

app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    summary="Simple, self-hosted iOS/Android app distribution server.",
    description="[Source code, issues and documentation](https://github.com/significa/app-distribution)",
    exception_handlers={
        NotFoundError: render_404_page,
        StarletteHTTPException: render_404_page,
    },
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
