# 0002. 1つの Dockerfile をマルチステージにし、依存は venv に固めて移送する

- ステータス: 採用
- 日付: 2026-08-19（Step 4）

## 背景

開発・テスト・CI・本番のあいだで実行環境がずれると、「手元では動いた」がデプロイ後に崩れる。一方で、本番イメージには pytest や ruff、uv のような開発・ビルド用の道具を入れたくない（サイズ、脆弱性の追跡対象、テスト用コードが本番で動く経路）。

「環境を揃えたい」と「中身を変えたい」を両立させる必要がある。

## 決定

`backend/Dockerfile` を1つだけ置き、次の5段のマルチステージにする。

```
base         python:3.13-slim。開発も本番もここから派生する
builder      uv sync --frozen --no-dev → /opt/venv
builder-dev  uv sync --frozen          → /opt/venv（dev 依存込み）
dev          builder-dev の venv を COPY。コードはバインドマウント
prod         builder の venv と app/・migrations/ を COPY。uv もテストも無し、非 root
```

- 依存は `UV_PROJECT_ENVIRONMENT=/opt/venv` で venv に固め、ステージ間は `COPY --from=builder /opt/venv /opt/venv` の1行で移す
- dev も prod も**同じ `uv.lock` を `--frozen` で使う**
- `tests/` を本番から外すのは `.dockerignore` ではなく、prod ステージで必要なものだけを `COPY` することで行う

## 却下した案

- **`Dockerfile.dev` と `Dockerfile.prod` を別々に書く**: 土台（Python のバージョン、OS パッケージ、環境変数）を二重に管理することになり、片方だけ更新されてずれていく。マルチステージなら `base` を共有するので構造的にずれない
- **1段のイメージに開発用の依存もすべて入れ、本番もそれを使う**: 本番に pytest・ruff・uv が入る
- **venv を使わずシステムの Python に入れる**: ライブラリは `site-packages`、実行スクリプト（`uvicorn` / `alembic`）は `/usr/local/bin` と散らばり、ステージ間で移すための `COPY` が複数行になって壊れやすい。venv を使うのは隔離のためではなく移送のため
- **本番イメージにも uv を入れて `uv run` で起動する**: 再現性はビルド時の `uv.lock` + `--frozen` で担保済みなので、実行時に uv が居ても得るものが無い。サイズと攻撃対象領域だけが増える
- **`.dockerignore` に `tests/` を書く**: `.dockerignore` はビルドコンテキスト全体に効き、ステージごとに切り替えられない。dev ステージからも消えてしまう

## 結果

- 「テストが通った依存関係 = 本番の依存関係」と言い切れる
- Step 11 の実測で、prod は dev より約 170MB 小さく、`uv` / `pytest` / `ruff` / `tests/` がいずれも存在しないことを確認した
- 引き受けたこと:
  - dev ステージはコードを `COPY` しないので、バインドマウントが無いと動かない（開発専用のステージであることの裏返し）
  - 本番でマイグレーションを別ジョブとして流すため、prod には `alembic.ini` と `migrations/` も含めている

詳細: [step-04-backend-container.md](../notes/step-04-backend-container.md)、[step-11-prod-image.md](../notes/step-11-prod-image.md)
