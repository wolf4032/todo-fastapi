from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoBase(BaseModel):
    # 作成にも読み取りにも共通するフィールドだけをここに置く。
    title: str
    description: str | None = None
    due_date: datetime | None = None


class TodoCreate(TodoBase):
    # 空文字だけの title を弾く。min_length はバイト数ではなく文字数で数える。
    title: str = Field(min_length=1)


class TodoRead(TodoBase):
    # from_attributes=True で、dict だけでなく Todo（ORM インスタンス）からも
    # 属性アクセス（todo.id など）で値を読み取れるようになる。
    # → docs/notes/step-07-todo-schema-crud-api.md
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_completed: bool
    created_at: datetime
    updated_at: datetime


class TodoUpdate(BaseModel):
    # 全フィールドが省略可（PATCH の部分更新）。TodoBase を継承しない理由は、
    # 継承すると将来 TodoBase に必須フィールドが増えたとき、ここでの
    # オーバーライド漏れに気づけないため。差分を表す別概念として独立させる。
    # exclude_unset との組み合わせ方 → docs/notes/step-08-todo-crud-remainder.md
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    due_date: datetime | None = None
    is_completed: bool | None = None


class TodoListResponse(BaseModel):
    items: list[TodoRead]
    total: int
    limit: int
    offset: int
