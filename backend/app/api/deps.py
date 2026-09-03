from app.db.session import get_db

__all__ = ["get_db"]

# エンドポイントは app.db.session ではなく app.api.deps から Depends 対象を import する。
# 将来 get_current_user 等を足す先をここに集約しておく。
# → docs/notes/step-07-todo-schema-crud-api.md
