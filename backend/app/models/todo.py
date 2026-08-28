from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    # Mapped[str | None] のように Optional にすると nullable=True が自動で付く。
    # → docs/notes/topic-sqlalchemy-defaults.md
    description: Mapped[str | None] = mapped_column(Text)
    is_completed: Mapped[bool] = mapped_column(default=False, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # server_default=func.now() は DB 側（PostgreSQL の now()）で値を埋める指定。
    # Python 側の default= と違い、このテーブルに直接 INSERT する他の経路でも効く。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
