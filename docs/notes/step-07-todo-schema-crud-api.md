# Step 7: スキーマ・CRUD 層・作成／取得 API

作成物: `backend/app/schemas/todo.py`（`TodoBase` / `TodoCreate` / `TodoRead`）、`backend/app/crud/todo.py`（`create` / `get`）、`backend/app/api/deps.py`、`backend/app/api/v1/router.py`、`backend/app/api/v1/endpoints/todos.py`（`POST /api/v1/todos` / `GET /api/v1/todos/{todo_id}`）、`backend/app/main.py`（ルーター登録）

FastAPI の `Depends()` / DI の仕組みとテストでの差し替え、URL がディレクトリ構造ではなく `prefix` の足し算で決まること、API バージョニングの意図は、ステップをまたいで参照する一般知識として以下に切り出した。

- → [topic-fastapi-dependency-injection.md](topic-fastapi-dependency-injection.md)

直列化（Serializer）という言葉の由来は Pydantic の基礎知識に、`devtools` から `api` への `curl` が繋がらなかった件は Docker のネットワーク知識に追記した。

- → [topic-pydantic-basics.md](topic-pydantic-basics.md)
- → [topic-docker-networking.md](topic-docker-networking.md)

ここでは backend 固有の設計判断を扱う。

---

## ORM モデルと Pydantic スキーマを分離した理由

`Todo`（ORM モデル）は DB のテーブル構造を表し、`TodoRead` / `TodoCreate`（Pydantic スキーマ）は API が外部に約束する契約を表す。今は形がほぼ同じだが、将来 `Todo` に「DB には要るが外に出したくない」列が増えたとき、モデルとスキーマが同じクラスだと誤って漏らしてしまう。別クラスにしておけば `response_model=TodoRead` に載せない限りレスポンスに出ない。

`response_model` は返り値（今回は ORM の `Todo` インスタンス）を指定した型に絞り込んで整形する役割と、その形を OpenAPI（`/docs`）のスキーマとして公開する役割の両方を兼ねる。`TodoRead` に `ConfigDict(from_attributes=True)` を付けているのは、`dict` だけでなく属性アクセスできるオブジェクト（ORM インスタンス）からも値を読み取れるようにするため。

## 404 への変換をエンドポイント層に置いた理由

`crud.get()` は「見つからない」を例外ではなく `None` で返す。CRUD 層は HTTP を知らない（DB の関心事だけを扱う）層にしておき、`None` → `HTTPException(404)` の変換は HTTP の関心事を扱うエンドポイント層に置く。同じ `crud.get()` を将来 CLI 等の別経路から呼んでも「HTTP 404」という概念を持ち込まずに済む。

## `create()` 内の `commit` → `refresh` について

`Todo(**todo_in.model_dump())` の時点では `id` / `created_at` は未定義。`db.add()` はまだ SQL を送らず、`db.commit()` で初めて `INSERT` が実行される。PostgreSQL は `INSERT ... RETURNING` に対応しており、SQLAlchemy はこれを自動で使うため、実際には commit の時点でサーバー側の値も取得できていることが多い。それでも明示的に `refresh()` を呼んでいるのは、DB の種類や SQLAlchemy の内部挙動に依存せず「DB が決めた値を確実に反映する」意図をコードで明示するため。

## 422 のエラー形式は自動で統一される

`TodoCreate.title: str = Field(min_length=1)` の検証に失敗すると FastAPI が自動で 422 を返す。レスポンスの形は Step 5 で作った `register_exception_handlers` の `RequestValidationError` ハンドラがそのまま面倒を見るため、今回は何も書いていない。

---

## 確認して分かったこと

- `POST /api/v1/todos` → 201、`id` / `created_at` / `updated_at` / `is_completed`（デフォルト `false`）が自動で埋まって返る
- `GET /api/v1/todos/{id}` → 200、`POST` した内容と一致
- 存在しない `id` → 404
- `title` 空文字 → 422、統一エラー形式（`error.code` / `message` / `request_id` / `details`）の `details` に Pydantic の `type` / `loc` / `msg` / `input` / `ctx` がそのまま入る
- `/docs`（Swagger UI）に `todos` タグで `POST /api/v1/todos` と `GET /api/v1/todos/{todo_id}` が表示され、`default` タグに Step 5 の `/health` 系が並んだ
- `devtools` コンテナのシェルから `curl localhost:8000/...` を叩くと `Connection refused` になった。原因と対処は [topic-docker-networking.md](topic-docker-networking.md) へ
- `docker compose logs api` に、今回作っていないパス（`/api/goods/new` 等）へのアクセスが記録されていた。中身から見て今回のアプリとは無関係な、インターネット側からのスキャン bot のトラフィックと判断（別途ルーター側の公開設定を確認する対象とし、本リポジトリでは対応しない）
- 理解確認の問い「`TodoCreate` と `TodoRead` を1クラスにまとめると何が困るか」への回答: 将来 `Todo` にパスワードハッシュのような「DB には要るが外に出したくない」列が増えたとき、1クラスだと `response_model` で絞り込む先が無く、誤ってレスポンスに漏らしてしまう
