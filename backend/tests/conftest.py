import os

# app 配下を import するより前に、接続先DBをテスト専用の todo_test に上書きする。
# app.core.config.settings はモジュール import 時に一度だけ生成される（シングルトン）ため、
# 後段の import よりも前にこの行を置くことで、アプリ本体・alembic の両方が
# todo_test を向いた状態で動く。→ docs/notes/step-09-tests.md
os.environ["POSTGRES_DB"] = "todo_test"

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.main import app

# テスト専用のエンジン。pytest-asyncio はテストごとに新しいイベントループを作るため、
# 接続を保持するプールを持つと、前のループに紐づいた接続が次のテストで使い回されて壊れる。
# NullPool は接続を保持せず毎回開いて閉じるので、ループをまたいだ再利用が起きない。
# → docs/notes/step-09-tests.md
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)


def _create_test_database_if_missing() -> None:
    async def _create() -> None:
        # todo_test 自体にはまだ繋げないので、管理用DB（postgres）に接続して作成する。
        admin_url = (
            "postgresql+asyncpg://"
            f"{settings.postgres_user}:{settings.postgres_password}"
            f"@{settings.postgres_host}:{settings.postgres_port}/postgres"
        )
        # CREATE DATABASE はトランザクション内では実行できないため AUTOCOMMIT にする。
        admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": settings.postgres_db},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{settings.postgres_db}"'))
        await admin_engine.dispose()

    asyncio.run(_create())


def _upgrade_test_database() -> None:
    # alembic upgrade head を CLI ではなく Python から直接呼ぶ。
    # → docs/notes/step-09-tests.md
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    _create_test_database_if_missing()
    _upgrade_test_database()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    # 外側の接続でトランザクションを1つ張り、その上で AsyncSession を動かす。
    # join_transaction_mode="create_savepoint" により、テスト内・CRUD層での
    # db.commit() は SAVEPOINT の解放として扱われる。最後に外側を rollback すれば
    # commit 済みの変更も含めてまとめて消える。→ docs/notes/step-09-tests.md
    async with test_engine.connect() as connection:
        await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        await connection.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def _get_test_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    # get_db を差し替えて、エンドポイントにテスト用トランザクションのセッションを注入する。
    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
