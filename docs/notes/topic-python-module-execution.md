# `python -m` とモジュールの探索パス（`sys.path`）

Step 9 で `make test` を `pytest` ではなく `python -m pytest` にした理由を追ったときに整理したもの。

## `sys.path` とは

Python が `import` 対象を探しに行く**ディレクトリのリスト**。先頭から順に探し、最初に見つかったものを使う。

いわゆる「パスを通す」と同じ発想だが、シェルの `PATH` とは対象が別物なので混同しない。

| | 探索されるもの | 使う主体 |
|---|---|---|
| シェルの `PATH` | **実行ファイル**（`pytest`、`git` など） | シェル |
| Python の `sys.path` | **import 対象のモジュール・パッケージ** | Python インタプリタ |

## 実行方法によって先頭に入るものが変わる

| 実行方法 | `sys.path[0]` |
|---|---|
| `python -m モジュール名` | **カレントディレクトリ**（絶対パス） |
| `pytest` など、インストールされたコマンドを直接叩く | **その起動スクリプトが置かれたディレクトリ**（`/opt/venv/bin`） |
| `python -c "..."` / 対話モード | `''`（空文字列） |

`python -m X` は「その名前のパッケージを探して、モジュールとして実行する」という Python 本体の機能で、**実行前にカレントディレクトリを `sys.path` の先頭に追加する**という仕様を持つ。

一方 `pytest` というコマンドの実体は、`uv sync` 時に作られる `/opt/venv/bin/pytest` という小さな起動スクリプト。スクリプトを実行したときの `sys.path[0]` は**そのスクリプト自身が置かれたディレクトリ**であり、カレントディレクトリは自動では入らない。

### 空文字列 `''` は「探索対象なし」ではない

`''` は Python では**カレントディレクトリを指す慣習的な表記**。`print()` すると何も見えないので空欄に見えるだけで、「今いるディレクトリを見ろ」という指示である。`repr()` で囲むと正体が見える。

```
$ docker compose exec api python -c "import sys; print(repr(sys.path[0]))"
''

$ docker compose exec api python -m site
sys.path = [
    '/app',
    ...
]
```

`-c` では `''`、`-m` では絶対パス `/app` と表記が違うが、**どちらもカレントディレクトリを指していて意味は同じ**。

## カレントディレクトリ自体は変わらない

よくある誤解として「`-m` を付けるとカレントディレクトリで実行され、付けないとモジュール側のディレクトリで実行される」というものがあるが、**作業ディレクトリはどちらの場合も同じ**（シェルでいる場所がそのまま使われる）。

変わるのは `sys.path` の先頭だけ。実際、`tests/conftest.py` の `Config("alembic.ini")` という相対パス指定が `/app/alembic.ini` を読めているのは、カレントディレクトリが `/app` だからであって `-m` とは無関係。

## このプロジェクトでの帰結

`Makefile` の `test` ターゲットが `python -m pytest` なのはこのため。テストコードは `from app.core.config import settings` のように **`app` パッケージを絶対 import している**ので、`sys.path` に `/app`（＝コンテナ内のカレントディレクトリ、`Dockerfile` の `WORKDIR`）が入っていないと解決できない。

`-m` を外すと、狙いどおりこうなる。

```
$ docker compose exec api pytest
ImportError while loading conftest '/app/tests/conftest.py'.
E   ModuleNotFoundError: No module named 'app'
```
