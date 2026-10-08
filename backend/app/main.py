import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_conf import setup_logging
from app.errors import BhashaLiveException, ErrorCode
from app.api import export, glossary, health, languages, metrics, sessions, translate, tts
from app.ws import handler as ws_handler

logger = logging.getLogger("bhashalive.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info(f"Starting BhashaLive Backend ({settings.app_env})")
    from app.db.repo import start_background_writer
    await start_background_writer()
    logger.info(
        f"Configured providers: Sarvam ASR={settings.is_sarvam_asr_configured}, "
        f"Sarvam Translate={settings.is_sarvam_translate_configured}, "
        f"Azure Speech={settings.is_azure_speech_configured}, "
        f"Azure Translator={settings.is_azure_translator_configured}"
    )
    yield
    # Shutdown
    logger.info("Shutting down BhashaLive Backend")


def create_app() -> FastAPI:
    app = FastAPI(
        title="BhashaLive Backend",
        description="Real-time speech translation backend for Indic languages",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(BhashaLiveException)
    async def bhashalive_exception_handler(request: Request, exc: BhashaLiveException):
        logger.warning(f"Handled application exception: {exc.code} - {exc.detail or exc.safe_message}")
        status_code = 400
        if exc.code == ErrorCode.RATE_LIMIT_EXCEEDED:
            status_code = 429
        elif exc.code in (ErrorCode.INVALID_SESSION, ErrorCode.SESSION_EXPIRED):
            status_code = 404
        elif exc.code == ErrorCode.UNAUTHORIZED_ORIGIN:
            status_code = 403
        elif exc.code == ErrorCode.PROVIDER_NOT_CONFIGURED:
            status_code = 503

        return JSONResponse(
            status_code=status_code,
            content={
                "code": exc.code.value,
                "safe_message": exc.safe_message,
                "retryable": exc.retryable,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": ErrorCode.INTERNAL_ERROR.value,
                "safe_message": "An unexpected server error occurred.",
                "retryable": False,
            },
        )

    # Include REST Routers
    app.include_router(health.router, prefix="/api")
    app.include_router(languages.router, prefix="/api")
    app.include_router(translate.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(export.router, prefix="/api")
    app.include_router(metrics.router, prefix="/api")
    app.include_router(glossary.router, prefix="/api")
    app.include_router(tts.router, prefix="/api")

    # Include WebSocket Router
    app.include_router(ws_handler.router)

    return app


app = create_app()
