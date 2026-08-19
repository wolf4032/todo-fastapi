# Step 4: backend のマルチステージ Dockerfile と最小 FastAPI

作成物: `backend/pyproject.toml` / `uv.lock`、`backend/Dockerfile`、`backend/.dockerignore`、`backend/app/main.py`、`compose.yaml`（`api` の共通定義）、`compose.override.yaml`（`api` の開発差分）

CMD / RUN のタイミングや healthcheck の仕組みなど、Docker 全般の一般知識は → [topic-docker-build-and-run.md](topic-docker-build-and-run.md) に切り出した。ここでは backend 固有の設計判断を扱う。

---

## マルチステージの役割分担

```
base → builder（本番用の依存解決） → prod
     → builder-dev（開発用の依存解決） → dev
```

`builder` / `builder-dev` は依存関係を解決するためだけの使い捨てステージで、`pyproject.toml` と `uv.lock` だけを先に `COPY` している。`app/` を先に `COPY` すると、コードを1行直すだけでこの層のキャッシュが効かなくなり、`uv sync` が毎回再実行されて遅くなる。

`dev` と `prod` はそれぞれの venv だけを `COPY --from=` で受け取る。`uv` バイナリ自体は `builder` / `builder-dev` にしか `COPY` しておらず、最終イメージ（`dev` / `prod`）には残らない。

## ビルドコンテキストを `./backend` に絞る効果

`compose.yaml` の `api.build.context: ./backend` により、Docker デーモンに送信されるファイル一式も `COPY` の起点も `backend/` 配下だけになる。ルートの `compose.yaml` や `.devcontainer/`、将来の `frontend/` はビルド中のコンテナから物理的に見えない。`devtools` の `context: .devcontainer`（→ [step-02-devcontainer.md](step-02-devcontainer.md)）と同じ考え方。

## `.dockerignore` はステージを区別できない

`.dockerignore` はビルドコンテキスト全体に対して1回だけ効き、「`dev` には含めるが `prod` には含めない」という出し分けができない。そのため `backend/.dockerignore` にはどのステージにも不要なキャッシュ類だけを書き、「本番から `tests/` を外す」は `prod` ステージの `COPY app/ ./app/` で**必要なものだけを明示的に集める**ことで実現している。

## `[tool.uv] package = false`

pyproject.toml ベースの Python プロジェクトは既定で「このディレクトリ自体を pip でインストール可能なパッケージにする」前提（PEP 517/518 に基づく、uv 固有ではない一般的な話）。`uv sync` は依存関係のインストールに加えて、自分自身を editable install する手順も走らせようとする。

`pip install numpy` が「numpy のファイルをカレントディレクトリに展開する」のではなく「venv の site-packages に配置し、そこから import できるようにする」のと同じ意味で、`package = true`（既定）は**このプロジェクト自身もその「配置される側」にする**設定。`app/` はどこかに配布したり import されたりする予定が無く、`uvicorn app.main:app` を作業ディレクトリから直接読ませるだけなので、`package = false` でこの手順自体を止めている。将来 `app/` を配布可能なライブラリにしたくなったら `package = true` に戻し `[build-system]` を足す。

## 非 root ユーザーと ARG について

`prod` ステージで `groupadd` / `useradd` により `app`（UID/GID 1000）を作っているが、これは **Linux のアカウント（`/etc/passwd` へのエントリ）を作るだけ**で、ディレクトリの所有者には触れない。`COPY --from=builder` や `COPY app/ ./app/` は `USER app` より前、つまり root として実行されるため、コピーされたファイルは root 所有のままになる。今回はアプリが `/app` や `/opt/venv` に書き込む必要が無いので実害は無いが、書き込みが要る場合は `COPY --chown=app:app` のように所有者ごと指定する必要がある。

`prod` はここを `ARG` 化していない。`.devcontainer/Dockerfile` の `ARG USERNAME` / `ARG USER_UID` と違い、`prod` の `app` ユーザーはホストのどの UID とも対応する必要が無い（Step 11 で見る通り本番はバインドマウントを一切しないため）ので、外から差し替える動機が無い。`devtools` 側の `ARG` も、実際に UID をホストに合わせているのは `updateRemoteUserUID: true`（コンテナ**起動後**の書き換え）の方で、`ARG` 自体は Dev Container の Dockerfile テンプレートによくある慣習的な差し替え口であり、現状 `--build-arg` で上書きされている箇所は無い。UID・所有権・git の dubious ownership の仕組みそのものは → [step-02-devcontainer.md](step-02-devcontainer.md) と [topic-docker-volumes.md](topic-docker-volumes.md) に既にまとめてある。

`dev` ステージには `USER` 命令が無く root のまま動く。計画の「非 root 実行」が明示的に対象としているのは本番イメージとツールボックスの2つで、`api` の開発コンテナは対象外としている。バインドマウントしている以上、非 root にするならホスト UID との整合が必要になるが、`devtools` にある `updateRemoteUserUID` 相当の自動調整の仕組みが `api` サービスには無いため、今の時点では手当てしていない。

## `./backend:/app` で `backend/` を丸ごとマウントする理由

`app/` だけでなく `backend/` 全体（将来の `tests/` を含む）をマウントしているのは、**Step 9 でテストを `api` コンテナ自身の中で実行する**ため。`devtools` には `fastapi` 等アプリの依存関係が一切入っておらず（`git` / `make` / `uv` / `postgresql-client` のみ）、`app/` のコードを import して動かすテストは `devtools` からは実行できない。`docker compose exec api pytest` のように **api コンテナの中で直接実行する**必要があり、そのためには `tests/` も含めて `backend/` 全体が `api` コンテナから見えている必要がある。

## 既知の未解決ギャップ: devtools に `fastapi` が無い

`devtools` で `backend/app/main.py` を開くと、`from fastapi import FastAPI` に波線が出る（実際に発生済み）。`devtools` は Python パッケージを何も持っていないため。

ツールボックス方式の狙いは「**言語をまたいで**波線を出さない」ことであり、「アプリが依存を増やすたびに devtools 側にも自動で反映される」ことまでは保証していない。この波線対策は Step 10 の `python.defaultInterpreterPath` 固定で扱う予定（→ `docs/plan.md` の Step 10）。devtools 側にも `backend/uv.lock` から同内容の venv を作り、それを Pylance の解決対象にする形になる見込みだが、具体的な作り方は Step 10 で手を動かしながら詰める。

---

## 確認して分かったこと

- `docker compose up -d api` は `todo-fastapi-api` イメージが存在しなかったため自動でビルドが走った（`up` は対象イメージが無ければビルドする。既にある場合は `Dockerfile` を直しても自動では再ビルドされず、`docker compose build` または `up --build` が要る → [topic-docker-build-and-run.md](topic-docker-build-and-run.md)）
- `curl localhost:8000/health` → `{"status":"ok"}`。`docs` の Swagger UI にも `GET /health` が表示された
- `backend/app/main.py` を編集して保存しただけで、再ビルド無しに `curl` の結果が `{"status":"ok!"}` に変わった。バインドマウント + `--reload` の効果を実地で確認できた
- `docker compose exec api ls /opt/venv/bin` で `fastapi` / `uvicorn` に加え `pytest` / `httpx` も入っていることを確認（`dev` は `builder-dev` 由来の venv なので dev 依存も含まれる）
