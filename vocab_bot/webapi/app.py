from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vocab_bot.config import Settings
from vocab_bot.db import Database
from vocab_bot.repositories import CardRepository, UserRepository
from vocab_bot.services import ReviewService, UserService
from vocab_bot.webapi.deps import ApiError
from vocab_bot.webapi.routes import me_router, reviews_router


def create_app(settings: Settings, *, db: Database | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = db if db is not None else Database(settings.database_url)
        await database.init()
        app.state.db = database
        app.state.user_service = UserService(UserRepository(database))
        app.state.review_service = ReviewService(
            CardRepository(database),
            short_interval_minutes=settings.short_review_interval_minutes,
        )
        yield

    app = FastAPI(
        title="vocab_bot Mini App API",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.error, "message": exc.message})

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": "validation_error", "message": str(exc)})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": f"http_{exc.status_code}", "message": str(exc.detail)},
        )

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(me_router, prefix="/api")
    app.include_router(reviews_router, prefix="/api")
    return app
