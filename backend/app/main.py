from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import router as api_v1_router
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, request_id_middleware
from app.db.session import engine, get_db

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield
    # graceful shutdown: プロセスを止める前にコネクションプールを明示的に閉じる。
    # → docs/notes/step-05-app-foundation.md
    await engine.dispose()


app = FastAPI(lifespan=lifespan)
app.middleware("http")(request_id_middleware)
register_exception_handlers(app)
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    # プロセスが生きているかだけを見る。DB 等の依存先には触れない。
    return {"status": "ok"}


@app.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    # 依存先（DB）まで実際に疎通できるかを見る。
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
