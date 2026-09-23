# Step 11: 本番相当イメージの確認

作成物: `compose.prod.yaml`、`Makefile`（`prod-up` / `prod-migrate` / `prod-down`）

`backend/Dockerfile` の `prod` ステージは Step 4 で作成済み。このステップでは、それを本番相当の構成で起動し、中身が想定どおりかを実際に確かめた。

---

## `-f` を付けると `compose.override.yaml` は読まれない

`docker compose` は `-f` が無いと `compose.yaml` と `compose.override.yaml` を自動で探してマージする。`-f` を1つでも書くと自動探索は止まり、指定したファイルだけが読まれる。

```
$ docker compose config --services
db
api
devtools
$ docker compose -f compose.yaml -f compose.prod.yaml config --services
db
api
```

`compose.prod.yaml` に書いたのは `target: prod` とポート公開だけ。`volumes:` と `command:` を**書かないこと**に意味がある。

- バインドマウントが無い → 動くのはビルド時に `COPY` で焼かれたコードだけ。手元を編集しても反映されず、反映するにはリビルドが要る（`prod-up` に `--build` を付けている理由）
- `command:` が無い → Dockerfile の `CMD`（`--reload` なし）がそのまま使われる

## プロジェクト名を `-p todo-fastapi-prod` で分けた理由

compose はイメージ・コンテナ・ボリュームに `<プロジェクト名>-<サービス名>` で名前を付ける。開発と同じプロジェクト名のまま prod をビルドすると、次のことが起きる。

- prod イメージが `todo-fastapi-api` のタグを上書きする。その後の開発側の `docker compose up` は「イメージがある」と判断して再ビルドしないため、**pytest の無いイメージで開発環境が起動**する
- DB ボリューム `pgdata` を共有し、本番相当の確認が開発データに触れる

本物の本番は別マシンで動くので、この衝突はローカル特有の問題。そのため `compose.prod.yaml` ではなく Makefile 側で指定した。ホストの 8000 番は開発の api と取り合うので、`make debug` と同じく先に `docker compose stop api` する。

## マイグレーションは別ジョブで流す

起動時に `alembic upgrade head` を流す方式は採らない。

- api を複数台に増やすと、全台が同時にマイグレーションを流して競合する
- マイグレーションが失敗するとアプリが起動ループに入り、「スキーマ変更の失敗」と「アプリの不調」の区別がつかない

`make prod-migrate` は `run --rm` で**同じイメージからマイグレーション専用のコンテナを1つ立て、終わったら消す**。prod イメージに `alembic.ini` と `migrations/` を含めているのはこのため（→ [step-06-alembic.md](step-06-alembic.md)）。

実際、prod-up 直後の空の DB では `/health` は ok でも一覧 API は 500 になった。`prod-migrate` の後に `{"items":[],...}` に変わった。

## 本番イメージの中身の確認結果

| 確認 | 結果 |
|---|---|
| `whoami` | `app`（非 root） |
| `uv` / `pytest` / `ruff` | 3つとも not found |
| `ls /app` | `alembic.ini  app  migrations`（`tests` 無し） |

| イメージ | ディスク使用量 | コンテンツサイズ |
|---|---|---|
| `todo-fastapi-api`（dev） | 456MB | 93.3MB |
| `todo-fastapi-prod-api`（prod） | 287MB | 60.2MB |

どちらも `base`（`python:3.13-slim`）を共有しており、差の約 170MB は dev 依存（pytest / ruff / mypy / debugpy 等）と uv 由来。コンテンツサイズは圧縮済みのレイヤの合計で、レジストリとの転送量に効く方。

## 本番イメージに pytest（とテスト）が入っていると何がまずいか

- **テストが本番の DB サーバーに触れる**: `conftest.py` は接続先の DB 名を `todo_test` に差し替えるだけで、ホスト・認証情報は環境変数のまま使う。本番コンテナで誤って `pytest` を実行すると、本番の DB サーバー上で `CREATE DATABASE todo_test` とマイグレーションが走る。テスト用の分離は「開発環境で動かす」前提でしか成り立たない
- **攻撃対象領域が広がる**: パッケージが増えるほど脆弱性（CVE）の追跡・更新対象が増え、脆弱性スキャナの指摘もその分増える。uv があれば、侵入者がネットワーク越しに好きなパッケージを入れる手段も与える
- **サイズ**: 上の表のとおり。pull やデプロイが遅くなる

## 本番のファイルは直接書き換えない

本番のコードはイメージのビルド時点で固定され、変更は「新しいイメージを作って差し替える」ことでしか入れない（イミュータブルなデプロイ）。

- 障害時の切り戻しも、ファイルの修正ではなく**前のバージョンのイメージに戻す**ことで行う。イメージにタグ（バージョン）が付いていれば、切り戻しはタグの切り替えだけで済む
- コンテナ内を直接書き換えても、再起動・台数追加・再デプロイのたびに消えるうえ、git に記録も残らない
- この prod イメージでは `COPY` したファイルの所有者が root で、実行ユーザーの `app` には書き込み権限が無い。非 root 実行はこの誤操作も防ぐ

例外として、**データ**（DB の中身）の修正は本番に直接当てることがある。その場合も手作業ではなく、レビュー済みの SQL やスクリプトとして実行するのが普通。設定値は環境変数で渡すので、リビルドせずに変えられる。

## つまずき: 「見つからないこと」の確認が Docker のエラー表示になった

`exec api which uv pytest ruff` は出力が空で、正しく「3つとも無い」ことを示していた。ところが Docker Desktop が `Debug this Compose error with Gordon` と表示した。

`which` は1つでも見つからないと終了コード 1 を返す。`docker compose exec` は中のコマンドの終了コードをそのまま返し、Docker Desktop は 0 以外を失敗とみなしてこの案内を出す。**期待する結果が「非 0 終了」になる確認コマンドは、成功しても見た目がエラーになる**。

結果を明示して終了コードを 0 にする形に書き換えた。

```
sh -c 'for c in uv pytest ruff; do command -v "$c" || echo "$c: not found"; done'
```
