import asyncio
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .api import router
from .persistence import database
from .service import MarketService, ServiceError

logger = logging.getLogger("salesbench.platform")


def create_app(*, database_url: str | None = None, admin_token: str | None = None, auto_run: bool = True,
               market_service: MarketService | None = None) -> FastAPI:
    engine = None
    if database_url and market_service is None:
        engine, sessions = database(database_url)
        market_service = MarketService(sessions)

    @asynccontextmanager
    async def lifespan(app):
        stop = asyncio.Event()

        async def worker():
            while not stop.is_set():
                try:
                    await asyncio.to_thread(market_service.work_pending)
                except (SQLAlchemyError, ServiceError) as error:
                    # Avoid SQL parameter/connection URL/credential logging.
                    logger.warning("Market worker retryable condition: %s", getattr(error, "code", type(error).__name__))
                try:
                    await asyncio.wait_for(stop.wait(), timeout=0.5)
                except TimeoutError:
                    pass

        task = asyncio.create_task(worker()) if market_service is not None and auto_run else None
        try:
            yield
        finally:
            stop.set()
            if task:
                await task
            if engine:
                engine.dispose()

    app = FastAPI(title="SalesBench persistent market service", version="0.2.0", lifespan=lifespan,
                  description="Local shared market application boundary. /health measures process responsiveness only.")
    app.state.market_service = market_service
    app.state.admin_token = admin_token
    app.include_router(router)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        return JSONResponse({"error": {"code": error.code, "retryable": error.status == 503}}, status_code=error.status)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError):
        return JSONResponse({"error": {"code": "DATABASE_UNAVAILABLE", "retryable": True}}, status_code=503)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "scope": "api_process"}

    return app


app = create_app(database_url=os.getenv("SALESBENCH_DATABASE_URL"), admin_token=os.getenv("SALESBENCH_ADMIN_TOKEN"),
                 auto_run=os.getenv("SALESBENCH_AUTO_RUN", "1") == "1")
