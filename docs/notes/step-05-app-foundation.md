# Step 5: 設定・DB 接続・ログ・エラーハンドリング（アプリ基盤）

作成物: `backend/app/core/config.py`（`Settings`）、`backend/app/db/session.py`（`get_db`）、`backend/app/core/logging.py`（JSON構造化ログ + リクエストID）、`backend/app/core/exceptions.py`（統一エラーレスポンス）、`main.py`（`lifespan` / `GET /health/db`）、`.vscode/launch.json`、`Makefile`（`make debug`）、`compose.yaml`（`api` に DB 認証情報の `environment:` を追加）

`async`/`await`・並行処理・コルーチンの一般知識は → [topic-async-await.md](topic-async-await.md) に切り出した。ここでは backend 固有の設計判断と、デバッガ接続で起きた実地のトラブルシュートを扱う。

---

## `Settings.database_url` を `@property` にした理由

`postgres_user` 等の各フィールドから接続文字列を組み立てる箇所を、通常のフィールドではなく `@property` にしている。

これは「環境変数が実行中に変わるかもしれないから」ではない。`settings = Settings()` はプロセス起動時に1回だけ実行され、以後フィールドの値は固定される（Dockerコンテナの環境変数もコンテナ作成時に固定で、動いているプロセスの途中で書き換わることはない）。

理由は、`database_url` を通常のフィールドとして宣言すると、`DATABASE_URL` という環境変数からも上書きできる入力値として扱われてしまうため。`@property` にすることで「他のフィールドから導出される、外から差し替える余地のない値」であることを明示している。

## コネクションプールとセッションは別の階層

- **コネクションプール（`create_async_engine`）**: TCP接続の確立・認証コストを避けるため、PostgreSQL側の接続（＝PostgreSQL用語での「セッション」）を使い終わっても切断せず、次の別のリクエストのために再利用する仕組み
- **SQLAlchemyの `Session`（`get_db` が返すもの）**: リクエストごとに新しく作られる使い捨てのオブジェクト。トランザクションの境界管理・変更検知・同一性管理を担う。実際にクエリを発行する段になって、プールから接続を1本借りる

トランザクション（`BEGIN`〜`COMMIT`/`ROLLBACK`）は、その状態がPostgreSQL側の接続（バックエンドプロセス）のメモリ上にしか存在しないため、**開始から終了まで同じ接続に固定される必要がある**。これはプールの都合（速度目的）とは別の、正しさのための制約。

## `.env` のパスワードを壊して確認したこと

`docker compose up -d api`（`--build` なし）だけで、書き換えた `.env` の内容が反映された。環境変数はDockerfileの `ARG`/`ENV` で焼き込んでいるわけではなく、**コンテナが作られる瞬間に注入される**ため。compose は `.env` を含めた実効設定に差分があればコンテナを作り直し、新しいプロセスが新しい環境変数を読む。

DBアクセス時に `asyncpg.exceptions.InvalidPasswordError` が発生し、`unhandled_exception_handler` が拾って統一エラー形式（`{"error": {...}}`）の500を返した。ログにもJSON形式でスタックトレースが記録された。

## デバッガのアタッチが繋がらなかった話

`make debug` で起動した `debugpy` に VS Code からアタッチできず、`localhost` / `api` / `::1` を順に試してすべて失敗した。原因が1つではなく複数重なっていたため、実際に切り分けた過程を残す。

1. **接続元は `devtools` コンテナの中**: VS Codeは常に `devtools` に接続しているため（→ [step-02-devcontainer.md](step-02-devcontainer.md) のツールボックス方式）、デバッグアダプタのTCP接続も `devtools` の中から発生する。`localhost` はホスト(Mac)ではなく `devtools` 自身のループバックを指すため失敗していた
2. **`api` という名前が名前解決できなかった本当の理由**: `db` は `devtools hosts db` で正しく解決できるのに `api` だけ失敗するのは、ネットワークが違うからではなく、**`docker compose run` で作られる使い捨てコンテナには、サービス名（`api`）のDNS別名が付かない**ため（`docker compose up` で管理される `db`/`devtools` には付く）。`Makefile` の `docker compose run` に `--name api` を明示することで解決した
3. **ゾンビコンテナによる混乱**: `docker compose run --rm` は正常終了時のみコンテナを自動削除する。`Ctrl+C` や接続断で異常終了すると `--rm` が効かず、古いコンテナがポートを掴んだまま残り続けた。`docker compose stop/rm api` はこの使い捨てコンテナには効かず、コンテナ名を直接指定した `docker stop`/`docker rm` が必要だった

切り分けに使ったコマンド（`devtools` 側で `getent hosts <name>`、`timeout 2 bash -c "</dev/tcp/<host>/<port>"` によるDNSに依存しない到達確認、Mac側で `docker inspect ... NetworkSettings.Networks`）は、コンテナ間ネットワークの調査に汎用的に使える。

## ネットワークの仕組みの一般知識

Pydantic/SQLAlchemyの基礎知識、コルーチン・イベントループ、Dockerのcompose上のDNS解決の詳細は、ステップをまたいで参照する内容として以下に切り出した。

- → [topic-pydantic-basics.md](topic-pydantic-basics.md)
- → [topic-async-await.md](topic-async-await.md)
- → [topic-docker-networking.md](topic-docker-networking.md)

---

## 確認して分かったこと

- `curl localhost:8000/health/db` が `{"status":"ok"}` を返した
- ログが `{"timestamp": ..., "level": "INFO", "logger": "app", "message": "request completed", "request_id": ..., ...}` のJSON形式で出力された（uvicorn自身のアクセスログは別形式のまま残る。→ [topic-async-await.md](topic-async-await.md) の既知のギャップ）
- `.env` のパスワードを壊すと、統一エラー形式の500とJSON形式のスタックトレースが確認できた
- `make debug` → VS Codeでアタッチ → `health_db` のブレークポイントで実際に停止し、`Locals` に変数の値が見えた。`続行` で処理が再開され、正常なレスポンスが返った
- アタッチ中の `print()` は、`devtools` 側VS Codeの「デバッグコンソール」と、`make debug` を実行したMacのターミナル（コンテナの標準出力）の**両方**に出力される
