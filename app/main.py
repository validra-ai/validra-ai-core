import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("validra")

from app.api.routes import cancel, generation, validation
from app.engine.executor import Executor
from app.plugins.fuzz.plugin import FuzzPlugin
from app.plugins.pen.plugin import PenTestPlugin
from app.plugins.registry import PluginRegistry
from app.plugins.security.plugin import SecurityPlugin
from app.providers.anthropic.provider import AnthropicProvider
from app.providers.ollama.provider import OllamaProvider
from app.providers.openai.provider import OpenAIProvider
from app.providers.registry import ProviderRegistry
from app.validator.llm_validator import LLMValidator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Plugins ──────────────────────────────────────────────────────────────
    plugin_registry = PluginRegistry()
    plugin_registry.register("FUZZ", FuzzPlugin())
    plugin_registry.register("AUTH", SecurityPlugin())
    plugin_registry.register("PEN", PenTestPlugin())
    app.state.plugin_registry = plugin_registry

    # ── Providers ────────────────────────────────────────────────────────────
    provider_registry = ProviderRegistry()
    provider_registry.register("ollama", OllamaProvider())
    provider_registry.register("openai", OpenAIProvider())
    provider_registry.register("anthropic", AnthropicProvider())
    app.state.provider_registry = provider_registry

    # ── Shared singletons ────────────────────────────────────────────────────
    app.state.executor = Executor()
    app.state.validator = LLMValidator()
    app.state.active_runs = {}

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Validra",
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
    app.include_router(generation.router)
    app.include_router(validation.router)
    app.include_router(cancel.router)

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title="Validra",
            swagger_favicon_url="/favicon.ico",
            swagger_ui_parameters={
                "defaultModelsExpandDepth": -1,
                "defaultModelExpandDepth": -1,
            },
        )

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return FileResponse(str(Path(__file__).parent / "static" / "favicon.ico"))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_req: Request, exc: Exception):
        logger.error("Unhandled exception:\n%s", traceback.format_exc())
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app


app = create_app()
