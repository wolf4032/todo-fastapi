# 開発用ツールボックスのイメージ。
# VS Code (Dev Container) はこのコンテナに接続する。
# アプリの本番イメージ（backend/Dockerfile）とは別系統で、開発に必要なものだけを入れる。
# 将来フロントエンドを足すときも、Node はこちら側に追加する。
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# git は slim イメージに入っていない。無いと VS Code の Git 機能が丸ごと無効になる。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        make \
        curl \
        ca-certificates \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# uv はインストールスクリプトを走らせるより、公式イメージからバイナリを取る方が速く確実。
# latest ではなくタグを固定するのは、ビルドする時期によって挙動が変わるのを避けるため。
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /usr/local/bin/

# 非 root ユーザーで作業する。root のままだと bind mount したリポジトリとの UID 不一致で
# git の所有者チェックに引っかかり、リポジトリを認識しなくなる。
# 名前 vscode は Dev Containers の、UID 1000 は Debian 系の慣習に合わせたもの。
# → docs/notes/step-02-devcontainer.md
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID --create-home --shell /bin/bash $USERNAME

# Claude Code の設定置き場。ここには名前付きボリュームをマウントするが、
# イメージ側に vscode 所有のディレクトリを先に作っておかないと、
# Docker が root 所有でボリュームを初期化してしまい書き込めなくなる。
RUN mkdir -p /home/$USERNAME/.claude \
    && chown -R $USER_UID:$USER_GID /home/$USERNAME/.claude

USER $USERNAME
