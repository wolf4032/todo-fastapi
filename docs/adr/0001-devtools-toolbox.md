# 0001. 開発環境にツールボックス方式（`devtools`）を採用する

- ステータス: 採用
- 日付: 2026-08-17（Step 2）

## 背景

満たしたい要件は3つある。

1. ホスト PC に Python も Node も入れない
2. VS Code で git の差分表示が効き、import に誤った波線が出ず、保存時にフォーマッタが走る。これを**将来フロントエンドを足した後も言語をまたいで**保つ
3. 開発ツールを本番イメージに混ぜない

制約として、VS Code の Dev Container は **1ウィンドウにつき1コンテナにしか接続できない**。拡張機能（Pylance など）は接続先コンテナの中で動くので、補完や波線の判定に使えるのは接続先に存在する言語環境と依存パッケージだけになる。

## 決定

VS Code の接続先として、アプリの実行コンテナとは別に**開発専用のツールボックス `devtools`** を用意する。

- イメージは `.devcontainer/Dockerfile`（git / make / uv / pre-commit / psql）。アプリの `backend/Dockerfile` とは完全に別系統にする
- 将来の Node は Dev Container Features（`ghcr.io/devcontainers/features/node:1`）で `devtools` に足す。現在も Claude Code のために既に入っている
- Pylance に読ませる Python 依存は、`postCreateCommand` の `uv sync --frozen --project backend` で `backend/.venv` に作る。`api` コンテナの `/opt/venv` と同じ `uv.lock` 由来なので中身は一致する

## 却下した案

- **サービスごとに dev コンテナを分け、VS Code をアプリのコンテナに直接接続する**（`api` の dev ステージに接続する等）: 1言語だけなら最も素直だが、バックエンドのコンテナに接続したままフロントのコードを開くと、そこには TypeScript も `node_modules` も無く波線が全面に出る。要件2を満たせない。また、エディタ用の拡張機能やツールがアプリのイメージ側に入り込む
- **言語ごとに VS Code のウィンドウを分けて、それぞれ別コンテナに接続する**: 動きはするが、1つのリポジトリを横断して検索・編集・コミットする体験が分断される
- **ホストに言語環境を入れる**: 要件1に反する
- **Node をイメージに `COPY --from=node` で移植する**: 共有ライブラリ（`libexpat.so.1` 等）・`PATH`・バージョン入りのディレクトリ名を手で合わせる必要があり、バージョン更新のたびに壊れやすい。ツールボックス用途では Features が素直

## 結果

- 言語をまたいでも接続先は1つのまま。フロントを足すときは `devtools` に Node と `node_modules` を揃えるだけで済む
- 開発ツールは本番イメージから完全に切り離される
- 引き受けたこと:
  - Python の依存が `api` の `/opt/venv` と `devtools` の `backend/.venv` の2か所に存在する。同じ `uv.lock` から作ることで一致を保つが、依存を変えたら両方を作り直す必要がある（→ [topic-uv-dependency-management.md](../notes/topic-uv-dependency-management.md)）
  - `devtools` には docker CLI も Docker ソケットも渡していない。そのため `docker compose` / `make` はホスト側のターミナルで実行する。ソケットを渡せば `devtools` から操作できるようになるが、コンテナの中からホストの Docker を丸ごと操作できる状態になる
  - `devtools` から `api` へは `localhost` ではなくサービス名で到達する（→ [topic-docker-networking.md](../notes/topic-docker-networking.md)）

詳細: [step-02-devcontainer.md](../notes/step-02-devcontainer.md)、[step-10-lint-format-editor.md](../notes/step-10-lint-format-editor.md)
