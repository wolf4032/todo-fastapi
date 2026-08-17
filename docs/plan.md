# TODO アプリ + ローカルを汚さないフルスタック開発環境の構築

## Context

`todo-fastapi` は現在空のディレクトリ。ここに学習用の TODO アプリ（FastAPI + PostgreSQL）を構築する。

ただし目的はアプリ単体ではなく、**次の3つを同時に確立すること**。

1. **ローカル PC を一切汚さない開発環境**: ホストに Python も Node も入れない。すべてコンテナ内。
2. **快適な開発体験**: Dev Container 接続中の VS Code で、git の差分表示が効き、インポートに誤った波線が出ず、言語を問わず保存時にフォーマッタが走る。
3. **本番との乖離を最小化**: 開発・テスト・CI・本番が同じ Dockerfile・同じロックファイル由来であること。デプロイ後の「手元では動いた」を構造的に潰す。

今回のアプリ機能は TODO の CRUD API のみ。フロントエンドとユーザー認証は将来の追加とし、**追加時に構成を作り直さずに済むレイアウト**を最初から敷く。

進め方は**毎回「何かが動く」単位で 12 ステップに分割**し、各ステップで「実装 → 解説 → 自分で叩ける確認コマンド → 理解確認の問い → コミット」を回す。コード中の初見の記法には日本語の学習用コメントを入れる（実務ではコメント過多になる旨を README に明記し、後で削れるようにする）。

**解説は各ステップで初出の概念を都度行う**。この計画書に出てくる用語（構造化ログ、graceful shutdown、依存性注入など）を事前に理解している必要はなく、それが登場するステップで説明する。

コミットメッセージは **Conventional Commits**（`feat:` `fix:` `chore:` `docs:` `test:` `refactor:` の種別ラベルを先頭に付ける規約）に従うが、**説明本文は日本語**で書く。例: `feat: TODO の作成・取得 API を追加`

---

## 設計判断と根拠

この5点が構成の骨格。判断の根拠は `docs/adr/` に ADR として残す。

### 1. 開発環境は「ツールボックス方式」— アプリの本番イメージとは別系統

`.devcontainer/` に**開発専用のツールボックスイメージ**を用意し、VS Code はここに接続する。アプリの実行コンテナ（`api`、将来の `web`）は本番と同じ Dockerfile から作り、ツールボックスとは別に compose で立てる。

**根拠**: VS Code の Dev Container は **1ウィンドウにつき1コンテナにしか接続できない**。サービスごとに dev コンテナを分ける流派だと、バックエンド用コンテナに接続した状態でフロントのコードを開いた瞬間、そのコンテナに TypeScript も `node_modules` も無いため「モジュールが見つかりません」の波線が全面に出る。**言語をまたいで波線を出さないためには、両方の言語環境と両方の依存関係が接続先の1コンテナ内に揃っている必要がある**。要件2を満たすにはツールボックス方式しかない。

その代わり「開発ツールが本番イメージに混入する」問題は、ツールボックスを本番イメージから完全に切り離すことで解決する。

**将来 Node を足す方法は Dev Container Features**（`devcontainer.json` に `ghcr.io/devcontainers/features/node:1` を1行）。公式イメージから `COPY --from=node /usr/local/bin ...` でランタイムを移植する手法もあるが、不足する共有ライブラリ（pip が要求する `libexpat.so.1` 等）・PATH・バージョンが埋め込まれたディレクトリ名を手で埋める必要があり、バージョン更新のたびに壊れやすい。ツールボックス用途では Features が素直。

### 2. アプリは本番と同じ Dockerfile の dev ステージで走らせる

開発中の uvicorn は**ツールボックスではなく `api` コンテナ**で走らせる。テストも同じ `api` イメージ（dev ステージ）で実行する。

**根拠**: 開発・テスト・CI の実行環境が同一になり、本番とも `base` ステージを共有する。デプロイ後の予期せぬ差異を構造的に減らせる。

デバッグは `debugpy` のポートアタッチで行う（compose の起動コマンド1行 + `.vscode/launch.json` 15行程度）。`--reload` はリローダが子プロセスでアプリを動かす都合でブレークポイントを拾い損ねることがあるため、**`make dev`（reload あり・デバッガなし）と `make debug`（reload なし・デバッガ待受）を分ける**。

なお `.vscode/` 配下の `settings.json` / `launch.json` / `extensions.json` は**コミットする**。個人の好みではなくプロジェクトの開発環境定義であり、GitHub 公式の `.gitignore` テンプレートもこの4ファイルだけを例外として除外対象から外している。環境定義をリポジトリに残すという本方針とも一致する。

### 3. マルチステージ + venv

```dockerfile
FROM python:3.13-slim AS base          # 共通土台。開発も本番もここから派生
FROM base AS builder                   # uv sync --frozen --no-dev  → /opt/venv
FROM base AS builder-dev               # uv sync --frozen           → /opt/venv（dev依存込み）
FROM base AS dev                       # builder-dev の venv を COPY。コードはバインドマウント
FROM base AS prod                      # builder の venv + app/ を COPY。uv もテストも無し、非root
```

**マルチステージの主目的は「1つの Dockerfile から dev と prod を作り分けること」**。イメージ縮小はその副産物。

**venv を使う理由は隔離ではなく `COPY` の都合**。システム Python に入れると、ライブラリは `site-packages`、実行スクリプト（`uvicorn` / `alembic`）は `/usr/local/bin` と散るため、ステージ間の移送が壊れやすい。`/opt/venv` に固めれば `COPY --from=builder /opt/venv /opt/venv` の1行で済む。また `uv sync` は仮想環境を作る前提のコマンドなので、`UV_PROJECT_ENVIRONMENT=/opt/venv` で置き場所を指定するのが素直な使い方。

**本番イメージに uv とテストライブラリは入れない**。理由はサイズ・攻撃対象領域（CVE）・テスト専用コードが本番で動く経路を断つこと。バージョンの厳格さは実行時ではなく**ビルド時に `uv.lock` + `--frozen` が担保**するので、実行時に uv が居なくても再現性は落ちない。**dev も prod も同じロックファイルから作る**ので「テストが通った依存関係 = 本番の依存関係」と言い切れる。

### 4. モノレポレイアウト + サービスごとのビルドコンテキスト

`backend/` に Python 一式、将来 `frontend/` を並べる。compose のビルドコンテキストを `./backend` に絞ることで、**Docker デーモンに送られるファイルも `COPY` の起点も `backend/` 配下だけ**になり、ルートの compose や `.devcontainer/` や将来の `frontend/` はイメージから見えない。

**本番イメージから `tests/` を外すのは `.dockerignore` の仕事ではない**。`.dockerignore` はビルドコンテキスト全体に効くもので**ステージごとに切り替えられない**ため、ここに `tests/` を書くと dev ステージからも消える。正しくは prod ステージで `COPY app/ ./app/` と**必要なものだけを COPY する**ことで達成する。`.dockerignore` に書くのは `__pycache__` / `.pytest_cache` / `.venv` / `.git` のような、どのステージにも不要なものだけ。

### 5. compose ファイルは「共通 + 環境ごとの差分」で重ねる

Compose の複数ファイルマージ機能を使い、3ファイル構成にする。

| ファイル | 役割 | 読まれ方 |
|---|---|---|
| `compose.yaml` | 共通の基本定義（`db` / `api`） | 常に |
| `compose.override.yaml` | **開発差分**（バインドマウント、`target: dev`、`--reload`、ポート公開、`devtools`） | **ファイル名がこれなら自動** |
| `compose.prod.yaml` | 本番相当（`target: prod`） | `-f` で明示指定時のみ |

`docker compose up` が開発、`docker compose -f compose.yaml -f compose.prod.yaml up` が本番相当になる。**開発専用の `devtools` は `compose.override.yaml` に置く**ので、本番の構成定義に混ざらない。Dev Container からは `devcontainer.json` の `dockerComposeFile` に両ファイルを列挙して参照する。

---

## 技術選定

| 項目 | 採用 | 理由 |
|---|---|---|
| Web | FastAPI + Uvicorn | 型ヒントから OpenAPI が自動生成される |
| DB | PostgreSQL 17（Docker） | 実務標準 |
| ORM | SQLAlchemy 2.0（async / asyncpg） | 型ヒント前提の現行記法。FastAPI の非同期性能を活かす |
| マイグレーション | Alembic（async テンプレート） | スキーマ変更を差分ファイルで追跡 |
| 設定・検証 | Pydantic v2 / pydantic-settings | 環境変数と API 契約の型定義 |
| パッケージ管理 | uv（`pyproject.toml` + `uv.lock`） | ロックファイルで開発・CI・本番の依存を完全一致 |
| テスト | pytest + pytest-asyncio + httpx | FastAPI 公式が推奨する組み合わせ |
| 静的解析 | ruff（lint + format）、mypy | ruff は flake8 + black 相当を1ツールで担う |
| コミット前検査 | pre-commit | 壊れたコードがコミットに入るのを防ぐ |

## ディレクトリ構成（完成形）

```
todo-fastapi/
├── .devcontainer/
│   ├── devcontainer.json       # VS Code 接続設定・拡張機能・エディタ設定
│   └── Dockerfile              # 開発ツールボックス（git/make/uv/将来 Node）
├── .vscode/
│   ├── settings.json           # 保存時フォーマット等（コミットする）
│   ├── extensions.json
│   └── launch.json             # debugpy アタッチ設定
├── .editorconfig
├── .pre-commit-config.yaml
├── .gitignore
├── .env.example / .env         # .env はコミットしない
├── compose.yaml                # 共通定義（db / api）
├── compose.override.yaml       # 開発差分（devtools・バインドマウント等／自動で読まれる）
├── compose.prod.yaml           # 本番相当（-f で明示指定時のみ）
├── Makefile                    # 開発コマンドの単一窓口。CI からも同じものを呼ぶ
├── README.md
├── docs/adr/                   # 設計判断の記録
└── backend/
    ├── Dockerfile              # base → builder / builder-dev → dev / prod
    ├── .dockerignore
    ├── pyproject.toml / uv.lock
    ├── alembic.ini / migrations/
    ├── app/
    │   ├── main.py
    │   ├── core/
    │   │   ├── config.py       # Settings（pydantic-settings）
    │   │   ├── logging.py      # 構造化ログ + リクエストID
    │   │   └── exceptions.py   # 統一エラーレスポンス
    │   ├── db/{base.py, session.py}
    │   ├── models/todo.py
    │   ├── schemas/todo.py
    │   ├── crud/todo.py
    │   └── api/
    │       ├── deps.py         # DB セッション、将来の current_user
    │       └── v1/{router.py, endpoints/todos.py}
    └── tests/{conftest.py, unit/, integration/}
```

**レイヤ分割の意図**: エンドポイント（HTTP の関心事）→ crud（DB の関心事）→ models（テーブル定義）。認証追加時は `models/user.py` + `api/v1/endpoints/auth.py` + `deps.get_current_user` を足し、`Todo` に `user_id` 外部キーを追加するだけで済む。`/api/v1` プレフィックスは破壊的変更時に v2 を並走させるため。

## 一般的な観点の扱い

**この表の用語を今わかっている必要はない**。それぞれが登場するステップで、なぜ必要なのかから解説する。

| 観点 | 今回 | 内容・理由 |
|---|---|---|
| 設定の外部化（12-factor） | 実装 | 設定は環境変数のみ、`Settings` に集約。イメージに秘密を焼かない |
| ログを標準出力へ | 実装 | コンテナの流儀。JSON 構造化ログ + リクエスト ID で追跡可能に |
| 統一エラーレスポンス | 実装 | 例外ハンドラで形を揃える。クライアントが機械的に処理できる |
| 非 root 実行 | 実装 | 本番イメージもツールボックスも非 root。バインドマウントの UID も合わせる |
| graceful shutdown | 実装 | `lifespan` で DB コネクションプールを明示的に閉じる |
| ヘルスチェック | 実装 | `/health`（プロセス生存）と `/health/db`（依存先疎通）を分ける |
| 適切な HTTP ステータス | 実装 | 201 / 204 / 404 / 422 を正しく返す |
| ページネーション | 実装 | 一覧 API に最初から入れる。後付けは破壊的変更になる |
| テストピラミッド | 実装 | unit / integration を分離。E2E はフロント追加時 |
| コミット前検査 | 実装 | pre-commit で ruff / mypy を通してからコミット |
| 設計判断の記録 | 実装 | `docs/adr/` に ADR を残す |
| CORS | 設定枠のみ | フロント追加時に有効化。`Settings` に許可オリジンの枠を用意 |
| CI/CD | 見越すのみ | Makefile とロックファイルで前提を整える。GitHub Actions は後日 |
| 依存の自動更新・脆弱性検査 | 見越すのみ | リモート接続後に Dependabot / `uv` の監査を導入 |
| 認証・認可 | スコープ外 | レイヤ分割で追加余地を確保済み |

---

## 実装ステップ（全 12 回）

各ステップの末尾でコミット。種別ラベルは Conventional Commits、説明は日本語。

### Step 1: git の初期化とコミットの著者設定

- `git init`（デフォルトブランチ `main`）、`.gitignore`（`.vscode/` は `settings.json` / `launch.json` / `extensions.json` を例外として残す）、`.editorconfig`
- `user.name` / `user.email` を **リポジトリローカル（`.git/config`）に設定**。`.git` はコンテナにもバインドマウントされるので、ホストでも Dev Container 内でも同じ ID が効く。name / email は着手時にお伺いする
- **`~/.gitconfig` は変更しない**。リポジトリローカル設定だけで完結し、それがコンテナ内でも効く以上、ホームの設定を触る理由がない（`includeIf "gitdir:"` はコンテナ内ではパスが `/workspaces/...` になり一致しないため、そもそも当てにできない）
- 解説: リポジトリローカル設定がグローバル設定より優先される仕組み、`.gitignore` の否定パターン（`!`）
- 確認: `git config user.email` が設定したアドレスを返すこと
- コミット: `chore: リポジトリを初期化`

### Step 2: Dev Container を立ち上げ、git が効く状態にする

- `.devcontainer/Dockerfile`: `python:3.13-slim` に **git・make・curl・ca-certificates** と uv を入れ、非 root ユーザー `vscode` を作成
- `.devcontainer/devcontainer.json`: `dockerComposeFile` に `compose.yaml` と `compose.override.yaml` を列挙し `devtools` サービスを指定。`remoteUser: "vscode"`、`updateRemoteUserUID: true`、`workspaceFolder`
- `compose.yaml`（空の骨格）と `compose.override.yaml` に `devtools` サービス（`command: sleep infinity`、ワークスペースをバインドマウント）
- 解説: **前回 git が消えた2つの原因** —(a) slim に git が入っていない (b) root 実行 + ホスト所有のバインドマウントで git 2.35.2 以降の *dubious ownership* 判定に引っかかる（→ `updateRemoteUserUID` で UID を合わせる、保険で `safe.directory`）。加えて Dev Container Features という拡張手段（将来 Node を足す口）
- 確認: VS Code で「Reopen in Container」→ コンテナ内ターミナルで `git status` / `git log` / ソース管理ビューに変更が出ること / `whoami` が `vscode` / `id -u` がホストと一致
- 問い: なぜ root のままだと git がリポジトリを認識しないのか？
- コミット: `chore: Dev Container を追加`

### Step 3: PostgreSQL を立てる

- `compose.yaml` に `db`（`postgres:17-alpine`、名前付きボリューム `pgdata`、`pg_isready` の healthcheck）
- `.env.example` / `.env`
- 解説: コンテナとボリュームの関係（消えるもの／残るもの）、healthcheck が後で `depends_on` に効いてくる理由、`.env` をコミットしない理由
- 確認: `docker compose up -d db` → `docker compose exec db psql -U todo -d todo -c '\l'` → `down` 後に再起動してもデータが残ること
- コミット: `chore: PostgreSQL サービスを追加`

### Step 4: backend のマルチステージ Dockerfile と最小 FastAPI

- `backend/pyproject.toml`（fastapi / uvicorn、dev グループに pytest 等）、`uv.lock`、`backend/Dockerfile`（base / builder / builder-dev / dev / prod）、`backend/.dockerignore`（`__pycache__` / `.pytest_cache` / `.venv` / `.git` のみ）
- `backend/app/main.py` に `GET /health` のみ
- `compose.yaml` に `api` の共通定義（`context: ./backend`、`depends_on: db(healthy)`）、`compose.override.yaml` に開発差分（`target: dev`、`./backend:/app` バインドマウント、8000・5678 公開、`--reload`）
- 解説: **ビルドコンテキストを `./backend` に絞る効果**、各ステージの役割、**`.dockerignore` はステージごとに切り替えられない**こと（だから本番から tests を外すのは `COPY` の書き方で行う）、`--reload` が開発専用である理由
- 確認: `curl localhost:8000/health` / `http://localhost:8000/docs` / `main.py` を編集して自動リロード / `docker compose exec api ls /opt/venv/bin`
- 問い: `dev` ステージではコードを `COPY` せずバインドマウントするのはなぜか？
- コミット: `feat: バックエンドのコンテナと最小構成の FastAPI を追加`

### Step 5: 設定・DB 接続・ログ・エラーハンドリング（アプリ基盤）

- `core/config.py`（`Settings`、`postgresql+asyncpg://` の組み立て、CORS 許可オリジンの枠）
- `db/session.py`（`create_async_engine`、`async_sessionmaker(expire_on_commit=False)`、`get_db`）
- `core/logging.py`（JSON 構造化ログ + リクエスト ID のミドルウェア）
- `core/exceptions.py`（統一エラーレスポンス形式の例外ハンドラ）
- `main.py` に `lifespan`（起動・終了時のコネクションプール管理）と `GET /health/db`
- `.vscode/launch.json`（コミットする）+ `make debug` を用意し、**実際にブレークポイントを止めてみる**
- 解説: **`async` / `await` とは何か**（DB 応答待ちの間に他リクエストを処理できる）、**依存性注入とは何か**（`Depends` が後のテスト差し替えを可能にする）、`expire_on_commit=False` が必要な理由、**構造化ログとリクエスト ID** が調査で効く理由、**graceful shutdown** で接続を閉じる意味、`--reload` とデバッガの相性問題
- 確認: `curl localhost:8000/health/db` / ログが JSON で出る / `.env` のパスワードをわざと壊してエラーの出方を見る / `make debug` でブレークポイントが止まる
- 問い: なぜ接続文字列の組み立てを `Settings` 1か所に集約するのか？
- コミット: `feat: 設定・DB 接続・ログ・エラーハンドリングを追加`

### Step 6: モデルと Alembic マイグレーション

- `db/base.py`（`DeclarativeBase`）、`models/todo.py`
- `alembic init -t async migrations` → `env.py` の `target_metadata` を `Base.metadata` に、URL を `Settings` から読むよう修正
- `alembic revision --autogenerate` → **生成された SQL を一緒に読んでから** `upgrade head`
- マイグレーションは `make migrate` で明示実行する（アプリ起動処理には含めない。理由は解説で扱う）

| カラム | 型 | 備考 |
|---|---|---|
| `id` | `int` | 主キー、自動採番 |
| `title` | `str(255)` | NOT NULL |
| `description` | `str \| None` | Text |
| `is_completed` | `bool` | NOT NULL, default False, インデックス |
| `due_date` | `datetime \| None` | timezone-aware |
| `created_at` / `updated_at` | `datetime` | `server_default=func.now()`、`onupdate` |

- 解説: **SQLAlchemy 2.0 の `Mapped[str]` / `mapped_column()` 記法**（ネット上の 1.x 系記事とは書き方が違う）、`autogenerate` は万能ではないので必ず目視レビューすること、`alembic_version` テーブルの役割、**本番でマイグレーションをアプリ起動に含めない理由**（複数レプリカが同時に実行して競合する）
- 確認: `make migrate` → `docker compose exec db psql -U todo -d todo -c '\d todos'` / `alembic downgrade -1` → `upgrade head`
- 問い: `create_all()` ではなく Alembic を使うと何が嬉しいか？
- コミット: `feat: Todo モデルと初回マイグレーションを追加`

### Step 7: スキーマ・CRUD 層・作成／取得 API

- `schemas/todo.py`（`TodoBase` → `TodoCreate`（`min_length=1`）、`TodoRead`（`ConfigDict(from_attributes=True)`））
- `crud/todo.py`（`create` / `get`。見つからなければ `None` を返す）
- `api/deps.py`、`api/v1/router.py`、`api/v1/endpoints/todos.py` に `POST /api/v1/todos`（201）、`GET /api/v1/todos/{id}`（200 / 404）
- 解説: **ORM モデルと Pydantic スキーマを分ける理由**（DB の都合と API の契約は別物。例: `password_hash` を返さない）、`response_model` が OpenAPI とレスポンス整形の両方を担うこと、404 への変換をエンドポイント層の責務に置く理由
- 確認: `POST` → `GET` → 存在しない ID で 404 → `title` 空文字で 422（統一エラー形式で返ること）
- 問い: `TodoCreate` と `TodoRead` を1クラスにまとめると何が困るか？
- コミット: `feat: TODO の作成・取得 API を追加`

### Step 8: 残りの CRUD

| メソッド | パス | ステータス |
|---|---|---|
| GET | `/api/v1/todos` | 200（`limit` / `offset` / `is_completed`） |
| PATCH | `/api/v1/todos/{id}` | 200 / 404 |
| DELETE | `/api/v1/todos/{id}` | 204 / 404 |

- `TodoUpdate`（全フィールド省略可）、`TodoListResponse`（`items` / `total` / `limit` / `offset`）
- 解説: **PATCH と PUT の違い**と `model_dump(exclude_unset=True)` が部分更新の要になること、ページネーションを最初から入れる理由、DELETE が 204（ボディなし）である理由
- 確認: 複数件登録して `?limit=2&offset=1` / `?is_completed=true` → PATCH → DELETE で 204 → 再取得で 404
- 問い: `exclude_unset=True` を外すと、`{"is_completed": true}` だけ送ったとき何が起きるか？
- コミット: `feat: TODO の一覧・更新・削除 API を追加`

### Step 9: テスト

- `tests/conftest.py`: テスト専用 DB（`todo_test`）を作成し Alembic でスキーマ適用。テストごとにトランザクションを張ってロールバック。`httpx.AsyncClient(transport=ASGITransport(app=app))` でネットワークを介さず API を叩く。`app.dependency_overrides[get_db]` でテスト用セッションを注入
- `tests/unit/test_schemas.py`（DB 不要）、`tests/integration/test_todos_api.py`（CRUD 一連 + 異常系）
- **テストは `api` コンテナ（dev ステージ）で実行**し、開発・テスト・CI の環境を揃える
- 解説: **テストピラミッドと、単体テスト・結合テストの違い**、`dependency_overrides` が Step 5 の `Depends` によって可能になっていること、テスト DB を分ける理由、トランザクションロールバックでテストが汚れない仕組み
- 確認: `make test` / わざと実装を壊してテストが落ちることを見る
- 問い: `unit/` と `integration/` を分けておくと CI でどう活きるか？
- コミット: `test: 単体テストと結合テストを追加`

### Step 10: 静的解析・pre-commit・エディタ体験の仕上げ

- `pyproject.toml` に ruff / mypy / pytest の設定を集約し、既存コードに適用して指摘を一緒に読む
- `.pre-commit-config.yaml`（ruff check・ruff format・末尾空白などの基本フック）
- `.vscode/settings.json` / `extensions.json`、`devcontainer.json` の `customizations` に拡張機能を列挙
- **波線対策**: `python.defaultInterpreterPath` をコンテナ内 `/opt/venv/bin/python` に固定
- **保存時フォーマット**: `editor.formatOnSave` + Python の既定フォーマッタを ruff に。⚠️ **`files.autoSave` を `afterDelay` にすると `formatOnSave` は発火しない**（VS Code の仕様）ため `onFocusChange` を使う
- 解説: **pre-commit とは何か**（コミット前に自動で検査を走らせる仕組み）、環境定義をリポジトリに入れると別マシンでも同じ開発体験が再現できること、Makefile を CI から呼べば手元と CI の実行内容がずれないこと
- 確認: 適当に崩したコードを書いて保存 → 自動整形される / 未インストールのパッケージを import して波線が出る（＝解決が効いている証拠）/ `make lint` が通る / `git commit` で pre-commit が走る
- コミット: `chore: Lint・フォーマット・pre-commit・エディタ設定を追加`

### Step 11: 本番相当イメージの確認

- `compose.prod.yaml`（`target: prod`、`--reload` なし、バインドマウントなし、非 root）
- `docker build --target prod` と `--target dev` のイメージサイズを比較し、**本番イメージに uv・pytest・ruff・tests が存在しないこと**を実際に確認する
- 解説: **`compose.override.yaml` が自動で読まれ、`-f` を明示すると読まれない**仕組み、本番でのマイグレーション実行を別ジョブにすること、バインドマウントが無い＝イメージに焼かれたコードだけが動くこと、非 root 実行の意味
- 確認: `make prod-up` → `curl localhost:8000/health` → `docker compose ... exec api which uv`（見つからないこと）/ `ls /app`（tests が無いこと）/ `docker images` でサイズ比較
- 問い: 本番イメージに pytest が入っていると、どんなリスクがあるか？
- コミット: `chore: 本番向けイメージのビルド構成を追加`

### Step 12: README と ADR

- `README.md`: セットアップ手順、Dev Container の使い方、各ディレクトリの役割、よく使うコマンド、学習用コメントの扱い、将来の拡張 TODO
- `docs/adr/`: 「開発環境にツールボックス方式を採用した理由」「マルチステージで venv を使う理由」「アプリを api コンテナで走らせる理由」「compose を共通＋差分に分けた理由」を記録
- **フロントエンド追加時の手順**を README に明記（`frontend/` 作成 → `devcontainer.json` に Node の Feature を1行追加 → `node_modules` は名前付きボリュームに載せる → `compose.yaml` に `web` を追加）
- 解説: **ADR とは何か**（設計判断を「決めたこと・背景・理由・却下した案」の形で残す軽量な文書）
- コミット: `docs: README と設計判断の記録を追加`

---

## 全体の最終検証

```bash
# クリーンな状態から通しで確認
docker compose down -v
cp .env.example .env

# 1. Dev Container: VS Code で「Reopen in Container」
#    → git status が動く / ソース管理ビューに差分が出る / 波線が出ない / 保存で整形される

# 2. 以下はコンテナ内ターミナルから
make up            # db + api 起動
make migrate       # マイグレーション適用
curl -s localhost:8000/health
curl -s localhost:8000/health/db
open http://localhost:8000/docs        # Swagger UI から CRUD を一通り操作
docker compose exec db psql -U todo -d todo -c '\dt'

make test          # unit + integration
make lint          # ruff + mypy
make debug         # ブレークポイントが止まること

# 3. 本番相当（compose.override.yaml が読まれないことを確認）
make prod-up
curl -s localhost:8000/health
docker images | grep todo              # dev と prod のサイズ差

# 4. 履歴
git log --oneline                      # 12 コミットが機能単位で並んでいること
```

## スコープ外（将来の拡張）

- **フロントエンド**: `frontend/` + ツールボックスに Node の Dev Container Feature を追加 + compose に `web`。本番はビルド済み静的ファイルを配信する独立イメージ
- **ユーザー認証**: `models/user.py`、`api/v1/endpoints/auth.py`（JWT）、`deps.get_current_user`、`todos.user_id` 外部キー
- **CI/CD**: GitHub Actions から `make lint` / `make test` を実行し、`--target prod` でイメージをビルド
- **E2E テスト**: フロント追加時に Playwright を `tests/e2e/` に配置
- **リモートリポジトリ**: 今回はローカルコミットのみ。GitHub への push は後日
