# todo-fastapi

FastAPI + PostgreSQL + Next.js の TODO アプリ。アプリそのものより、次の3つを同時に満たす開発環境の構成を学ぶための学習用リポジトリ。

1. **ホストを汚さない**: ホストに Python も Node も入れない。開発ツールもアプリもすべてコンテナの中で動かす
2. **エディタが快適**: Dev Container に接続した VS Code で、git の差分表示・補完・波線・保存時の整形が効く
3. **本番とずれない**: 開発・テスト・本番のイメージが同じ Dockerfile と同じ lock ファイル（`uv.lock` / `package-lock.json`）から作られる

機能は TODO の CRUD API と、それを操作する画面1枚（一覧・追加・完了切り替え・削除）。フロントエンドは、API だけの構成を作り直さずに後から足した（→ [フロントエンドの追加](#フロントエンドの追加)）。

## 構成の全体像

```
ホスト（Mac）
 ├─ VS Code ──接続──▶ devtools   開発ツールボックス（git / uv / npm / pre-commit / Claude Code）
 ├─ docker compose ─▶ web        画面（frontend/Dockerfile の dev ステージ、next dev）:3000
 │                    api        API（backend/Dockerfile の dev ステージ）:8000
 │                    db         PostgreSQL 17
 └─ ブラウザ ──▶ localhost:3000 ──▶ web ──/api/... を中継──▶ api
```

- VS Code がつながるのは `devtools`。アプリは `web` と `api` で動く。役割を分けた理由は [ADR 0001](docs/adr/0001-devtools-toolbox.md) と [ADR 0003](docs/adr/0003-run-app-in-api-container.md)
- 4つのコンテナは compose の同じネットワーク上にあり、サービス名（`web`、`api`、`db`）で互いに到達できる
- ブラウザは `localhost:3000` にだけリクエストを送り、`/api/...` は `web` が `api` へ中継する。ブラウザから見て同一オリジンになるので CORS は使わない（→ [ADR 0005](docs/adr/0005-relay-api-via-rewrites.md)）

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

コマンドパレット（`Cmd+Shift+P`）から **Dev Containers: Reopen in Container** を実行する。初回は `devtools` / `api` / `web` のイメージのビルドが走り、`db` / `api` / `web` / `devtools` の4つが起動する。続けて `postCreateCommand` が一度だけ走り、次を行う。

- `backend/.venv` の作成（Pylance が import を解決するため）
- `pre-commit install`（`git commit` 時に検査が走るようにする）
- `frontend/node_modules` の作成（`npm ci`。TypeScript の補完と ESLint のため）

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

ブラウザで <http://localhost:3000> を開くと TODO の画面が出る。<http://localhost:8000/docs> の Swagger UI からも API を直接操作できる。

## コマンドを実行する場所

**`devtools` には docker CLI が入っていない。** そのため `docker compose` と `make`（中身は `docker compose`）は**ホストのターミナル**で実行する。

| 実行する場所 | 使うもの |
|---|---|
| ホストのターミナル | `docker compose ...`、`make ...` |
| VS Code のターミナル（= `devtools` の中） | `git`、`uv add`、`npm ... --prefix frontend`、`pre-commit`、`psql -h db`、`curl api:8000/...` |

`devtools` から `api` や `web` を叩くときは `localhost` ではなくサービス名（`api:8000`、`web:3000`）を使う（→ [topic-docker-networking.md](docs/notes/topic-docker-networking.md)）。

## よく使うコマンド

いずれもホストのターミナルで実行する。

### 起動・停止・ログ

Dev Container を開けば `db` / `api` / `web` も起動するが、VS Code を使わずに起動するときはこれ。

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
| `make lint` | api で `ruff check` / `ruff format --check` / `mypy`、web で ESLint と型検査。報告のみ |
| `make format` | ruff の自動修正と整形を適用する |

`git commit` 時にも pre-commit が ruff 等を走らせる。GitHub に push すると、CI（`.github/workflows/ci.yml`）が同じ `make lint` / `make test` と prod イメージのビルドを走らせる。

編集中にフロントエンドだけを手早く検査したいときは、VS Code のターミナル（`devtools`）でも実行できる。

```bash
npm run lint --prefix frontend
```

```bash
npm run typecheck --prefix frontend
```

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

フロントエンドの依存は `package.json` を手で編集せず `npm install` を使う（VS Code のターミナルで）。

```bash
npm install --prefix frontend <パッケージ名>
```

`web` の `node_modules` はイメージと匿名ボリュームにあるので、ホストで作り直す。`-V` を付けないと古い匿名ボリュームが引き継がれ、新しい依存が見えない（→ [step-14-web-container.md](docs/notes/step-14-web-container.md)）。

```bash
docker compose up -d --build -V web
```

### 本番相当の構成

`compose.prod.yaml` を重ねた本番相当のイメージで動かす。api は uv もテストも無し、web は Next.js の standalone 出力で devDependencies もソースの `.tsx` も無し。どちらも非 root で、コードはイメージに焼いたもの。ホストの 8000 番と 3000 番を使うので、開発の `api` と `web` は先に止める。

```bash
docker compose stop api web
```

```bash
make prod-up
```

```bash
make prod-migrate
```

ブラウザで <http://localhost:3000> を開いて確認する。終わったら止めて、開発の構成に戻す。

```bash
make prod-down
```

```bash
docker compose start api web
```

開発とはプロジェクト名（`-p todo-fastapi-prod`）を分けているので、イメージも DB のボリュームも開発とは別になる（→ [step-11-prod-image.md](docs/notes/step-11-prod-image.md)）。

## ディレクトリ構成

```
todo-fastapi/
├── .devcontainer/         devtools のイメージと Dev Container の接続設定
├── .github/workflows/     CI の定義。push のたびに make lint / make test と prod のビルドを走らせる
├── .vscode/               保存時の整形・Python の解決先・デバッガ設定（コミットする）
├── compose.yaml           共通の定義（db / api / web）
├── compose.override.yaml  開発の差分（devtools・バインドマウント・--reload）。自動で読まれる
├── compose.prod.yaml      本番相当の差分（target: prod）。-f で明示したときだけ読まれる
├── Makefile               開発コマンドの窓口。将来 CI からも同じターゲットを呼ぶ
├── .pre-commit-config.yaml
├── .editorconfig
├── .env.example           .env の雛形（.env 自体はコミットしない）
├── docs/
│   ├── plan.md            全 16 ステップの実装計画
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
└── frontend/
    ├── Dockerfile         base → deps → dev / builder → prod の5段
    ├── package.json       依存と npm スクリプト（lint / typecheck）
    ├── package-lock.json  依存の厳密なバージョン。dev も prod もここから作る
    ├── next.config.ts     /api/... の中継（rewrites）と standalone 出力
    ├── app/               ページ（App Router）。page.tsx が TODO 画面
    ├── components/        Client Component（todo-app.tsx）
    └── lib/               API の型と、fetch を包んだ API クライアント
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

- [docs/plan.md](docs/plan.md): 全 16 ステップの実装計画（Step 13〜16 はフロントエンドの追加）
- [docs/adr/](docs/adr/README.md): 設計判断の記録（なぜこの構成なのか）
- [docs/notes/](docs/notes/README.md): 各ステップで扱った内容と、つまずきの記録

## フロントエンドの追加

API だけの構成（Step 12 まで）に、構成を作り直さず次を足した（Step 13〜16）。

1. **`frontend/` を `backend/` と並べた**: ビルドコンテキストはサービスごとに分けているので、フロントのファイルは `api` のイメージから見えない
2. **`devtools` の Node をそのまま使った**: Claude Code のために入れていた Node の Feature で足りた
3. **`node_modules` はコンテナごとに別に持つ**: `devtools` は名前付きボリューム（`postCreateCommand` の `npm ci`）、`web` はイメージと匿名ボリューム。backend の `backend/.venv` と `/opt/venv` と同じ構図で、どちらも同じ `package-lock.json` から作る（→ [step-13-nextjs-scaffold.md](docs/notes/step-13-nextjs-scaffold.md)）
4. **compose に `web` を足した**: 共通の定義は `compose.yaml`、バインドマウントと `next dev` は `compose.override.yaml`、standalone 出力の prod イメージは `compose.prod.yaml`（→ [step-14-web-container.md](docs/notes/step-14-web-container.md)、[step-16-prod-web.md](docs/notes/step-16-prod-web.md)）
5. **CORS ではなく中継にした**: Next.js の rewrites で `/api/...` を `api` へ転送し、同一オリジンにした（→ [ADR 0005](docs/adr/0005-relay-api-via-rewrites.md)）

## 将来の拡張

- [ ] ユーザー認証: `models/user.py`、`api/v1/endpoints/auth.py`（JWT）、`deps.get_current_user`、`todos.user_id` の外部キー
- [ ] CD: CI でビルドした prod イメージをレジストリに置き、本番のコンテナを新しいイメージに差し替える
- [ ] E2E テスト: Playwright を `tests/e2e/` に置く
- [ ] リモートリポジトリへの push と、Dependabot などによる依存の自動更新・脆弱性検査
