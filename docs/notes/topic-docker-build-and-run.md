# トピック: ビルド時に決まること・実行時に決まること

Step 4 で `RUN` と `CMD` の違い、`depends_on: condition: service_healthy` の仕組みを整理したもの。
ステップ横断の一般知識なので独立したノートにしている。

---

## `docker build` と `docker run` は別のタイミング

| | いつ動くか | 何をするか |
|---|---|---|
| `RUN` | `docker build` の最中、その場で即座に | コマンドを実行し、結果（ファイルの変化）をイメージの層として焼き込む |
| `CMD` | `docker build` では**実行されない**。コンテナを起動する**たびに** | 「他に指定が無ければこれを実行する」というイメージのメタデータを書くだけ |

同じイメージから100回コンテナを起動すれば `CMD` は100回実行される。ビルドは1回しかしていなくても、である。`ARG` のスコープが「`docker build` の実行中のみ」なのも同じ理由（→ [step-02-devcontainer.md](step-02-devcontainer.md) の「`ARG` と `ENV` の違い」）。

### CMD は「コンテナのメインプロセス」を1つ指すもの

Docker のコンテナは PID 1（メインプロセス）を1つ持ち、そのプロセスが終了するとコンテナ自体も終了する、という設計になっている。`CMD` に複数コマンドを書くこと自体は構文上可能（`&&` で繋ぐ、あるいは同じステージに `CMD` を複数書く）だが、

- 同じステージに `CMD` を複数書いても**最後の1つだけ**が有効（後勝ち）
- `command1 && command2` は「`command1` が正常終了したら `command2`」の意味。`command1` が uvicorn のような常駐サーバーだと `command2` には永遠に到達しない

なので実務では基本的に「1ステージ・1つの常駐プロセス」として設計する。

---

## compose の `command:` は `CMD` をまるごと置き換える

`command:` は **追記ではなく置換**。イメージに `CMD` が定義されていなくても `command:` 単体で機能する（`ENTRYPOINT` を使っていない構成なら特に）。

このリポジトリでの使い分け（→ [step-04-backend-container.md](step-04-backend-container.md)）:

- `backend/Dockerfile` の `dev` ステージの `CMD` … `--reload` 無しの素の既定値。override を書き忘れても最低限動くための保険
- `compose.override.yaml` の `api.command` … 実際に使う `--reload` 付きコマンド

逆に言うと、**override 側で `command:` を書かない環境では `CMD` が必須**になる。`compose.prod.yaml`（Step 11）はここに `command:` を書かない想定なので、`prod` ステージの `CMD` が無いと本番は起動できない。

---

## healthcheck は「コンテナ内でコマンドを定期実行し、終了コードで判定する」だけの汎用機構

Docker は対象がデータベースなのか HTTP サーバーなのか一切知らない。すべて「シェルコマンドを一定間隔で実行し、終了コード 0 なら成功、それ以外なら失敗」という共通ルールで判定しているだけで、**「何を確認すれば健康と言えるか」は毎回こちらが書く**。

| 対象 | よく使われる確認コマンドの例 |
|---|---|
| PostgreSQL | `pg_isready -U ... -d ...` |
| MySQL | `mysqladmin ping -h localhost` |
| Redis | `redis-cli ping` |
| HTTP サーバー | `curl -f http://localhost:PORT/health \|\| exit 1` |

`db` サービスでの実例は → [step-03-postgres.md](step-03-postgres.md)。

### `depends_on: condition: service_healthy` はゲートであって、healthcheck の起動トリガーではない

- healthcheck を実際に**動かし続けている**のは Docker デーモン自身。`healthcheck:` が定義されているサービスは、`depends_on` の有無に関わらず起動中ずっと定期実行される（`docker compose ps` の `STATUS` に出る）
- `condition: service_healthy` は「その結果が `healthy` になるまで、依存する側の起動を待つ」という**起動順序の制御**のみを行う
- 対象サービスに `healthcheck:` が無ければ `service_healthy` は参照先が無くエラーになる
- **起動時だけの話**。起動後に依存先が `unhealthy` になっても、Compose が依存する側を自動で止めることはしない（継続的な監視・再起動が要るなら Kubernetes の readiness probe のような別の仕組みになる）

---

## `docker compose up -d`

`-d` は **detach**（切り離す）の略。

- 無指定の `up` はコンテナ起動後もターミナルに張り付いてログを流し続ける（`Ctrl+C` まで専有）
- `-d` を付けると起動だけしてすぐプロンプトを返す。ログは後から `docker compose logs -f <service>` で追える

**ビルドが走るかどうかは `-d` と無関係。** `up` は対象イメージが存在しなければ自動でビルドするが、**一度イメージができた後は `Dockerfile` を直しても `up` だけでは自動再ビルドされない**。変更を反映するには `docker compose build <service>` または `docker compose up -d --build <service>` が必要。
