# Step 3: PostgreSQL を立てる

作成物: `compose.yaml`（`db` サービス）、`.env.example` / `.env`

---

## `postgres` 公式イメージの初期化は「初回だけ」

`POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` は、コンテナが**データディレクトリが空の状態で起動したときにだけ**読まれ、そのユーザー・パスワード・DB を作る初期化スクリプトが走る。

一度 `pgdata` ボリュームにデータができた後は、`.env` の値を書き換えて `docker compose up` し直しても**何も起きない**。これは Step 2 で見た「名前付きボリュームは初回作成時にしか初期化コピーが起こらない」（→ [topic-docker-volumes.md](topic-docker-volumes.md)）と同じ形の話。パスワードを変えたければボリュームを作り直すか、コンテナに入って `ALTER USER` する必要がある。

---

## データはコンテナではなくボリュームに乗る

`db` サービスを削除・再作成しても、`docker compose down` しても、`pgdata` という名前付きボリュームに実データが残る限りデータは消えない。消えるのは `down -v` を打ったときだけ。仕組みの詳細（3種類のマウント、永続性の一覧、確認コマンド）は [topic-docker-volumes.md](topic-docker-volumes.md) にまとめてある。今回はそこに PostgreSQL のデータが新しく乗った、という位置づけ。

---

## healthcheck を今のうちに入れておく理由

```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 5s
  timeout: 5s
  retries: 5
```

`pg_isready` は PostgreSQL 同梱のコマンドで、「接続を受け付けられる状態か」を確認する。プロセスが起動していても、初期化中で接続をまだ受け付けられない瞬間があるため、**「起動している」と「使える」は別の状態**として扱う必要がある。

今 `db` 単体では healthcheck の結果を使う相手がいないが、Step 4 で `api` を追加したときに

```yaml
depends_on:
  db:
    condition: service_healthy
```

という形で使う。これがないと「`db` コンテナは起動したが、まだ接続を受け付けていない」タイミングで `api` が先に繋ぎに行き、起動直後だけ失敗する事故が起きる。`docker compose ps` で `STATUS` に `healthy` と出るのがこの結果。

---

## `${POSTGRES_USER}` の展開元は `.env`

`compose.yaml` の `${POSTGRES_USER}` のような記法は、**`docker compose` コマンドを実行したディレクトリにある `.env` ファイル**から自動的に読み込んで展開される（`env_file:` で明示する仕組みとは別で、こちらは compose 自身の変数展開の話）。だから `compose.yaml` にはパスワードの値そのものは一切書かれていない。

## `.env` をコミットしない理由

`.env` にはパスワードそのものが入る。Git の履歴は基本的に消せない（force push や履歴書き換えをしない限り）ため、一度コミットすると過去のコミットを辿れば誰でも見える。

`.env.example` の方は値を持たない・持ってもダミー値のテンプレートなので、**リポジトリには「どんな変数が必要か」という形だけを残し、実際の値は各自の手元にしか置かない**という分担にしている。`.gitignore` は Step 1 の時点ですでに `.env` を無視し `.env.example` だけ例外にする形で用意済み（→ [step-01-git-init.md](step-01-git-init.md) の否定パターンの節）。

---

## 確認コマンドで見ていること

`docker compose up -d db` の `-d` は detach（バックグラウンド起動）。フォアグラウンドで実行すると、ログを見ている間ターミナルを占有してしまう。

`docker compose exec db psql -U todo -d todo -c '\l'` は、起動中の `db` コンテナの中で `psql`（PostgreSQL の CLI）を実行し、`\l` でデータベース一覧を見る。ここに `todo` が出ていれば初期化が成功している。

`down` の後に `up` してもデータが残っているのを確認するのは、「コンテナは使い捨てだがボリュームは別ライフサイクル」であることを実際に手で確かめるため。
