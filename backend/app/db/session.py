from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# エンジンはプロセス内で使い回すコネクションプールそのもの。
# ここではまだ実際には繋ぎに行かない（最初のクエリで遅延接続される）。
engine = create_async_engine(settings.database_url)

# expire_on_commit=False にしないと、commit 直後に属性へアクセスした時点で
# SQLAlchemy が値を再取得しようとして DB に問い合わせる。
# async セッションでは await できない場所でこれが起きて例外になるため、
# 非同期では実質必須の設定。→ docs/notes/step-05-app-foundation.md
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession]:
    # FastAPI の Depends から呼ばれる。リクエストごとに独立したセッションを払い出し、
    # 終わったら（例外時も）確実にクローズする。
    async with async_session_factory() as session:
        yield session
