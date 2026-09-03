from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.crud import todo as todo_crud
from app.models.todo import Todo
from app.schemas.todo import TodoCreate, TodoRead

router = APIRouter(prefix="/todos", tags=["todos"])


@router.post("", response_model=TodoRead, status_code=status.HTTP_201_CREATED)
async def create_todo(
    todo_in: TodoCreate, db: AsyncSession = Depends(get_db)
) -> Todo:
    return await todo_crud.create(db, todo_in)


@router.get("/{todo_id}", response_model=TodoRead)
async def read_todo(todo_id: int, db: AsyncSession = Depends(get_db)) -> Todo:
    todo = await todo_crud.get(db, todo_id)
    if todo is None:
        # crud 層が返した None をここで HTTP 404 に変換する。
        # → docs/notes/step-07-todo-schema-crud-api.md
        raise HTTPException(status.HTTP_404_NOT_FOUND, "todo not found")
    return todo
