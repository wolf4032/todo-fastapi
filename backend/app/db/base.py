from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # 全モデル共通の親クラス。Alembic の autogenerate はこの Base.metadata と
    # 実際の DB スキーマを比較して差分を検出する。→ docs/notes/topic-alembic-basics.md
    pass
