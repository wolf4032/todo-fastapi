# Step 17: GitHub への push と CI

作成物: `.github/workflows/ci.yml`
変更: `Makefile`、`README.md`

---

## CI とは

CI（継続的インテグレーション）は、push のたびに検査を自動で走らせる仕組み。手元で `make lint` を忘れても、壊れた変更は push した時点で分かる。GitHub Actions は GitHub に組み込まれた CI で、`.github/workflows/` に YAML を置くだけで動く。

| 用語 | 意味 | 今回の例 |
|---|---|---|
| ワークフロー | YAML ファイル1つ。「いつ（`on:`）何をするか」 | `ci.yml` |
| ジョブ | 1台のマシンで行う作業のまとまり。ジョブ同士は別々のマシンで同時に動く | `check`（lint と test）、`build-prod`（prod イメージのビルド） |
| ステップ | ジョブの中で上から順に実行するコマンド1つ。1つ失敗するとジョブが失敗する | `cp .env.example .env`、`make lint` |

**CI のマシンは毎回まっさら**。手元にあるイメージ・`.env`・ボリュームは一切無いので、リポジトリの取得（`actions/checkout`）→ `.env` の作成 → コンテナのビルドと起動、を省かずに書く。

## 書いたもの

- **CI には「コンテナを立てて make を呼ぶ」ことだけを書いた**: 検査の中身は Makefile にあるので、手元と CI で同じ定義が動く（Step 10 の方針）
- **フロントの lint と typecheck を `make lint` に入れた**: CI では devtools を立てないので、backend と同じく web コンテナの中で走らせる。手元の `make lint` でもフロントが検査されるようになった
- **`docker compose up -d --build --wait db api web`**: サービスを列挙して devtools（約 2GB）を立てない。`--wait` は healthcheck が通り全サービスが起動し終わるまで待つ
- **`permissions: contents: read`**: ワークフローには GitHub を操作する権限が自動で渡されるので、読むだけに絞った
- **`if: failure()` でログを出す**: CI のマシンは終わると消え、後から中を調べられないため
- **`make prod-build`**: 起動はせず、prod イメージがビルドできることだけを確かめるターゲット

`docker compose exec` は端末に繋がっていないと自動で端末を割り当てない動きをするので、CI でも `-T` 無しで動いた。

初回の実行は `lint と test`・`prod イメージのビルド` とも約1分で成功した。

## 公開前にやったこと

### コミットのメールアドレスを隠した

公開リポジトリでは、コミットに記録されたメールアドレスを誰でも見られる（`git log`、コミット URL の末尾に `.patch`）。GitHub の Settings → Emails で **Keep my email addresses private** を有効にすると、`<数字>+<ユーザー名>@users.noreply.github.com` の代わりのアドレスが使える。**Block command line pushes that expose my email** も有効にすると、本物のアドレスが入ったコミットの push を GitHub が拒否する。

push 前だったので、`git config user.email` を代わりのアドレスにしたうえで、全コミットを書き換えた。

```bash
git rebase --root --exec 'GIT_COMMITTER_DATE="$(git log -1 --format=%aI)" git commit --amend --no-edit --no-verify --author="wolf4032 <$(git config user.email)>"'
```

- `--exec` は、コミットを1つ作り直すたびにそのコマンドを実行する
- `--amend --author=...` で作者を付け替える。committer は `user.email` から自動で新しいアドレスになる
- 作り直すとコミット日時が「今」になるので、`GIT_COMMITTER_DATE` に元の日時（author date）を入れて戻した。ADR やノートの日付と履歴を揃えるため

### ファイルの中の Mac のユーザー名を消した

ファイルの中身は、今のファイルを直しても過去のコミットに残る。`git filter-branch --tree-filter` で全コミットのファイルを書き換えた。各コミットを一時ディレクトリに取り出してコマンドを実行し、コミットし直す（作者と日付は引き継がれる）。

```bash
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch --tree-filter "sh <置き換えスクリプト>" -- --all
```

書き換え前の履歴は `refs/original/` に残るので、確認後に `git update-ref -d refs/original/refs/heads/main` で消した。push で送られるのは `main` から辿れるコミットだけなので、元の履歴が GitHub に載ることは無い。

どちらの書き換えも、**push する前だから気軽にできた**。push 後に書き換えると、GitHub 側の履歴との食い違いを強制 push で上書きすることになり、他人が clone していればその人の履歴も壊れる。

### AWS のサインインと MFA

| | 何者か | サインインに使うもの |
|---|---|---|
| root ユーザー | アカウントそのもの。何でもでき、権限を制限できない | 作成時のメールアドレスとパスワード |
| IAM ユーザー | アカウントの中に後から作る利用者。権限を絞れる | アカウント ID（またはエイリアス）・ユーザー名・パスワード |

IAM ユーザーでアカウント ID を聞かれるのは、ユーザー名が「そのアカウントの中」でしか区別されないから。サインイン画面の初期表示がブラウザごとに違うのは、ブラウザが前回の方法を覚えているため。

- 2025年7月15日以降に作ったアカウントはクレジット制（最大 200 ドル・6ヶ月）。このアカウントは **Free プランで 2027年2月4日まで**。Free プランはクレジットを超えて請求されない代わりに、期限かクレジット切れでアカウントが閉じる
- **AWS Organizations を使うと Paid プランに自動で切り替わる**。普段使い用のユーザー作成でよく勧められる IAM Identity Center は Organizations を使うので、今は使わない
- root に MFA としてパスキーを登録した（保存先は Bitwarden）。パスキーはブラウザが本物の aws.amazon.com かを確かめてから認証するので、フィッシングが効かない。認証アプリの6桁は偽サイトにも入力できてしまう
- 認証アプリを登録するときの「連続した2つのコード」は、同じものを2回ではなく、30秒ごとに変わる数字の今の分と次の分。秘密の鍵が正しく読み取れたことと、時計がずれていないことを確かめている

#### つまずき: MFA の追加も削除も拒否された

`To complete this action, please ensure that you are authenticated with an MFA device that is enabled for this user.` と出た。MFA の追加・削除は **MFA でサインインしたセッション**からしか許可されず、パスキーを登録する前にパスワードだけでサインインしたセッションだったため。別のデバイスのブラウザからパスキーでサインインし直して解決した。

このとき Bitwarden のパスキーを消すのは危険。AWS 側には登録が残ったまま、出せる手段が無くなって閉め出される。どうしても MFA が通らないときは、MFA の画面の「トラブルシューティング」から、登録済みのメールと電話で本人確認して復旧する。

## push

VS Code の「Publish Branch」（VS Code の GitHub 連携で、リポジトリの作成と push をまとめて行う）は使わず、このリポジトリ専用のトークンで push した。

1. ブラウザで空の公開リポジトリを作る
2. **Fine-grained のアクセストークン**を、このリポジトリだけ・Contents と Workflows の Read and write で発行する。Workflows の権限は、`.github/workflows/` を含む push に別途要る。ワークフローは GitHub のマシンで実行されるので、トークンが漏れたときに勝手なワークフローを仕込まれないよう、権限が分けてある
3. 送り先の URL にユーザー名を入れる（`https://wolf4032@github.com/wolf4032/todo-fastapi.git`）。git はそのユーザー名の認証情報だけを探して使う
4. push はホストのターミナルで行い、パスワードの代わりにトークンを入れる

## 理解確認: 手元では通るのに CI で落ちるのはどんなときか

回答: `node_modules` などが無いとき。ただし `ci.yml` はそうならないように作ってある。

`node_modules` は CI でも Dockerfile の `npm ci` が `package-lock.json` から作るので、無くて落ちることは無い。一般化すると「**手元にはあるが、コミットされたものからは再現できないもの**」に頼っていると落ちる。CI が使えるのはリポジトリに入っているものだけ。

- **コミットし忘れたファイル**: 新しく作ったファイルを `git add` し忘れても、手元では存在するので通る。いちばん多い
- **lock ファイルのコミット忘れ**: `npm install` や `uv add` で依存を足したのに `package-lock.json` / `uv.lock` をコミットしていない。CI は古い lock から入れるので、足した依存が無い
- **`.gitignore` している手元の状態**: 手元の `.env` の値を書き換えていて、それを前提にしたテストを書いた。CI は `.env.example` の値で動く
- **手元に残った古い状態**: 手元のテスト用 DB やボリュームに前回のデータやテーブルが残っていて、たまたま通っている
- **マシンの違い**: 手元の Mac は ARM（arm64）、GitHub の標準のマシンは x86_64。ネイティブバイナリを含む依存や、時刻・タイムゾーンに依存するテストで差が出る

逆に言えば、CI が緑であることは「リポジトリだけから、まっさらな環境で再現できる」ことの証明になる。これが CI を置く価値。
