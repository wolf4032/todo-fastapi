from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.crud import todo as todo_crud
from app.models.todo import Todo
from app.schemas.todo import TodoCreate, TodoListResponse, TodoRead, TodoUpdate

router = APIRouter(prefix="/todos", tags=["todos"])


async def _get_todo_or_404(db: AsyncSession, todo_id: int) -> Todo:
    # 3つのエンドポイント（取得・更新・削除）で共通する
    # 「None → HTTP 404」変換をここに集約する。
    # → docs/notes/step-07-todo-schema-crud-api.md
    todo = await todo_crud.get(db, todo_id)
    if todo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "todo not found")
    return todo


@router.post("", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
async def create_todo(todo_in: TodoCreate, db: AsyncSession = Depends(get_db)) -> Todo:
    return await todo_crud.create(db, todo_in)


@router.get("", response_model=TodoListResponse)
async def list_todos(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_completed: bool | None = None,
) -> TodoListResponse:
    items, total = await todo_crud.list_todos(db, limit, offset, is_completed)
    return TodoListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{todo_id}", response_model=TodoRead)
async def read_todo(todo_id: int, db: AsyncSession = Depends(get_db)) -> Todo:
    return await _get_todo_or_404(db, todo_id)


@router.patch("/{todo_id}", response_model=TodoRead)
async def update_todo(
    todo_id: int, todo_in: TodoUpdate, db: AsyncSession = Depends(get_db)
) -> Todo:
    todo = await _get_todo_or_404(db, todo_id)
    return await todo_crud.update(db, todo, todo_in)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: int, db: AsyncSession = Depends(get_db)) -> None:
    todo = await _get_todo_or_404(db, todo_id)
    await todo_crud.delete(db, todo)
