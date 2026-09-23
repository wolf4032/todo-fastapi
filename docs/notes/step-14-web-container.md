# Step 14: web コンテナと API への中継

作成物: `frontend/Dockerfile`、`frontend/.dockerignore`
変更: `compose.yaml`、`compose.override.yaml`、`frontend/next.config.ts`、`Makefile`

---

## 構成

```
ブラウザ ──► localhost:3000 ──► web（next dev）──rewrites──► api:8000
```

- **`web` は `api` と同じ分け方**: `compose.yaml` にはコンテキストと `depends_on` だけを書き、`target: dev`・バインドマウント・ポートは `compose.override.yaml` に書く
- **rewrites**: `/api/:path*` を `http://api:8000/api/:path*` へ転送する。ブラウザから見ると同一オリジンなので CORS が要らない（→ [topic-same-origin-and-cors.md](topic-same-origin-and-cors.md)）。`:path*` は「`/` を含む残りのパス全部」に一致し、同じ名前で転送先に埋め込める

## Dockerfile

`base` → `deps` → `dev` の3段構成。backend と対応させている。

| frontend | backend | 役割 |
|---|---|---|
| `node:24-slim` | `python:3.13-slim` | devtools と同じメジャー版。SWC などのネイティブバイナリが glibc 前提なので Debian 系 |
| `deps`（`npm ci`） | `builder-dev`（`uv sync --frozen`） | lock ファイルだけを先に COPY して依存の層をキャッシュする |
| `ENV PATH=/app/node_modules/.bin:$PATH` | `ENV PATH=/opt/venv/bin:$PATH` | インストールしたコマンドを直接呼べるようにする |

- **`CMD ["next", "dev"]`**: `npm run dev` にしなかったのは、npm を挟むと停止シグナル（SIGTERM）が next に届かず、`docker compose stop` が 10 秒待ってから強制終了になるため
- **override に `command:` を書いていない**: dev ステージの CMD がすでに `next dev` なので、上書きする中身が無い（api は `--reload` を足すために書いている）
- **builder / prod は Step 16 に回した**: prod には `output: "standalone"` が必要で、Step 16 の作業と切り離せないため。それまでは `compose.yaml` の `web` を prod 構成で立てるとコードの無い dev ステージになってしまうので、`make prod-up` の対象を `api` に絞った

## `node_modules` と `.next` を匿名ボリュームに載せる

```yaml
- ./frontend:/app
- /app/node_modules
- /app/.next
```

`/app` のバインドマウントがイメージ内の `node_modules` を隠すので、匿名ボリュームを重ねてイメージ側の中身を見せる。`.next` は next dev のビルドキャッシュで、ホストと同期させると遅く、ホストに残す理由も無いので同じく載せた。

### 依存を変えたときの作り直し

```bash
docker compose up -d --build -V web
```

`--build` だけでは足りない。compose は再作成時に前の匿名ボリュームを引き継ぐので、新しいイメージの `node_modules` が古いボリュームの下に隠れたままになる。`-V` で匿名ボリュームも作り直す（→ [topic-docker-volumes.md](topic-docker-volumes.md)）。

devtools 側（名前付きボリューム）は、これまでどおり `npm ci --prefix frontend` で入れ直す。

## 症状と対処

### 雛形ページで hydration mismatch のエラーが出た

差分に `data-darkreader-*` という属性が出ていた。ブラウザ拡張の Dark Reader が、React が動き出す前に HTML を書き換えたのが原因で、コードの問題ではない。サーバーが返した HTML と、ブラウザ側で React が組み立て直した結果（hydration）が食い違うと、このエラーになる。`localhost` で拡張を無効にすれば消える。

### devtools から `curl localhost:3000` が繋がらない

これまでの `localhost:8000` と同じで、devtools にとっての `localhost` は devtools 自身。コンテナ内からは `web:3000` を使う（→ [topic-docker-networking.md](topic-docker-networking.md)）。

### Mac の Docker で開発するとホットリロードが遅くなりうる

Next.js の公式ドキュメント（Local Development）は、Docker Desktop のホストと VM の間のファイル共有で変更通知が遅れる・落ちると注意している。今回は保存から約1秒で反映され、問題にならなかった。遅いときにポーリング（`watchOptions.pollIntervalMs`）で逃げるのは、公式も最終手段としている。

## 確認したこと

- `docker compose up -d --build web` で db / api / web が揃って立つ
- ホストからの `curl -i localhost:3000/api/v1/todos` に、`server: uvicorn` と `x-request-id` の付いた API のレスポンスが返る（web を通って api が答えている）
- devtools からの `curl web:3000/api/v1/todos` も 200
- ブラウザで `localhost:3000` に雛形ページが表示され、`page.tsx` の保存は約1秒で反映される
