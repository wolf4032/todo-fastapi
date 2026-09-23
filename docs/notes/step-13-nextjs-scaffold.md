# Step 13: Next.js の雛形と devtools の Node 環境

作成物: `frontend/`（`create-next-app` の生成物 + `package-lock.json`）
変更: `.devcontainer/Dockerfile`、`.devcontainer/devcontainer.json`、`compose.override.yaml`、`.vscode/settings.json`、`.vscode/extensions.json`、`.editorconfig`

---

## 生成の手順

```bash
npx create-next-app@latest frontend --ts --app --eslint --tailwind --use-npm --skip-install --disable-git --yes
git add frontend
npm install --package-lock-only --prefix frontend
git add frontend/package-lock.json
```

- **`--skip-install` を付けた理由**: この時点では `frontend/node_modules` 用のボリュームがまだ無い。そのままインストールすると、数百パッケージぶんのファイルがバインドマウント越しにホスト（macOS）へ書き出される
- **`--package-lock-only`**: 依存を解決して `package-lock.json` を書くだけで、`node_modules` は作らない。これで `npm ci` に渡す lock ファイルが先に手に入る
- 生成直後にステージしたので、以降の手直しは `git diff` で区別できる（→ [topic-scaffold-generators.md](topic-scaffold-generators.md)）

`frontend/AGENTS.md` と `frontend/CLAUDE.md` も生成される。AI エージェント向けの注意書きで、「この版の Next.js は学習データと違う可能性があるので、`node_modules/next/dist/docs/` を読んでから書け」という内容。`next dev` が再生成するので残しておく。

## npm と uv の対応

| 目的 | uv | npm |
|---|---|---|
| 依存の宣言 | `pyproject.toml` | `package.json` |
| 解決済みの全依存 | `uv.lock` | `package-lock.json` |
| 追加（lock も更新） | `uv add` / `uv add --group dev` | `npm install <pkg>` / `npm install --save-dev <pkg>` |
| lock どおりに入れ直す | `uv sync --frozen` | `npm ci` |
| 一時的に取得して実行 | `uvx` | `npx` |

`npm ci` は lock ファイルを書き換えず、`package.json` と食い違っていればエラーにする。既存の `node_modules` は丸ごと消して入れ直す。`postCreateCommand` に置くのはこちら。

## `node_modules` を名前付きボリュームに載せる

```yaml
# compose.override.yaml（devtools）
- .:/workspaces/todo-fastapi
- frontend-node-modules:/workspaces/todo-fastapi/frontend/node_modules
```

バインドマウントの内側のパスに、別のボリュームを重ねてマウントしている。コンテナからは Linux のファイルシステム（`mount` で見ると `ext4`）として見え、ホストとは同期しない。ホスト側には中身の無い `frontend/node_modules/` だけが現れる（`frontend/.gitignore` で無視済み）。

所有者の問題は Step 2 の `.claude` と同じで、`.devcontainer/Dockerfile` でディレクトリを vscode 所有で先に作っておけば解決する。マウント先がバインドマウントの内側でも、ボリュームの初回作成時にコピーされるのは**イメージ側**のそのパスの中身なので、この対処が効く（→ [topic-docker-volumes.md](topic-docker-volumes.md)）。

### 中身はイメージではなくボリュームにある

イメージにあるのは空のディレクトリだけで、中身は `postCreateCommand` の `npm ci` がボリュームへ書き込んだもの。そのため `git pull` などで `package-lock.json` が新しくなっても、ボリュームの中身は古いまま残る。新しい依存の import に `Cannot find module` の波線が出て、`npm run lint` / `typecheck` も落ちる。

直すのにリビルドは要らない。`devtools` のターミナルで lock どおりに入れ直せばよい（`backend/.venv` に対する `uv sync` と同じ関係）。

```bash
npm ci --prefix frontend
```

`devtools` の `node_modules` はエディタ（補完・波線・ESLint 拡張）のためのもの。`web` コンテナは Step 14 で自分の `node_modules` を別に持つ。backend で `api` の `/opt/venv` と `devtools` の `backend/.venv` を分けているのと同じ構図。

## `allowScripts`（依存のインストールスクリプトの許可制）

npm 11 系は、依存パッケージの `postinstall` などを既定で実行しない。「入れただけで任意のコードが走る」仕組みがサプライチェーン攻撃によく使われてきたため。許可したものだけを `package.json` の `allowScripts` に書く。

今回引っかかった `unrs-resolver` は、`eslint-config-next` → `eslint-import-resolver-typescript` 経由で入る、import のパス解決を担う Rust 製の部品（依存の経路は `npm explain unrs-resolver` で見られる）。postinstall は「OS 用のネイティブバイナリが入らなかった場合に後から取る」保険にすぎない。バイナリ（`@unrs/resolver-binding-linux-arm64-gnu`）は通常の依存として入っていて、`npm run lint` も通ったので不要と判断した。確認済みであることを残すため、明示的に拒否した。

```bash
npm install-scripts deny unrs-resolver --prefix frontend
```

## エディタ設定

- **Prettier**: `npm install --save-dev --save-exact prettier`。パッチ版の更新でも整形結果が変わりうるので、公式が版の完全固定を推奨している。Prettier 拡張は `node_modules` の版を優先して使うので、エディタとコマンドラインで結果がずれない
- **ESLint 拡張**: 既定ではワークスペースのルートで設定ファイルを探す。`eslint.workingDirectories` で `frontend/` を指定した
- **`.editorconfig` の JS/TS/CSS を 2 幅に**: Prettier は自前の設定ファイルが無いと `.editorconfig` を読む。全体の既定値 4（Python 向け）のままだと、生成物が全部インデントし直される。2 幅は JS/TS 界隈の慣習で、公式の決まりではない（Python の 4 は PEP 8 が決めている）
- **`eslint-config-prettier` は入れていない**: Next.js の ESLint 設定には書式のルールがほぼ無く、Prettier とぶつからないため

## 症状と対処

### Tailwind のクラスに黄色い波線（`w-[100px]` can be written as `w-25`）

Tailwind 拡張の提案で、エラーではない。v4 の間隔は `1` = 4px なので、`[100px]`（任意値の記法）は `25` と書ける。雛形の `page.tsx` は Step 15 で書き換えるのでそのままにした。

### `tsc --noEmit` で `Cannot find name 'LayoutProps'`

`LayoutProps` / `PageProps` は、Next.js がルート構成から生成するグローバル型。`next dev` / `next build` / `next typegen` のどれかを実行するまで `.next/types/` に存在しない。開発サーバーを動かさない場所（CI など）でも通るよう、生成してからチェックするスクリプトを足した。

```bash
npm pkg set scripts.typecheck="next typegen && tsc --noEmit" --prefix frontend
```

## 確認したこと

- Rebuild Container 後、`frontend/node_modules` が `ext4` でマウントされ、所有者は `vscode`
- `app/page.tsx` で型の波線が出ず、`<Image` のホバーで型情報が出る。インデントを崩して保存すると戻る
- `npm run lint --prefix frontend` と `npm run typecheck --prefix frontend` が通る
