# Step 16: 本番相当の web と文書の更新

作成物: `docs/adr/0005-relay-api-via-rewrites.md`
変更: `frontend/Dockerfile`、`frontend/next.config.ts`、`compose.prod.yaml`、`Makefile`、`backend/app/core/config.py`、`README.md`

---

## 構成

```
ブラウザ ──► localhost:3000 ──► web（node server.js、非 root）──rewrites──► api:8000
```

- `compose.prod.yaml` に `web`（`target: prod`、ポート 3000）を足した。api と同じく `volumes:` も `command:` も書かない
- `make prod-up` の対象を全サービスにした。ホストの 3000 番を使うので、開発の web も先に止める（`docker compose stop api web`）

## Dockerfile

`base` → `deps` → `dev` / `builder` → `prod` の5段。backend と同じ形になった。

| 段 | やること | backend で対応する段 |
|---|---|---|
| `builder` | `deps` の `node_modules`（devDependencies 込み）とソースで `next build` | `builder`（`uv sync --no-dev`） |
| `prod` | ビルド結果だけを COPY して `node server.js` | `prod` |

### `output: "standalone"`

`next build` が、各ページが実際に読み込むファイルを `import` / `require` から静的に辿り、`.next/standalone/` に集める。中身は最小限の `server.js` と、実行に要る分だけの `node_modules`。これが無いと `next start` を使うことになり、`dependencies` を丸ごと入れる必要がある。backend の「`--no-dev` の venv だけを持っていく」より一段細かく、パッケージではなくファイル単位で絞っている。

`builder` で devDependencies ごと使うのは、`next build` が TypeScript の型検査と Tailwind の CSS 生成も行うため。

### `public/` と `.next/static/` を別に COPY する

standalone には含まれない。ブラウザに配るだけのファイルなので、本来は CDN（配信専用のサーバー群）に置き、Node のサーバーを通さない想定だから。今回は CDN を使わないので、所定の場所にコピーして `server.js` に配らせる。

### `ENV HOSTNAME=0.0.0.0`

`server.js` は環境変数 `HOSTNAME` のアドレスで待ち受ける（未設定なら `0.0.0.0`）。Docker はすべてのコンテナの `HOSTNAME` にコンテナ ID を自動で入れるので、上書きしないとそのアドレスでしか待たず、コンテナ内の `localhost` から繋がらなくなる。

### 権限: コードは root 所有、書けるのは `.next/cache` だけ

Next.js 公式の例は、コピーしたファイルを `--chown` ですべて実行ユーザーの持ち物にしている。ここでは backend の prod に揃え、コードは root が所有し、`node` ユーザーは読むだけにした。書き込みを許すのは、Next.js が実行中に使うキャッシュの置き場 `.next/cache` だけ。

## 中継先はビルド時に確定する

rewrites の転送先 `http://api:8000` は `next build` の時点で評価され、ビルド結果に書き込まれる。prod イメージには `next.config.ts` も TypeScript も無いが、`server.js` は書き込み済みの設定を読むので中継が動く。

Step 11 のノートに「設定値は環境変数で渡すので、リビルドせずに変えられる」と書いたが、rewrites はその例外で、起動時の環境変数では変えられない（→ [topic-docker-build-and-run.md](topic-docker-build-and-run.md) の「アプリの設定ファイルも『ビルド時に評価される』ことがある」）。

## CD と ISR は別の話

CD を実現するには「ページを実行中に作り直す機能」（ISR）が必要なのでは、という疑問が出たので整理した。

| | 何を | いつ・誰が変える |
|---|---|---|
| **CD**（継続的デリバリー／デプロイ） | **コード**の変更を本番に届ける | コミットのたびに CI が新しいイメージを作り、古いコンテナと差し替える |
| **ISR**（Incremental Static Regeneration） | **データ**の変化をページに反映する | 実行中の Next.js が、一定時間ごとなどにページを作り直してディスクに保存する |

CD は Step 11 で扱ったイミュータブルなデプロイ（→ [step-11-prod-image.md](step-11-prod-image.md)）そのもので、動いているコンテナの中身は一切書き換えない。新しいイメージの中では `next build` が走り直すので、ページも作り直された状態で届く。ISR は要らない。

そもそもこの画面は、一覧をブラウザ側の `fetch` で取りに行く（→ [step-15-todo-page.md](step-15-todo-page.md)）。サーバーが作る HTML にデータが入っていないので、データが変わってもページを作り直す必要が無い。

ISR を使うことになった場合、書き込み権限を広げる変更自体は1行で済む。ただし、コンテナを複数台で動かすとキャッシュが台ごとにばらばらになるので、共有のキャッシュ置き場（Redis など）を用意する話になる。使う予定が無いのに権限だけ広げると、アプリが乗っ取られたときに書き換えられる範囲が増えるだけなので、今は対応しない。

## イメージの中身とサイズ

`exec web ls -a` の結果は `.next  node_modules  package.json  public  server.js` だけ。`app/` や `components/` の `.tsx` は無い。

`exec web ls node_modules` の結果:

```
@img  @next  @swc  client-only  detect-libc  next  react  react-dom  semver  sharp  styled-jsx
```

`typescript`・`eslint`・`tailwindcss`・`prettier` などの devDependencies は無い。`sharp`（と、そのネイティブバイナリの `@img`）は、Next.js の画像最適化（`next/image`）が使う画像処理ライブラリで、Next.js がそれを読み込むコードを持っているので辿られて入る。

| イメージ | ディスク使用量 | コンテンツサイズ |
|---|---|---|
| `todo-fastapi-web`（dev） | 946MB | 192MB |
| `todo-fastapi-prod-web`（prod） | 402MB | 93.1MB |

どちらも `base`（`node:24-slim`）を共有しており、差の約 540MB は dev にだけある `node_modules` の残り（devDependencies と、standalone が辿らなかったパッケージ内のファイル）。

## 症状と対処

### `make prod-migrate` で `Running upgrade` が出なかった

prod の DB ボリュームは Step 11 の確認で既にマイグレーション済みだったため。適用するものが無いときは接続のログだけが出る。

## 確認したこと

- `make prod-up` で db / api / web の3つが揃って立つ
- `curl -i localhost:3000/api/v1/todos` に `server: uvicorn` と `x-request-id` の付いた API のレスポンスが返る
- ブラウザで `localhost:3000` から CRUD を一通り操作できる
- `exec web whoami` は `node`
- 中身とサイズは上のとおり
