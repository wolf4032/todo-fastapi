import pytest
from pydantic import ValidationError

from app.schemas.todo import TodoCreate, TodoUpdate


def test_todo_create_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        TodoCreate(title="")


def test_todo_create_accepts_title_only() -> None:
    todo_in = TodoCreate(title="牛乳を買う")
    assert todo_in.description is None
    assert todo_in.due_date is None


def test_todo_update_rejects_empty_title() -> None:
    with pytest.raises(ValidationError):
        TodoUpdate(title="")


def test_todo_update_exclude_unset_keeps_only_sent_fields() -> None:
    # is_completed だけ送ったとき、model_dump(exclude_unset=True) に他のフィールドが
    # 含まれないことを確認する。→ docs/notes/step-08-todo-crud-remainder.md
    todo_in = TodoUpdate(is_completed=True)
    assert todo_in.model_dump(exclude_unset=True) == {"is_completed": True}
