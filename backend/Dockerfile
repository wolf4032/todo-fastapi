# base → builder / builder-dev → dev / prod の5段構成。
# 目的は「1つの Dockerfile から dev と prod を作り分けること」で、
# イメージサイズが小さくなるのはその副産物。→ docs/notes/step-04-backend-container.md
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# --- 依存関係だけを解決する段（本番用） ---
FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /usr/local/bin/

# pyproject.toml と uv.lock だけを先に COPY する。
# app/ を先に COPY すると、コードを1行直すだけでこの層のキャッシュが効かなくなり、
# 依存関係の再インストールが走ってしまう。
COPY pyproject.toml uv.lock ./
# --frozen は uv.lock をそのまま使う（再解決しない）指定。
# --no-dev で pytest 等の開発用グループを除外する。
RUN uv sync --frozen --no-dev

# --- 依存関係だけを解決する段（開発用。pytest 等も含める） ---
FROM base AS builder-dev

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# --- 開発用イメージ ---
FROM base AS dev

COPY --from=builder-dev /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# コードは compose.override.yaml でバインドマウントするため、ここでは COPY しない。
# → docs/notes/step-04-backend-container.md
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- 本番用イメージ ---
FROM base AS prod

# 本番も非 root で実行する。
RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 本番イメージには uv もテストライブラリも tests/ も存在しない。
# 必要なもの（app/ だけ）を明示的に COPY することで実現している。
COPY app/ ./app/
# マイグレーションは本番でも「別ジョブとして」実行するため、
# その実行に必要な alembic.ini と migrations/ もここに含める。
# → docs/notes/step-06-alembic.md
COPY alembic.ini ./
COPY migrations/ ./migrations/

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
