from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import generation, validation
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

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Validra",
        swagger_ui_parameters={"defaultModelsExpandDepth": -1},
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(generation.router)
    app.include_router(validation.router)

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
        return FileResponse("app/static/favicon.ico")

    return app


app = create_app()
