# Step 2: Dev Container

作成物: `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`, `compose.yaml`, `compose.override.yaml`

---

## なぜツールボックス方式なのか

**VS Code の Dev Container は、1ウィンドウにつき1コンテナにしか接続できない。**

サービスごとに開発コンテナを分ける流派だと、バックエンド用コンテナに接続した状態でフロントのコードを開いた瞬間、そのコンテナに TypeScript も `node_modules` も存在しないため「モジュールが見つかりません」の波線が全面に出る。

言語をまたいで波線を出さないためには、**両方の言語環境と両方の依存関係が、接続先の1コンテナ内に揃っている必要がある**。そこで「開発ツール一式を持つツールボックスコンテナ」を1つ用意し、VS Code は常にそこへ接続する。

アプリを動かすコンテナ（`api`、将来の `web`）は本番と同じ Dockerfile から作り、ツールボックスとは完全に別系統にする。これで「開発ツールが本番イメージに混入する」問題も同時に避けられる。

将来 Node を足すときは **Dev Container Features**（`devcontainer.json` に `ghcr.io/devcontainers/features/node:1` を1行）を使う。公式イメージから `COPY --from=node /usr/local/bin ...` でランタイムを移植する手法もあるが、不足する共有ライブラリ（pip が要求する `libexpat.so.1` など）・PATH・バージョンが埋め込まれたディレクトリ名を手作業で埋める必要があり、バージョン更新のたびに壊れやすい。

---

## `vscode` / UID 1000 の由来

どちらも「Dev Container のデフォルト」ではなく、**慣習に合わせて自分で作った**もの。

- **UID 1000** は Linux 全般の慣習。`root` が 0 で、Debian 系の `useradd` は一般ユーザーを 1000 から採番する
- **`vscode` という名前**は Dev Containers 界隈の慣習。Microsoft 配布の dev container 用イメージ（`mcr.microsoft.com/devcontainers/*`）には最初から `vscode`（UID 1000）が入っている

今回のベースは `python:3.13-slim` で、これは公式 Python イメージであって dev container 用ではないため `vscode` ユーザーが存在しない。だから `groupadd` / `useradd` で自作している。

---

## Git に関する2つの別々の話

「git の設定」という言葉で混ざりがちだが、まったく別物。

### (A) `user.name` / `user.email` — コミットの著者名

自己申告の文字列。認証とは無関係。→ `step-01-git-init.md`

### (B) 所有者チェック — セキュリティ機能

こちらが Dev Container で問題になる方。

#### 背景: CVE-2022-24765

Git はカレントディレクトリから親方向へ `.git` を探しに行く。そして **`.git/config` には `core.pager` のような「コマンドを実行する設定」が書ける**。

つまり悪意ある人が用意したディレクトリに入って `git status` と打っただけで、仕込まれたコマンドが自分の権限で実行されてしまう。共有サーバや `/tmp` 配下が典型的な攻撃経路だった。

対策として **Git 2.35.2 以降は、リポジトリの所有者が現在のユーザーと異なる場合、操作そのものを拒否する**ようになった。

```
fatal: detected dubious ownership in repository at '/workspaces/...'
```

#### Docker で頻発する理由

bind mount はホストのファイルシステムをそのまま見せる。ホストで UID 501 が所有するファイルは、コンテナ内でも「UID 501 のファイル」に見える。コンテナ内で root(0) として動いていると所有者が一致せず、git が拒否する。

**`.git` は存在するのに VS Code のソース管理ビューが空になる**、という症状の正体。
（もう1つの原因は、そもそも slim イメージに `git` バイナリが入っていないこと。）

#### 対策は2通り、両方使っている

| 対策 | 手段 | 性質 |
|---|---|---|
| UID を一致させる | `"updateRemoteUserUID": true` | 根本解決 |
| 所有者が違っても信用すると宣言 | `safe.directory` | 保険 |

補足: macOS の Docker Desktop はファイル共有層（VirtioFS）が所有者をコンテナ内ユーザーに見せかけることが多く、実際には dubious ownership が起きない場合もある。ただし挙動が OS・バージョン依存なので保険は残す。

---

## `git config --global --add safe.directory ${containerWorkspaceFolder}` の分解

`postCreateCommand`（コンテナ作成後に1回実行される）に書いているコマンド。

| 部分 | 意味 |
|---|---|
| `safe.directory` | 「このパスは所有者が自分と違っても操作を許可する」という例外リスト |
| `--add` | この設定は複数の値を持てる（multi-valued）ため、付けないと既存の値を上書きしてしまう |
| `--global` | **コンテナ内の** `/home/vscode/.gitconfig` を指す。ホストの `~/.gitconfig` ではない |
| `${containerWorkspaceFolder}` | Dev Containers が展開する変数。ここでは `/workspaces/todo-fastapi` |

コンテナを作り直すたびにこの設定は消えるので、`postCreateCommand` で毎回設定し直している。

---

## `ARG` と `ENV` の違い

| | `ARG` | `ENV` |
|---|---|---|
| 有効な期間 | `docker build` の実行中のみ | イメージに焼かれ、コンテナ実行中もずっと残る |
| コンテナ内で `echo $VAR` | 空 | 値が出る |
| 外から変更 | `--build-arg` で可能 | ビルド時は不可（`docker run -e` で実行時に上書き） |
| 用途 | バージョン番号、ユーザー名、ビルド分岐 | アプリが実行時に読む設定 |

`ARG USERNAME=vscode` は `useradd` と `USER` で使うだけの一時変数なので、出来上がったコンテナに `USERNAME` という環境変数は存在しない。一方 `ENV PYTHONUNBUFFERED=1` はコンテナが動いている間ずっと Python が参照する。

外から差し替える例:

```
docker compose build --build-arg USERNAME=developer devtools
```

### 知っておくべき挙動

- **スコープはステージ単位**。マルチステージビルドでは、`ARG` は宣言したステージの終わりまでしか有効でない。次のステージで使うには再宣言が必要
- **`FROM` より前の `ARG` はグローバル扱い**だが、`FROM` 行の中でしか使えない（ベースイメージのタグを変数にする用途）
- **`ARG` 同士は参照できる**。`ARG USER_GID=$USER_UID` は「グループ ID は指定が無ければユーザー ID と同じ」の意味
- **同名の `ENV` があると `ENV` が勝つ**。混在させると事故のもと
- **秘密情報を `ARG` で渡してはいけない**。`docker history` でビルド履歴を覗くと値が見える。パスワードや API キーには `RUN --mount=type=secret` を使う

---

## マウント先を `/workspaces/<リポジトリ名>` にする理由

`- .:/workspaces` ではなく `- .:/workspaces/todo-fastapi` にしている。

1. `/workspaces` は本来「複数のリポジトリを並べる親ディレクトリ」の位置づけ。直下を1プロジェクトで占有すると、将来別リポジトリを同時に開くときに衝突する
2. `/workspaces/<リポジトリ名>` が Dev Containers の標準的な慣習で、周辺のツールやドキュメントもこれを前提にしている
3. VS Code のタイトルバーやターミナルのプロンプトに出るフォルダ名が `workspaces` になってしまい、何のプロジェクトか分からなくなる
4. 後でデバッガを設定する際、`pathMappings` でホスト側とコンテナ内のパス対応を書く。パスにリポジトリ名が入っている方が対応関係を追いやすい

なお `devcontainer.json` の `workspaceFolder` と、compose の bind mount 先は**一致させる必要がある**。

---

## コンテナ内で Claude Code を動かす

AI 駆動開発を学ぶ目的もあるため、ツールボックスに Claude Code を入れている。

### インストールは Dev Container Feature で

```json
"features": {
  "ghcr.io/devcontainers/features/node:1": {},
  "ghcr.io/anthropics/devcontainer-features/claude-code:1.0": {}
}
```

CLI と VS Code 拡張の両方が入る。タグの `:1.0` は **Feature のインストールスクリプトのバージョン**であって Claude Code 本体のバージョンではない。

Claude Code は npm 経由で入るため **Node.js が必須**。「Node はフロント着手時に」と決めていたが、前倒しで入ることになる。ツールボックス側の話なので本番イメージには影響しない。

#### ハマった点: `Failed to install Node.js and npm`

claude-code Feature は Node が無ければ自前で入れようとするが、`python:3.13-slim`（Debian ベース）では失敗した。

```
Setting up nodejs (20.19.2+dfsg-1+deb13u2) ...
Failed to install Node.js and npm
ERROR: Node.js and npm are required but could not be installed!
```

ログのとおり `nodejs` 自体は入っている。原因は **Debian では `nodejs` と `npm` が別パッケージ**であること。Feature 側の npm 存在チェックが通らず落ちる。

対策は Node を Feature として明示指定すること（公式ドキュメントにもこのフォールバックが記載されている）。Feature には依存関係と導入順序の仕組みがあるため、両方を並べておけば Node が先に入る。

### 認証と履歴の永続化

既定ではコンテナのホームディレクトリはリビルドで捨てられるため、毎回ログインし直しになる。名前付きボリュームを `~/.claude` にマウントして永続化する。

```yaml
volumes:
  - claude-config:/home/vscode/.claude
environment:
  CLAUDE_CONFIG_DIR: /home/vscode/.claude
```

**`CLAUDE_CONFIG_DIR` の指定が要る理由**: OAuth アカウント情報を持つ `~/.claude.json` は、既定では `~/.claude` の**外**に置かれる。ボリュームを `~/.claude` にマウントしただけでは、この1ファイルがリビルドで消えて再ログインになる。この環境変数で保存先を揃える。

### 名前付きボリュームと所有者のハマりどころ

**症状**: コンテナは `vscode`（UID 1000）で動くが、`/home/vscode/.claude` がイメージ内に存在しないと、Docker はボリュームを **root 所有**で作る。vscode からは読めるが書けないため、Claude Code が認証情報を保存できない。

**対策**: Dockerfile 側で先に vscode 所有のディレクトリを作っておく。

```dockerfile
RUN mkdir -p /home/$USERNAME/.claude \
    && chown -R $USER_UID:$USER_GID /home/$USERNAME/.claude
```

「内容がリセットされる」のではなく「書き込めない」のがポイント。仕組みと注意点（この初期化は**ボリュームの初回作成時にしか起こらない**ため、Dockerfile を直しても既存ボリュームには効かない、など）は → [topic-docker-volumes.md](topic-docker-volumes.md)

### セッションは移せるのか

調べた結果、以下が分かった。

| やりたいこと | 可否 |
|---|---|
| ホストのセッションをコンテナで続ける | **不可**（履歴は `~/.claude/projects/<作業ディレクトリのパス>/` にローカル保存され、パスもホームも異なる） |
| ローカルのセッションを Web に押し上げる | **CLI からは不可**（移動は一方向。Desktop アプリの「Continue in」のみ対応） |
| Web セッションを手元に引き込む | 可（`claude --teleport`。要 GitHub リモート） |
| 同じセッションを別デバイスから操作 | 可（**Remote Control**。ただしセッションが動くのは開始した場所のまま） |

**Claude Code on the web のセッションは Anthropic 管理のクラウド VM 上で動き、GitHub から clone して作業する**。手元の dev container の中で動くわけではない。

したがって環境をまたいで作業を引き継ぐ現実的な方法は、**セッションを移すことではなく、文脈をリポジトリに置くこと**。この目的で `CLAUDE.md`（進め方の規約）と `docs/plan.md`（実装計画）をリポジトリに置いている。

---

## Compose の複数ファイルマージ

Docker Compose は複数のファイルを重ねて1つの構成に合成できる。

| ファイル | 役割 | 読まれ方 |
|---|---|---|
| `compose.yaml` | 共通の基本定義 | 常に |
| `compose.override.yaml` | 開発時の差分 | **この名前なら自動** |
| `compose.prod.yaml` | 本番相当 | `-f` で明示指定時のみ |

```
docker compose up                                      # 共通 + 開発差分
docker compose -f compose.yaml -f compose.prod.yaml up # 共通 + 本番差分
```

開発専用の `devtools` を `compose.override.yaml` に置くことで、**本番の構成定義に開発用サービスが混ざらない**。

マージ結果は `docker compose config` で確認できる（実行はせず、合成後の設定を表示するだけ）。

### ビルドコンテキストを絞る

`devtools` の `build.context` を `.devcontainer` にしている。コンテキストとは **Docker デーモンに送られるファイル群**であり、`COPY` の起点でもある。リポジトリ全体を送るより速く、意図しないファイルの混入も防げる。

この考え方は後で `backend/` にも使う（本番イメージに何が入るかを、ディレクトリの切り方で制御する）。
