# uvの依存管理: `pyproject.toml`と`uv.lock`の役割分担

## `pip freeze` / `requirements.txt` とは別物

`pip freeze > requirements.txt` は、今installされている環境を**丸ごと書き出す・毎回作り直す派生物**。「直接使う依存」と「その依存が引っ張ってきた依存（推移的依存）」の区別が無く、バージョン範囲の意図（「これ以上なら動く」）が失われた結果のスナップショットでしかない。

uv（Poetry、PDMも同様）は**2ファイル方式**を取る。

- **`pyproject.toml`**: 自分のコードが直接必要とする依存を、**緩いバージョン制約**（`>=x.y.z`など下限のみ）で宣言する。丸ごと再生成するものではなく、`uv add`/`uv remove` で継続的に育てていく**意図の一次情報源**
- **`uv.lock`**: それを実際に解決した**厳密な全依存関係**（推移的依存・ハッシュ込み）を記録する、完全にコマンド管理下にあるファイル。人間が手で編集する対象ではない

`backend/Dockerfile` の `uv sync --frozen` は `uv.lock` だけを厳密に信頼するので、この2ファイルが食い違っていないことが前提になる（→ 下記「手で追加した依存が残っていた話」）。

## 新規依存の追加は `uv add`

`uv add <package>` は次を1コマンドでまとめて行う。

- PyPIから、既存の依存関係全体と矛盾しない範囲で**最新の安定版**（プレリリースは対象外）を解決する
- `pyproject.toml` の `dependencies`（または `--group dev` 指定時は該当グループ）に制約を書き足す
- `uv.lock` を再計算して更新する

バージョンを指定したい場合も `uv add "pkg>=1.2,<2.0"` のように引数で渡せるため、特定バージョンを狙う場合でも基本的に `uv add` 経由で足りる。`pyproject.toml` を直接手で編集する必要はほぼ無い。

新規プロジェクトで単純に「バージョン指定なしで最新を入れる」のは妥当な既定の振る舞い。まだ何も古いバージョンのAPIに依存したコードが存在しないため。

## `uv add` は冪等: 既存の制約を勝手に書き換えない

`pyproject.toml` に既に `alembic>=1.13.0` という制約がある状態で `uv add alembic`（バージョン指定なし）を実行したところ、`pyproject.toml` の制約は `>=1.13.0` のまま変わらず、実際にインストールされたのは `1.19.1` だった。

これはバグではなく仕様通り。`uv add` は「この制約が既に満たされているか」を見るだけで、満たされていれば（`1.19.1 >= 1.13.0` は真）`pyproject.toml` を書き換える必要が無いと判断する。**実際に使われている厳密なバージョンは常に `uv.lock` 側に記録される**ため、`pyproject.toml` の下限表記が実体と離れていても問題にならない。

## 手で `pyproject.toml` に依存を追加すると `uv.lock` と食い違う

Step 6でAlembic導入時、最初 `pyproject.toml` の `dependencies` に `alembic>=1.13.0` を手で書き足したが、`uv lock`/`uv sync`を経由しなかったため `uv.lock` には一切 `alembic` が登場しない状態になった。この状態で `docker compose build`（`uv sync --frozen`）を実行しても、`--frozen` は `pyproject.toml` との整合性チェック自体を省略して `uv.lock` をそのまま使うため、**`alembic` は静かにインストールされないままになる**。

後から `uv add --project backend alembic` を実行することで、この食い違いは解消された（`uv add` は「既に書かれている制約」を尊重しつつ、`uv.lock` 側の欠落を正しく埋める）。教訓: `pyproject.toml` の依存欄は手で編集せず、常に `uv add`/`uv remove` を経由する。

## `devtools` で `uv add` すると `backend/.venv` ができる

`backend/Dockerfile` は `UV_PROJECT_ENVIRONMENT=/opt/venv` を設定しているが、これはDockerfileの `ENV` 命令なのでビルドされたイメージの中でしか効かない。`devtools` コンテナのシェルから直接 `uv add`/`uv lock` を実行すると、この環境変数が無いため、uvは既定の `backend/.venv` を作ってそこにインストールしてしまう。

実害は無い（ルートの `.gitignore` の `.venv/` で無視される、`backend/.dockerignore` の `.venv/` でDockerビルドにも含まれない）。ただし実際にアプリが動くのは常に `docker compose build` で作られる `/opt/venv`（イメージの中）であり、`backend/.venv` は使われない副産物。混乱するようなら削除して構わない。
