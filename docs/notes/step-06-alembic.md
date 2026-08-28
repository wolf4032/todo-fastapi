# Step 6: モデルと Alembic マイグレーション

作成物: `backend/app/db/base.py`（`Base`）、`backend/app/models/todo.py`（`Todo`）、`backend/alembic.ini`、`backend/migrations/`（`env.py` / `script.py.mako` / `versions/9181c9c00bed_create_todos_table.py`）、`backend/pyproject.toml`（`alembic` 追加）、`backend/Dockerfile`（本番ステージへの `alembic.ini` / `migrations/` の COPY 追加）、`Makefile`（`make migrate`）

SQLAlchemy 2.0の宣言的マッピング・ORM/Coreの関係・`default`/`server_default`・Alembicの基本的な仕組み・uvの依存管理・バージョン選定の考え方は、ステップをまたいで参照する一般知識として以下に切り出した。

- → [topic-sqlalchemy-defaults.md](topic-sqlalchemy-defaults.md)
- → [topic-alembic-basics.md](topic-alembic-basics.md)
- → [topic-uv-dependency-management.md](topic-uv-dependency-management.md)
- → [topic-version-selection.md](topic-version-selection.md)
- → [topic-scaffold-generators.md](topic-scaffold-generators.md)

ここでは backend 固有の設計判断と、実地で起きたトラブルシュートを扱う。

---

## `alembic` を dev グループではなく本体の依存に置いた理由

plan にある「マイグレーションをアプリ起動処理に含めない」は、「本番では実行しない」ではなく「**アプリ起動とは別のジョブとして実行する**」という意味。本番でも別途 `alembic upgrade head` を実行する前提なので、本番イメージにも `alembic` 本体と `migrations/` が必要になる。そのため `backend/Dockerfile` の `prod` ステージにも `COPY alembic.ini ./` と `COPY migrations/ ./migrations/` を追加した。

## 標準の生成コマンドを使わず手で書いてしまい、やり直した話

最初 `alembic.ini` / `migrations/env.py` / `migrations/script.py.mako` を `alembic init -t async migrations` を実行せず手で書いた。指摘を受けて削除し、実際に `alembic init` を実行してから中身を見比べたところ、次の差分が見つかった。

- `script.py.mako` の `down_revision` の型ヒントが `Union[str, Sequence[str], None]` であるべきところを `Union[str, None]` と書いていた（複数のマイグレーションが合流する場合の考慮漏れ）
- `migrations/README` を作り忘れていた
- `alembic.ini` の各設定項目の説明コメント、特に `[post_write_hooks]` の `black`/`ruff` 自動整形の実例が抜けていた（Step 10 で ruff を入れた後に使えそう）

「記憶にある「決まった内容」が実際にインストールされたバージョンの出力と一致する保証はない」という教訓の一般化は → [topic-scaffold-generators.md](topic-scaffold-generators.md) へ。

## `pyproject.toml` への手動追加で `uv.lock` と食い違った話

`alembic` を `pyproject.toml` の `dependencies` に直接書き足したところ、`uv.lock` には反映されず2ファイルが矛盾した状態になった。この状態で `docker compose build` していたら、`uv sync --frozen` は `uv.lock` だけを信頼するため、**`alembic` は実はインストールされないままだった。** `uv add --project backend alembic` を実行して解消した。

副産物として、`devtools` コンテナのシェルから直接 `uv add` を実行すると `backend/.venv` が作られた（`UV_PROJECT_ENVIRONMENT=/opt/venv` は `backend/Dockerfile` の中でしか効かないため）。実害は無いが、実際にアプリが使うのは `docker compose build` で作られる `/opt/venv` の方。詳細 → [topic-uv-dependency-management.md](topic-uv-dependency-management.md)

## ついでに検討したPythonのバージョン

3.13のままか3.14に上げるかを検討したが、技術的には3.14でも動きそう（`asyncpg`/`SQLAlchemy`のwheel、Docker公式イメージいずれも対応済み）と分かった上で、ネット上の周辺知識の蓄積量という観点から3.13を維持することにした。判断の経緯は → [topic-version-selection.md](topic-version-selection.md)

---

## 確認して分かったこと

- `docker compose exec api alembic revision --autogenerate -m "create todos table"` で `todos` テーブル・`ix_todos_is_completed` インデックスの追加が検出され、モデル通りのDDLが生成された
- 生成されたDDLを読むと、`updated_at` の `onupdate=func.now()` はDDLに一切現れず（ORMのUPDATE時のみ効くPython側の挙動のため）、`is_completed` にもDB側のデフォルト値は無い（`default=` はPython側の値のため）ことが実物で確認できた。詳細 → [topic-sqlalchemy-defaults.md](topic-sqlalchemy-defaults.md)
- `make migrate` → `docker compose exec db psql -U todo -d todo -c '\d todos'` で、モデル通りのテーブル構造（型・NOT NULL・デフォルト・インデックス）を確認
- `alembic downgrade -1` → `psql \d todos` で `todos` が消えることを確認 → `alembic upgrade head` で再実行すると、元と完全に同一の構造に復元された
- 「もしDBを最初まで `downgrade` した状態で `--autogenerate` すると何が起きるか」を検証（実行はせず机上で確認）: `autogenerate` はDBの実物としか比較しないため、既存のマイグレーションと重複する内容の新しいファイルが生成されてしまう。教訓は → [topic-alembic-basics.md](topic-alembic-basics.md)
- 理解確認の問い「`create_all()` ではなく Alembic を使うと何が嬉しいか」への回答（既存テーブルを `ALTER` できる／履歴が追える／ロールバックできる）も同ノートにまとめた
