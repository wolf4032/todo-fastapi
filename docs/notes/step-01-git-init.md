# Step 1: git の初期化とコミットの著者設定

作成物: `.gitignore`, `.editorconfig`, リポジトリローカルの git 設定

---

## 初期ブランチ名の話

`git init -b main` の `-b` は初期ブランチ名を指定するオプションだが、**すでに `.git` があるディレクトリでは無視される**。

```
warning: re-init: ignored --initial-branch=main
```

`git init` を素で叩いてしまった後にやり直すには、リネームする。

```
git branch -m main
```

### なぜ削除ではなくリネームなのか

- **今いるブランチは削除できない**（`error: cannot delete branch 'master' used by worktree at ...`）
- 最初のコミットが無い状態では、**ブランチはまだ実体を持たない**（`git branch` の出力が空になる）。これを *unborn branch* と呼び、「これから作られる予定の参照」として `HEAD` に記録されているだけの状態

古い Git（2.30 未満）では unborn branch のリネームができなかったため、その場合は参照を直接書き換える。

```
git symbolic-ref HEAD refs/heads/main
```

---

## git 設定の優先順位

Git は設定を3つの場所から読み、**先に見つかったものが勝つ**。

| 範囲 | 場所 | 指定方法 |
|---|---|---|
| リポジトリローカル | `<repo>/.git/config` | `git config`（オプション無し） |
| グローバル | `~/.gitconfig` | `git config --global` |
| システム | `/etc/gitconfig` 等 | `git config --system` |

今回はこのリポジトリで使う ID を、リポジトリローカルに設定した。

```
git config user.name "..."
git config user.email "..."
```

確認は `git config --local --list` で行う。ここに出れば `.git/config` に書かれている。

### `~/.gitconfig` の `includeIf` を使わなかった理由

`~/.gitconfig` に以下を書くと、特定ディレクトリ配下のリポジトリだけ別の設定を適用できる。

```ini
[includeIf "gitdir:~/src/"]
    path = ~/.gitconfig-src
```

便利だが、**Dev Container 内ではパスが `/workspaces/...` になるためパターンに一致せず効かない**。リポジトリローカル設定なら `.git/config` ごと bind mount されるので、ホストでもコンテナ内でも同じ ID が効く。今回はそちらを採用した。

---

## `user.name` / `user.email` は何なのか

**コミットに埋め込まれる著者情報の文字列**であり、認証とは無関係。

Git は分散型で、中央サーバに登録されたアカウントという概念を持たない。そのため誰が書いたかを各コミットに自己申告で記録する。GitHub 等への push の認証（SSH 鍵やトークン）とはまったく別の仕組み。

---

## `.gitignore` の否定パターン

`!` で始まる行は「無視の対象から外す」を意味する。

```gitignore
.vscode/*
!.vscode/settings.json
```

### ディレクトリごと無視すると中身を復活できない

`.vscode/` と書くと git は**そのディレクトリの中を走査しなくなる**ため、後続の `!.vscode/settings.json` が効かない。中の一部を追跡したい場合は `.vscode/*` とファイル単位で無視する必要がある。

`.env` / `!.env.example` も同じ関係。

### `.vscode/` をコミットする理由

`settings.json` / `launch.json` / `extensions.json` / `tasks.json` は個人の好みではなく**プロジェクトの開発環境定義**なので追跡する。GitHub 公式の `.gitignore` テンプレートもこの4つだけを例外扱いにしている。

---

## `.editorconfig` の役割

文字コード・改行コード・インデントをエディタ横断で統一する仕組み。多くのエディタが標準またはプラグインで対応している。

フォーマッタ（後で入れる ruff）は Python しか整形しないため、YAML・JSON・Markdown まで含めて足並みを揃える役割を担う。

`Makefile` だけ `indent_style = tab` にしているのは、**Makefile はタブでないと構文エラーになる**ため。
