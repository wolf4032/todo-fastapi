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

## トピックノート

| トピック | 内容 |
|---|---|
| [Docker のボリュームと権限](topic-docker-volumes.md) | マウントの3種類、永続性、名前付きボリュームの初回作成時のコピー、UID による権限、トラブルシュート |
| [ビルド時に決まること・実行時に決まること](topic-docker-build-and-run.md) | `RUN` と `CMD` のタイミングの違い、CMD とメインプロセス、compose の `command:` との関係、healthcheck の汎用的な仕組み、`docker compose up -d` |
