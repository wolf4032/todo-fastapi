# base → deps → dev / builder → prod の5段構成。
# backend/Dockerfile と同じく「依存だけを先に解決する段」と「実行する段」を分ける。
# → docs/notes/step-14-web-container.md
#
# devtools の Node（Dev Container Feature の LTS）と同じメジャー版に揃える。
# slim（Debian）なのは、Next.js の SWC などネイティブバイナリが glibc 前提で配られているため。
FROM node:24-slim AS base

WORKDIR /app

# backend の ENV PATH="/opt/venv/bin:$PATH" に当たる。
# npm install したパッケージのコマンド（next など）は node_modules/.bin に置かれる。
ENV PATH="/app/node_modules/.bin:$PATH"

# --- 依存関係だけを解決する段 ---
FROM base AS deps

# backend と同じ理由で、lock ファイルだけを先に COPY してキャッシュを効かせる。
COPY package.json package-lock.json ./
# npm ci は package-lock.json どおりに入れる（uv sync --frozen に当たる）。
RUN npm ci

# --- 開発用イメージ ---
FROM base AS dev

COPY --from=deps /app/node_modules ./node_modules

# コードは compose.override.yaml でバインドマウントするため、ここでは COPY しない。
# npm run dev ではなく next を直接起動するのは、npm を挟むと docker compose stop の
# 停止シグナル（SIGTERM）が next まで届かず、10 秒待って強制終了になるため。
CMD ["next", "dev"]

# --- 本番用のビルド段 ---
FROM base AS builder

# next build は TypeScript の型検査や Tailwind の変換も行うので、devDependencies ごと要る。
# ここで使った node_modules は prod には持ち込まない。
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN next build

# --- 本番用イメージ ---
FROM base AS prod

ENV NODE_ENV=production
# standalone の server.js は環境変数 HOSTNAME のアドレスで待ち受ける。Docker は HOSTNAME に
# コンテナ ID を入れるので、上書きしないとコンテナ自身の localhost から繋がらなくなる。
# → docs/notes/step-16-prod-web.md
ENV HOSTNAME=0.0.0.0

# standalone は server.js と、実行に要る node_modules だけを集めたもの。
# public/ と .next/static/（ブラウザに配る JS・CSS）は含まれないので、別に COPY する。
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

# backend の prod と同じく、コードは root 所有のまま（実行ユーザーからは読むだけ）にする。
# Next.js が実行中に書き込むキャッシュの置き場だけを node に渡す。
# node ユーザーは node の公式イメージに最初からある一般ユーザー（UID 1000）。
RUN mkdir -p .next/cache && chown node:node .next/cache

USER node

CMD ["node", "server.js"]
