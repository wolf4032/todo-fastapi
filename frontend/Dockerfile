# base → deps → dev の3段構成（本番用の builder / prod は Step 16 で足す）。
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
