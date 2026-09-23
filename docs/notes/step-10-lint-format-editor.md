# Step 10: 静的解析・pre-commit・エディタ体験の仕上げ

作成物: `backend/pyproject.toml`（ruff / mypy / pytest の設定）、`.pre-commit-config.yaml`、`.vscode/settings.json`、`.vscode/extensions.json`、`Makefile`（`lint` / `format`）、`.devcontainer/`（pre-commit の導入と `postCreateCommand`）

リンタ・フォーマッタ・型チェッカ・pre-commit の一般的な仕組みは [topic-lint-and-precommit.md](topic-lint-and-precommit.md) に切り出した。ここではこの構成固有の判断とつまずきを扱う。

---

## 設定は backend/pyproject.toml に集約する

ruff は `.ruff.toml`、mypy は `mypy.ini`、pytest は `pytest.ini` と、それぞれ独立した設定ファイルも持てる。今回は全部 `pyproject.toml` の `[tool.*]` に寄せた。リポジトリ直下に設定ファイルが4つ並ぶより、「backend の設定はここ」と一箇所にある方が探す手間が少ない。

置き場がルートではなく `backend/` なのは、**ツールを走らせる場所が api コンテナの `/app`（＝ `backend/` の中身）だから**。ruff も mypy も設定ファイルを「対象ファイルから上に辿って」探すので、`backend/` 配下のコードは自然に `backend/pyproject.toml` を見つける。

## ルールの選定 — 日本語コメントとぶつかった2つ

既定の `select` は `["E4", "E7", "E9", "F"]` とかなり控えめなので、`E`/`W`/`F`/`I`/`UP`/`B`/`SIM`/`RUF` まで広げた。そのうえで**外した**ものが2つあり、どちらも日本語で書いていることが理由。

- **E501（行が長すぎる）**: 88 文字超が 59 行あったが、**全部が日本語コメント**だった。フォーマッタはコードは折り返すがコメントは折り返さないため、E501 を残すと「自動では直せない指摘」が学習用コメントの行にだけ延々と出続ける。コードの行長はフォーマッタが見ているので、リンタ側は外す
- **RUF001-003（紛らわしい Unicode 文字）**: ASCII と見間違えやすい文字を検出するルール。28 件出て、中身は**全角括弧「（）」**。英語のコードベースでは意味があるが、日本語コメント前提とは噛み合わない

ルールを広げると「本当に見たい指摘」がノイズに埋もれる。外した理由を設定ファイルにコメントで残しておくと、後で「なぜ外したか」を再検討できる。

## B008 と FastAPI の `Depends()`

`B008`（flake8-bugbear）は「引数の既定値の位置で関数を呼ぶな」というルール。既定値は**関数定義時に一度だけ評価される**ので、`def f(x=[])` のような書き方は全呼び出しで同じオブジェクトを共有してしまう。

ところが FastAPI の `db: AsyncSession = Depends(get_db)` はまさにその形。これは「既定値」ではなく「ここに依存を差し込め」という宣言で、正しい書き方。→ [topic-fastapi-dependency-injection.md](topic-fastapi-dependency-injection.md)

`# noqa` を各行に貼るのではなく、設定で例外に登録した。

```toml
[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = ["fastapi.Depends", "fastapi.Query"]
```

## mypy が最初に落ちた — `__init__.py` が無い構成

素で `mypy app tests` を走らせると、検査以前にこう落ちた。

```
app/models/todo.py: error: Duplicate module named "todo" (also at "app/crud/todo.py")
```

`app/` 配下に `__init__.py` を1つも置いていないため、mypy が `app/models/todo.py` と `app/crud/todo.py` を**どちらも「`todo` という名前のモジュール」**と解釈して衝突した。実行時は名前空間パッケージとして問題なく動いていたので、ここで初めて表面化した形。

`__init__.py` を各ディレクトリに足す手もあるが、今回は設定で解決した。

```toml
explicit_package_bases = true
mypy_path = "."
```

「パッケージの起点は実行ディレクトリ（`/app`）」と明示することで、`app.models.todo` / `app.crud.todo` という完全な名前で区別される。

## mypy strict で実際に出た指摘は2件だけ

型ヒントは Step 5 以降ずっと付けてきたので、`strict = true` でも出たのは同じ原因の2件のみ。

```
app/core/exceptions.py:66: error: Argument 2 to "add_exception_handler" of "Starlette"
  has incompatible type "Callable[[Request, HTTPException], ...]";
  expected "Callable[[Request, Exception], ...]"
```

Starlette は例外ハンドラの第2引数を `Exception` と宣言している。こちらのハンドラは `StarletteHTTPException` だけを受け取る形なので、**より狭い型しか受け取れない関数を、広い型を渡す場所に置いている**ことになり、型としては不正。

しかし実行時は「`add_exception_handler` で登録した例外クラスに該当するときだけ呼ぶ」ディスパッチなので、狭い型しか来ない。**型で表現しきれていないのは Starlette 側**であり、こちらのコードは正しい。

こういう箇所は、コードを型に合わせて歪めるのではなく、行単位で逃がす。

```python
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
```

`strict` には `warn_unused_ignores` が含まれるので、**将来 Starlette 側の型が直れば「この ignore はもう不要」と mypy が教えてくれる**。付けっぱなしで腐らない。

## 生成物（migrations/）の扱いは ruff と mypy で分けた

`migrations/` は alembic が生成したコードで、手で書いたものではない。

- **mypy の対象からは外した**（`files = ["app", "tests"]` と `overrides` の `ignore_errors`）。生成物の型を直す作業に意味が薄い
- **ruff の対象には残した**。指摘の中身が `Union[str, None]` → `str | None`、クォート、import 順といった**自動修正で片づくもの**だけであり、`ruff check --fix` と `ruff format` に任せれば手作業は発生しない

「生成物だから触らない」と「リポジトリのコードとして体裁は揃える」の折衷で、**自動で直る範囲かどうか**を基準にした。

## pre-commit は devtools に入れる

`git commit` を打つのは **devtools コンテナ**（VS Code のターミナル／ソース管理ビュー）。そして devtools には docker CLI が無いので、hook から `docker compose exec api ruff ...` を呼ぶことはできない。

そこで pre-commit 本体は devtools のイメージに入れ（`uv tool install pre-commit`）、検査ツール（ruff 等）は pre-commit が自前の隔離環境に用意する構成にした。devtools に ruff を入れる必要は無い。

結果として ruff のバージョンが**2箇所**に出てくる。

| 場所 | 何のため |
|---|---|
| `backend/pyproject.toml` の dev 依存（+ `uv.lock`） | `make lint` / `make format`（api コンテナ）と CI |
| `.pre-commit-config.yaml` の `rev` | `git commit` 時の hook |

ずれると「エディタと `make lint` は通るのに commit で弾かれる」が起きる。ruff を上げるときは必ず両方。

### `pre-commit install` はクローンごとに1回

`.git/hooks/` はクローンで共有されないため。`devcontainer.json` の `postCreateCommand` に入れて、コンテナを作るたびに自動で走るようにした。

なお `pre-commit install` が書き込む `.git/hooks/pre-commit` には、**pre-commit を入れた Python の絶対パスが埋め込まれる**。これは devtools 内のパスなので、**ホスト（Mac）側から `git commit` すると hook は動かない**。git 操作は devtools 側で行う前提。

### hook が docs/notes/*.md を書き換えた

`pre-commit run --all-files` を初めて走らせたとき、`ruff-format` が **Markdown を4件書き換えた**。

```
ruff format..............................................................Failed
- files were modified by this hook
4 files reformatted, 39 files left unchanged
```

43 = Python 17 + Markdown 26。`ruff-format` hook の既定の対象が `[python, pyi, jupyter, markdown]` で、**ruff は Markdown 中の Python コードブロックも整形する**ため。

一般には便利な機能だが、このリポジトリでは困った。書き換わったのが**説明のための意図的な整形**だったため。

```diff
-title: Mapped[str] = mapped_column(String(255))       # NOT NULL
+title: Mapped[str] = mapped_column(String(255))  # NOT NULL
```

`# NOT NULL` と `# nullable` を縦に揃えて見比べさせるのが例の主旨だった。別の1件も、メソッドチェーンが積み増されることを見せるための1行が括弧で折り返された。

さらに、`make lint` はこれを検出していなかった。**範囲が違う**ため。

| | 実行位置 | 視界に入る範囲 | 適用される設定 |
|---|---|---|---|
| `make lint` | api コンテナの `/app`（= `backend/`） | `backend/` のみ | `backend/pyproject.toml` |
| pre-commit hook | リポジトリのルート | 追跡中の全ファイル | ファイルごとに上へ探索。`backend/` の外には**設定が無く既定値** |

リポジトリのルートに ruff の設定ファイルが無いので、`docs/` 配下には `E501` 無効や `RUF001-003` 無効といった設定が**効かない**。

hook 側の範囲を `make lint` に揃えて解決した。

```yaml
- id: ruff-format
  files: ^backend/
  types_or: [python, pyi]
```

「同じ検査を1箇所の定義から回す」ことが目的なのに、**実行経路ごとに対象範囲が違うと結論が食い違う**。ツールのバージョンを揃えるだけでは足りない。

### `check-json` と JSONC の衝突

`pre-commit-hooks` の `check-json` を入れたところ、`.devcontainer/devcontainer.json` と `.vscode/*.json` で落ちる。拡張子は `.json` でも中身はコメントを許す **JSONC** で、厳密な JSON パーサは通らない。`exclude` で外した。

## エディタ設定 — 計画からの変更点

`docs/plan.md` の Step 10 では `python.defaultInterpreterPath` を **`/opt/venv/bin/python`** に固定する想定だったが、**これは動かない**。`/opt/venv` は api コンテナの中にあり、VS Code の拡張機能が動いている devtools からは見えない。→ [topic-docker-networking.md](topic-docker-networking.md)

Step 4 のノートで予告していたとおり、devtools 側にも同じ `uv.lock` から venv を作り、そちらを指す形にした。

```jsonc
"python.defaultInterpreterPath": "${workspaceFolder}/backend/.venv/bin/python"
```

`backend/.venv` は `postCreateCommand` の `uv sync --frozen --project backend` で作られる。api コンテナの `/opt/venv` と**同じ `uv.lock` 由来**なので、中身は一致する。→ [topic-uv-dependency-management.md](topic-uv-dependency-management.md)

さらに `python.analysis.extraPaths` に `backend` を足している。`app` は「インストールされたパッケージ」ではなく `/app` 直下に置いたコードなので（`tool.uv.package = false`）、venv を見るだけでは `import app...` を解決できないため。

### `formatOnSave` が発火しない条件

`files.autoSave` を `"afterDelay"`（時間経過で自動保存）にすると、**`editor.formatOnSave` は走らない**。VS Code の仕様で、タイマー保存は編集の途中経過という扱いのため。整形でカーソルが飛ぶのを避けている。

`"onFocusChange"`（フォーカスが外れたら保存）なら確定的なタイミングなので両立する。

### テストエクスプローラは無効にした

VS Code のテスト機能から pytest を動かすと、走るのは **devtools の Python** であって api コンテナではない。開発・テスト・CI を同じイメージで揃えるという構成の前提が崩れるうえ、devtools には DB の接続情報も渡していないので `Settings()` の生成時点で落ちる。テストは `make test` に一本化する。

### `.editorconfig` は拡張機能を入れないと効かない

Step 1 で `.editorconfig` を置いたが、**VS Code は標準では `.editorconfig` を読まない**。`editorconfig.editorconfig` 拡張を入れて初めてエディタ上で有効になる。それまでは「宣言だけされて機能していない」状態だった。

現状の守備範囲を整理するとこうなる。

| 対象 | 担保しているもの |
|---|---|
| Python ファイルの整形 | ruff format（保存時 + pre-commit） |
| コミットされる内容の行末空白・末尾改行 | pre-commit の `trailing-whitespace` / `end-of-file-fixer` |
| **編集中の** yaml / json / md / Makefile のインデント幅・改行コード | `.editorconfig` + EditorConfig 拡張 |

`files.insertFinalNewline` などを `settings.json` に直接書く手もあるが、そうすると `.editorconfig` を残す意味が無くなる。`.editorconfig` はエディタ非依存の規格なので、**定義を1箇所に保ったまま拡張で読ませる**方を選んだ。

なお「余分な末尾改行を削る」は `.editorconfig` の規格に無いため編集中は起きない。コミット時に `end-of-file-fixer` が正規化する。

### 「手元では効いている」の正体

作業中、「保存すると末尾に改行が自動で入るので `insert_final_newline` は要らないのでは」という話が出た。実際に入っていたのは **VS Code の個人設定（ユーザー設定）** で `files.insertFinalNewline` が有効だったため。VS Code の既定値は `false` で、リポジトリには何も無かった。

つまり快適さの出所がリポジトリではなく個人のマシンにあり、他の人が clone しても再現しない。Step 10 が「環境定義をリポジトリに入れる」ことを扱っているのは、まさにこの食い違いを潰すため。

### `devcontainer.json` と `.vscode/extensions.json` の使い分け

同じ拡張機能の一覧が2箇所に出るが、役割が違う。

- `devcontainer.json` の `customizations.vscode.extensions` … Dev Container 接続時に**自動インストールされる**
- `.vscode/extensions.json` … Dev Container を使わずにフォルダを開いた人への**推奨表示**

### 入れた拡張機能

| 拡張機能 | 役割 |
|---|---|
| `ms-python.python` / `ms-python.vscode-pylance` | インタプリタ選択・デバッガ / 補完・定義ジャンプ・波線 |
| `charliermarsh.ruff` | 保存時の整形と自動修正。ruff 本体を同梱している |
| `tamasfe.even-better-toml` / `redhat.vscode-yaml` | `pyproject.toml` / `compose.yaml` の補完とスキーマ検証 |
| `editorconfig.editorconfig` | `.editorconfig` を実際に効かせる |
| `usernamehw.errorlens` | ruff / mypy / Pylance の指摘を行末に直接表示 |
| `eamodio.gitlens` / `mhutchie.git-graph` | 行ごとの blame / ブランチとマージのグラフ |
| `oderwat.indent-rainbow` | インデントの深さを色分け |
| `mikestead.dotenv` | `.env` の色付け |

**Docker 拡張（`ms-azuretools.vscode-docker`）は入れない。** 拡張機能が動いているのは devtools コンテナの中で、そこに docker CLI も docker ソケットも無いため、入れても動かない。→ [topic-docker-networking.md](topic-docker-networking.md)

Pylance の型チェックは `python.analysis.typeCheckingMode` を `"standard"` に明示した。既定値が VS Code / 拡張の版で変わるため、環境差を無くす意図。mypy とは別エンジンなので指摘は完全には一致せず、**最終的な判定は `make lint`（mypy）**という位置づけになる。

## make lint / make format

```make
lint:
	docker compose exec api ruff check .
	docker compose exec api ruff format --check .
	docker compose exec api mypy

format:
	docker compose exec api ruff check --fix .
	docker compose exec api ruff format .
```

api コンテナで走らせるのは `make test` と同じ理由で、ツールのバージョンが `uv.lock` に固定され、手元と CI で結果がずれないため。CI からも同じターゲットを呼べば、実行内容の定義は1箇所で済む。

`ruff format --check` は**書き換えずに差分の有無だけ**を見る（あれば失敗）。lint は報告のみ、format は修正、と役割を分けている。

make はレシピの各行を別々のシェルで順に実行し、失敗した時点で止まるので、`&&` で繋がなくても「1行でも落ちれば `make lint` は失敗」になる。

### format 側で `--exit-zero` が要った理由

最初 `format` に `--exit-zero` を付けずに書いたところ、こうなった。

```
$ make format
docker compose exec api ruff check --fix .
W291 Trailing whitespace
 --> migrations/versions/9181c9c00bed_create_todos_table.py:4:9
Found 13 errors (12 fixed, 1 remaining).
make: *** [format] Error 1
```

`ruff check --fix` は「12件直したが1件残った」で終了コード 1 を返し、**make がそこで止まって `ruff format` に到達しなかった**。

そして残った W291 は、**`ruff format` なら直せるもの**だった。場所が docstring の中（`Revises: ` の行末）で、リンタとしては文字列リテラルの中身を書き換えることになるため安全な自動修正と見なされないが、フォーマッタは docstring の行末空白を正規化する。

`lint`（報告専用）が落ちるのは正しいが、`format`（修正専用）が「まだ直せない指摘が残っている」ことを理由に止まるのは筋が違う。`--exit-zero` で終了コードを握り潰し、必ず整形まで到達させる形にした。

なお、この行末空白は pre-commit の `trailing-whitespace` hook でも消える。同じ問題に別の層から手が届いている。

## 確認して分かったこと

- `uv add --dev ruff mypy` で ruff 0.16.8 / mypy 2.3.1 が入り、`.pre-commit-config.yaml` の `rev: v0.16.8` と一致した
- `make format` で `migrations/versions/` の整形が実際に走るところを確認（`2 files reformatted`）
- `make lint` は3つとも通過。`ruff check` → `All checks passed!`、`ruff format --check` → `17 files already formatted`、`mypy` → `Success: no issues found in 15 source files`
- `pre-commit run --all-files` の初回は各 hook の隔離環境の構築から始まる（`Installing environment for ...`）。2回目以降は `~/.cache/pre-commit` から再利用される
- `end-of-file-fixer` が `backend/migrations/README`（alembic の生成物。末尾に改行が無かった）を修正した
- `ruff-format` hook が Markdown を書き換えた → 上記「hook が docs/notes/*.md を書き換えた」
