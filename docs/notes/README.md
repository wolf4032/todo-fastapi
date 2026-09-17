# 学習メモ

実装を進めながら出てきた一般知識・つまずき・その解決を記録したもの。

- **ステップノート** (`step-XX-*.md`) … そのステップで扱った内容の記録
- **トピックノート** (`topic-*.md`) … ステップをまたいで参照する一般知識

実装計画そのものは [../plan.md](../plan.md)、設計判断の記録は `../adr/`（Step 12 で作成予定）。

## ステップノート

| ステップ | 内容 |
|---|---|
| [Step 1](step-01-git-init.md) | git の初期化、初期ブランチ名のやり直し、設定の優先順位、`.gitignore` の否定パターン、`.editorconfig` |
| [Step 2](step-02-devcontainer.md) | Dev Container、ツールボックス方式の根拠、git の所有者チェック、`ARG` と `ENV`、Compose のマージ、Claude Code の導入 |
| [Step 3](step-03-postgres.md) | PostgreSQL、公式イメージの初回限定初期化、healthcheck と `depends_on` の関係、`.env` の変数展開と非コミットの理由 |
| [Step 4](step-04-backend-container.md) | backend のマルチステージ Dockerfile、ビルドコンテキストと `.dockerignore` の限界、`tool.uv.package = false`、非 root ユーザーと ARG、`backend/` を丸ごとマウントする理由、devtools の波線ギャップ |
| [Step 5](step-05-app-foundation.md) | `Settings`・DB接続・構造化ログ・統一エラーハンドリング、`.env` 書き換えで確認したエラーの出方、`debugpy` アタッチのトラブルシュート |
| [Step 6](step-06-alembic.md) | `Todo` モデルと初回マイグレーション、標準の生成手段のやり直し、`pyproject.toml`/`uv.lock`の食い違い、`create_all()`との比較 |
| [Step 7](step-07-todo-schema-crud-api.md) | `TodoCreate`/`TodoRead`、CRUD層、作成・取得API、ORMとスキーマの分離、404変換をエンドポイント層に置く理由、`devtools`から`api`へのcurlが繋がらなかった件 |
| [Step 8](step-08-todo-crud-remainder.md) | 一覧（ページネーション・絞り込み）・更新・削除API、`TodoUpdate`を`TodoBase`から独立させた理由、PATCHと`exclude_unset=True`、DELETEが204を返す理由、404変換の集約 |
| [Step 9](step-09-tests.md) | 単体テストと結合テスト、テスト用DBの分離、トランザクションロールバックによる独立、`dependency_overrides`、イベントループをまたいだDB接続の再利用で3件落ちた件 |

## トピックノート

| トピック | 内容 |
|---|---|
| [Docker のボリュームと権限](topic-docker-volumes.md) | マウントの3種類、永続性、名前付きボリュームの初回作成時のコピー、UID による権限、トラブルシュート |
| [ビルド時に決まること・実行時に決まること](topic-docker-build-and-run.md) | `RUN` と `CMD` のタイミングの違い、CMD とメインプロセス、compose の `command:` との関係、healthcheck の汎用的な仕組み、`docker compose up -d` |
| [async/await・並行処理](topic-async-await.md) | コルーチン、`await` が本当にブロックする範囲、並行処理と並列処理の違い、Python/JSの差、FastAPIでの実務上の注意 |
| [コンテナ間ネットワークとDNS](topic-docker-networking.md) | VS Code拡張機能の実行場所、`docker compose run` のDNS別名、ゾンビコンテナ、診断コマンド、`devtools`から`api`への`curl`が繋がらない理由 |
| [Pydantic/pydantic-settingsの基礎](topic-pydantic-basics.md) | 今回追加した4パッケージの役割分担、dataclassとの違い、環境変数の大文字小文字マッチング、なぜ「Serializer」と呼ぶか |
| [標準の生成手段があるファイルの扱い](topic-scaffold-generators.md) | `alembic init` / `uv add` / VS Codeのlaunch.json生成など、CLIやIDE操作での生成を優先する判断基準 |
| [SQLAlchemyの型ヒント・ORM/Coreと`default`/`server_default`](topic-sqlalchemy-defaults.md) | `Mapped[...]`とNOT NULL/nullableの対応、ORMとCoreの位置づけ、`default`と`server_default`の違い、使い分けの基準 |
| [Alembicの基本的な仕組み](topic-alembic-basics.md) | `create_all()`との違い、`alembic_version`と履歴の持ち方、`downgrade()`の実体、autogenerateの比較対象と`head`で実行すべき理由、`NullPool`/`run_sync`の理由 |
| [SQLAlchemyのクエリ構築と`scalar`/`scalars`](topic-sqlalchemy-querying.md) | `select()`が文を表すオブジェクトであること、`where`/`order_by`/`limit`/`offset`の連鎖、`scalar`という用語の由来（線形代数の用法とは別物）、`execute`/`scalar`/`scalars`の使い分け |
| [uvの依存管理](topic-uv-dependency-management.md) | `pyproject.toml`(緩い制約)と`uv.lock`(厳密な実体)の役割分担、`uv add`の冪等性、手動編集で起きた食い違い、`backend/.venv`が出来る理由 |
| [バージョン選定の考え方](topic-version-selection.md) | Python本体は「エコシステムの追随」と「周辺知識の蓄積」の2軸、個別ライブラリには後者の基準を持ち込まない理由 |
| [Webの通信まわりの地図](topic-web-protocol-basics.md) | ソケット/HTTP/HTTPサーバー/ASGIの4層、WSGIとASGIの違いと非同期一本である意味、httpxと`requests`の関係、`ASGITransport`が何を飛ばして何を通すか |
| [`python -m`と`sys.path`](topic-python-module-execution.md) | `sys.path`とシェルの`PATH`の違い、実行方法で`sys.path[0]`に何が入るか、空文字列`''`の意味、カレントディレクトリ自体は変わらないこと |
| [FastAPIの`Depends()`とDIの基礎](topic-fastapi-dependency-injection.md) | HTTPリクエストとエンドポイント関数の対応、DIの一般的な定義とFastAPIでの実装、`yield`による後片付け、`dependency_overrides`、URLがディレクトリ構造ではなく`prefix`の足し算で決まること、APIバージョニングの意図 |
