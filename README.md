# todo-fastapi

FastAPI + PostgreSQL の TODO API。アプリそのものより、次の3つを同時に満たす開発環境の構成を学ぶための学習用リポジトリ。

1. **ホストを汚さない**: ホストに Python も Node も入れない。開発ツールもアプリもすべてコンテナの中で動かす
2. **エディタが快適**: Dev Container に接続した VS Code で、git の差分表示・補完・波線・保存時の整形が効く
3. **本番とずれない**: 開発・テスト・本番のイメージが同じ Dockerfile と同じ `uv.lock` から作られる

機能は TODO の CRUD API のみ。フロントエンドと認証は、構成を作り直さずに後から足せるようにしてある（→ [将来の拡張](#将来の拡張)）。

## 構成の全体像

```
ホスト（Mac）
 ├─ VS Code ──接続──▶ devtools   開発ツールボックス（git / uv / pre-commit / Claude Code）
 └─ docker compose ─▶ api        アプリ本体（backend/Dockerfile の dev ステージ）:8000
                      db         PostgreSQL 17
```

- VS Code がつながるのは `devtools`。アプリは `api` で動く。役割を分けた理由は [ADR 0001](docs/adr/0001-devtools-toolbox.md) と [ADR 0003](docs/adr/0003-run-app-in-api-container.md)
- 3つのコンテナは compose の同じネットワーク上にあり、サービス名（`api`、`db`）で互いに到達できる

## 必要なもの（ホスト側）

- Docker Desktop
- VS Code と拡張機能「Dev Containers」（`ms-vscode-remote.remote-containers`）
- git
- make（macOS なら Xcode Command Line Tools に含まれる）

## セットアップ

以下はホストのターミナルで実行する。

リポジトリを取得する。

```bash
git clone <このリポジトリの URL> todo-fastapi
```

```bash
cd todo-fastapi
```

DB の接続情報を置く。`.env` はコミットしない（→ [step-03-postgres.md](docs/notes/step-03-postgres.md)）。

```bash
cp .env.example .env
```

VS Code でフォルダを開く。

```bash
code .
```

コマンドパレット（`Cmd+Shift+P`）から **Dev Containers: Reopen in Container** を実行する。初回は `devtools` と `api` のイメージのビルドが走り、`db` / `api` / `devtools` の3つが起動する。続けて `postCreateCommand` が一度だけ走り、次を行う。

- `backend/.venv` の作成（Pylance が import を解決するため）
- `pre-commit install`（`git commit` 時に検査が走るようにする）

起動したら、DB にテーブルを作る（ホストのターミナルで）。

```bash
make migrate
```

動作を確認する。

```bash
curl -s localhost:8000/health
```

```bash
curl -s localhost:8000/health/db
```

ブラウザで <http://localhost:8000/docs> を開くと Swagger UI から API を一通り操作できる。

## コマンドを実行する場所

**`devtools` には docker CLI が入っていない。** そのため `docker compose` と `make`（中身は `docker compose`）は**ホストのターミナル**で実行する。

| 実行する場所 | 使うもの |
|---|---|
| ホストのターミナル | `docker compose ...`、`make ...` |
| VS Code のターミナル（= `devtools` の中） | `git`、`uv add`、`pre-commit`、`psql -h db`、`curl api:8000/...` |

`devtools` から `api` を叩くときは `localhost` ではなくサービス名 `api` を使う（→ [topic-docker-networking.md](docs/notes/topic-docker-networking.md)）。

## よく使うコマンド

いずれもホストのターミナルで実行する。

### 起動・停止・ログ

Dev Container を開けば `db` と `api` も起動するが、VS Code を使わずに起動するときはこれ。

```bash
docker compose up -d
```

```bash
docker compose logs -f api
```

```bash
docker compose ps
```

```bash
docker compose down
```

`down -v` はボリュームも消す。DB のデータに加え、`devtools` の Claude Code の認証情報（`claude-config`）も消えるので注意。

### テスト・静的解析

| コマンド | 内容 |
|---|---|
| `make test` | unit + integration テスト（テスト用 DB `todo_test` を使う） |
| `make lint` | `ruff check` / `ruff format --check` / `mypy`。報告のみ |
| `make format` | ruff の自動修正と整形を適用する |

`git commit` 時にも pre-commit が ruff 等を走らせる。

### マイグレーション

モデルを変えたら、差分からマイグレーションファイルを生成する。生成結果は必ず目視で確認する（→ [topic-alembic-basics.md](docs/notes/topic-alembic-basics.md)）。

```bash
docker compose exec api alembic revision --autogenerate -m "変更内容"
```

適用する。

```bash
make migrate
```

### デバッグ

`--reload` 付きで常駐している `api` を止めてから、デバッガ待受の `api` を立てる。

```bash
docker compose stop api
```

```bash
make debug
```

VS Code の「実行とデバッグ」から **Python: api にアタッチ (docker)** を選んでアタッチする。終わったら `Ctrl+C` で止め、通常の `api` に戻す。

```bash
docker compose start api
```

### 依存パッケージの追加

`pyproject.toml` は手で編集せず `uv add` を使う（→ [topic-uv-dependency-management.md](docs/notes/topic-uv-dependency-management.md)）。これは VS Code のターミナル（`devtools`）で実行する。

```bash
uv add --project backend <パッケージ名>
```

開発時だけ使うものは `--dev` を付ける。`devtools` の `backend/.venv` はこれで更新されるが、`api` の `/opt/venv` はイメージの中にあるので、ホストで作り直す。

```bash
docker compose up -d --build api
```

### 本番相当の構成

`compose.prod.yaml` を重ねた本番相当のイメージ（uv もテストも無し、非 root、コードはイメージに焼いたもの）で動かす。ホストの 8000 番を使うので、開発の `api` は先に止める。

```bash
docker compose stop api
```

```bash
make prod-up
```

```bash
make prod-migrate
```

```bash
make prod-down
```

開発とはプロジェクト名（`-p todo-fastapi-prod`）を分けているので、イメージも DB のボリュームも開発とは別になる（→ [step-11-prod-image.md](docs/notes/step-11-prod-image.md)）。

## ディレクトリ構成

```
todo-fastapi/
├── .devcontainer/         devtools のイメージと Dev Container の接続設定
├── .vscode/               保存時の整形・Python の解決先・デバッガ設定（コミットする）
├── compose.yaml           共通の定義（db / api）
├── compose.override.yaml  開発の差分（devtools・バインドマウント・--reload）。自動で読まれる
├── compose.prod.yaml      本番相当の差分（target: prod）。-f で明示したときだけ読まれる
├── Makefile               開発コマンドの窓口。将来 CI からも同じターゲットを呼ぶ
├── .pre-commit-config.yaml
├── .editorconfig
├── .env.example           .env の雛形（.env 自体はコミットしない）
├── docs/
│   ├── plan.md            全 12 ステップの実装計画
│   ├── adr/               設計判断の記録
│   └── notes/             ステップごとの学習メモと、ステップをまたぐ一般知識
└── backend/
    ├── Dockerfile         base → builder / builder-dev → dev / prod の5段
    ├── pyproject.toml     依存と ruff / mypy / pytest の設定
    ├── uv.lock            依存の厳密なバージョン。dev も prod もここから作る
    ├── alembic.ini
    ├── migrations/        Alembic のマイグレーション
    ├── app/
    │   ├── main.py        アプリの組み立て、/health と /health/db
    │   ├── core/          設定（Settings）・構造化ログ・統一エラーレスポンス
    │   ├── db/            ORM の基底クラスと DB セッション
    │   ├── models/        テーブル定義（SQLAlchemy）
    │   ├── schemas/       API の入出力の型（Pydantic）
    │   ├── crud/          DB 操作
    │   └── api/           エンドポイント。/api/v1 以下
    └── tests/
        ├── unit/          DB を使わないテスト
        └── integration/   API を実際の DB まで通すテスト
```

`app/` は「エンドポイント（HTTP の関心事）→ crud（DB の関心事）→ models（テーブル定義）」の順に依存する。

## 学習用コメントの扱い

このリポジトリのコードには、日本語のコメントが実務より**かなり多く**入っている。学習のため、初めて出てきた記法やツールの挙動にもコメントを付けているため。

コメントは次の2種類が混ざっている。実務向けに整理するときは、前者だけを削る。

| 種類 | 例 | 実務では |
|---|---|---|
| 記法やツールの一般的な説明 | 「`--frozen` は `uv.lock` を再解決しない指定」「`run --rm` は終わったらコンテナを消す」 | 削る。公式ドキュメントで分かる |
| このリポジトリ固有の判断理由 | 「prod に `migrations/` を含めるのは別ジョブで流すため」 | 残す。コードからは読み取れない |

コメント末尾の `→ docs/notes/...` は詳しい説明の置き場所への参照。一般知識は `docs/notes/topic-*.md`、大きな設計判断は `docs/adr/` にまとめてあるので、コメントを削っても情報は失われない。

## ドキュメント

- [docs/plan.md](docs/plan.md): 全 12 ステップの実装計画
- [docs/adr/](docs/adr/README.md): 設計判断の記録（なぜこの構成なのか）
- [docs/notes/](docs/notes/README.md): 各ステップで扱った内容と、つまずきの記録

## 将来の拡張

### フロントエンドを追加する手順

構成は作り直さず、次を足す。

1. **`frontend/` を作る**: `backend/` と並べる。ビルドコンテキストはサービスごとに分けるので、フロントのファイルは `api` のイメージから見えない
2. **`devtools` に Node を用意する**: `devcontainer.json` の `features` に `ghcr.io/devcontainers/features/node:1` を置く。**Claude Code のために既に入っている**ので、必要ならバージョンを指定するだけでよい
3. **`node_modules` は名前付きボリュームに載せる**: `frontend/node_modules` をバインドマウントのままにすると、ホスト（macOS）とコンテナ（Linux）でネイティブバイナリが食い違い、ファイル数が多いぶん同期も遅い。`devtools` 側にもこのボリュームをマウントし、`postCreateCommand` で `npm ci` する（波線を出さないために、接続先の `devtools` にも `node_modules` が要る）。ボリュームは root 所有で作られるので、所有者に注意する（→ [topic-docker-volumes.md](docs/notes/topic-docker-volumes.md)）
4. **compose に `web` を足す**: 共通の定義を `compose.yaml` に、開発時の差分（バインドマウント・開発サーバー）を `compose.override.yaml` に、本番の差分を `compose.prod.yaml` に書く。本番はビルド済みの静的ファイルを配信する独立したイメージにする
5. **CORS を有効にする**: `backend/app/core/config.py` の `cors_allow_origins` に許可するオリジンを渡し、`main.py` で CORS ミドルウェアを登録する

### その他の TODO

- [ ] ユーザー認証: `models/user.py`、`api/v1/endpoints/auth.py`（JWT）、`deps.get_current_user`、`todos.user_id` の外部キー
- [ ] CI: GitHub Actions から `make lint` / `make test` を呼び、`--target prod` でイメージをビルドする
- [ ] E2E テスト: フロント追加時に Playwright を `tests/e2e/` に置く
- [ ] リモートリポジトリへの push と、Dependabot などによる依存の自動更新・脆弱性検査
