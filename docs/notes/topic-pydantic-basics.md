# Pydantic / pydantic-settings の基礎

Step 5 で `pydantic-settings`（`Settings`）を初めて明示的に使った際に整理した基礎知識。Pydantic自体はFastAPIが最初から内部で使っているが、自分でクラスを書くのは今回が最初だった。

## 今回追加した4パッケージの役割分担

```
HTTP リクエスト
   │
   ▼
FastAPI ── Pydantic（型の定義・検証）
   │           └─ pydantic-settings（Pydantic を「環境変数から読む」用途に特化させたもの）
   ▼
SQLAlchemy（Python のオブジェクト ⇔ SQL 文の変換）
   │
   ▼
asyncpg（実際に PostgreSQL と通信するドライバ）
   │
   ▼
PostgreSQL
```

`debugpy` はこの流れとは無関係で、VS Codeとアプリのプロセスを繋ぐデバッグ専用の道具（→ [topic-docker-networking.md](topic-docker-networking.md)）。

## Pydantic ≒ dataclass + バリデーション

`dataclasses.dataclass` は型ヒントを**チェックしない**（`age: int` に `"abc"` を入れても実行時エラーにならない、ただの飾り）。Pydanticはインスタンス化のタイミングで実際に型を検証し、可能なら変換もする（`"5"` という文字列を `int` フィールドに渡すと `5` に変換される、など）。

この「検証 + 変換」があるからこそ、外部から来た信用できないデータ（HTTPリクエストボディ、環境変数）を受け取る境界に向いている。

## pydantic-settings の環境変数マッチング

`class Settings(BaseSettings)` のフィールドは、既定で**大文字小文字を区別せずに**同名の環境変数と対応する（`postgres_user: str` ↔ `POSTGRES_USER`）。この既定値は `case_sensitive=False` で、`SettingsConfigDict` で明示しても意味は変わらない（デフォルトと同じ値を書いても動作は変わらないため、[config.py](../../backend/app/core/config.py) では省略している）。
