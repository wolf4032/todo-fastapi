from sqlalchemy.ext.asyncio import AsyncSession

from app.models.todo import Todo
from app.schemas.todo import TodoCreate


async def create(db: AsyncSession, todo_in: TodoCreate) -> Todo:
    todo = Todo(**todo_in.model_dump())
    db.add(todo)
    await db.commit()
    # commit 後の id / created_at などの DB 側で決まる値を todo オブジェクトへ反映する。
    await db.refresh(todo)
    return todo


async def get(db: AsyncSession, todo_id: int) -> Todo | None:
    # 「見つからない」は例外ではなく None で表現する。
    # HTTP 404 への変換はこの層の責務ではなく呼び出し元（エンドポイント）が担う。
    # → docs/notes/step-07-todo-schema-crud-api.md
    return await db.get(Todo, todo_id)
