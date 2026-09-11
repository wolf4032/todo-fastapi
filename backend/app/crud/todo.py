from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.todo import Todo
from app.schemas.todo import TodoCreate, TodoUpdate


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


async def list_todos(
    db: AsyncSession,
    limit: int,
    offset: int,
    is_completed: bool | None,
) -> tuple[list[Todo], int]:
    # total は「絞り込み後の全件数」。ページネーションのUIが総ページ数を出すのに要る。
    stmt = select(Todo).order_by(Todo.id)
    count_stmt = select(func.count()).select_from(Todo)
    if is_completed is not None:
        stmt = stmt.where(Todo.is_completed == is_completed)
        count_stmt = count_stmt.where(Todo.is_completed == is_completed)

    total = await db.scalar(count_stmt)
    todos = await db.scalars(stmt.limit(limit).offset(offset))
    return list(todos), total or 0


async def update(db: AsyncSession, todo: Todo, todo_in: TodoUpdate) -> Todo:
    # exclude_unset=True で「リクエストに含まれていたキーだけ」を取り出す。
    # → docs/notes/step-08-todo-crud-remainder.md
    for field, value in todo_in.model_dump(exclude_unset=True).items():
        setattr(todo, field, value)
    await db.commit()
    await db.refresh(todo)
    return todo


async def delete(db: AsyncSession, todo: Todo) -> None:
    await db.delete(todo)
    await db.commit()
