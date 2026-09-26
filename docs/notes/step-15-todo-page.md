# Step 15: TODO 画面

作成物: `frontend/lib/types.ts`、`frontend/lib/api.ts`、`frontend/components/todo-app.tsx`
変更: `frontend/app/page.tsx`（雛形を置き換え）、`frontend/app/layout.tsx`（タイトルと `lang="ja"`）

---

## 構成

```
app/page.tsx（Server Component）
└── components/todo-app.tsx（"use client"）
    └── lib/api.ts ── fetch("/api/v1/...") ──► web の rewrites ──► api:8000
```

| ファイル | 役割 |
|---|---|
| `lib/types.ts` | `TodoRead` などに対応する型。`datetime` は JSON では文字列なので `string` |
| `lib/api.ts` | `fetch` を包み、失敗を `ApiError` にそろえる。画面は HTTP の細部を知らなくてよい |
| `components/todo-app.tsx` | 一覧・追加・完了切り替え・削除。state を持つのでここだけ Client Component |

型は手で `schemas/todo.py` と揃えている。TypeScript の型は実行時に消えるので、API がずれても画面は型エラーにならず、実行時に壊れる。規模が大きくなったら FastAPI の OpenAPI（`/openapi.json`）から型を生成する（`openapi-typescript` など）のが定番。今回は型が4つしかないので見送った。

## Server Component と Client Component の境界

App Router の `page.tsx` / `layout.tsx` は、何も書かなければ **Server Component**。サーバーでだけ実行され、ブラウザにはその結果だけが届き、コンポーネントの JavaScript は送られない。

ファイルの先頭に `"use client"` を書くと、そのファイルと、そこから import したものが **Client Component** になり、JavaScript がブラウザに送られる。`useState`・`onClick`・`useEffect` はブラウザでしか意味を持たないので、これらを使うコンポーネントには必要。

指定の無いコンポーネントの扱い・`"use server"` との違い・`useEffect` の仕組み → [topic-react-components-and-effects.md](topic-react-components-and-effects.md)

今回は `page.tsx`（見出しだけ）を Server Component のまま残し、操作する部分だけを `TodoApp` に切り出した。`"use client"` はこの境界を宣言するもので、ここより下には付け直さなくてよい。

### Client Component も最初の HTML はサーバーで作られる

`curl web:3000` の HTML には `読み込み中…` まで入っている。Client Component も初回はサーバーで一度描画して HTML にし、ブラウザではその HTML にイベントハンドラを取り付ける（**hydration**。Step 14 の Dark Reader の件で出てきたもの）。「Client」は「ブラウザ**でも**動く」の意味で、「ブラウザ**でしか**動かない」ではない。

`useEffect` の中身だけは hydration の後にブラウザで実行される。だから一覧の取得はブラウザから行われ、相対 URL の `/api/v1/todos` がそのまま使える。

### Server Component で一覧を取得しなかった理由

Server Component の `async` 関数で `await fetch(...)` すれば、最初の HTML に一覧を入れられる。今回そうしなかったのは次の理由。

- **相対 URL が使えない**: 相対 URL は「基準の URL」と組み合わせて初めて完全な URL になる。ブラウザでは今開いているページ（`http://localhost:3000/`）が基準になるが、サーバー（`web` コンテナ内の Node.js）で動くコードには基準にするページが無い。`fetch("/api/v1/todos")` はリクエストを送る前に `TypeError: Failed to parse URL` で失敗する。`web` と `api` が別コンテナであることとは関係ない
- **rewrites は「受け取る側」の仕組み**: `next.config.ts` の rewrites は、Next.js のサーバーが**外から受け取った**リクエストを転送する。Server Component のコードは Next.js のサーバーの中で動いているので、そこから出ていくリクエストは rewrites を通らない。結局 `http://api:8000` を直接書くことになり、ブラウザ用（`/api/...`）とサーバー用で API の URL が2通りになる
- **ビルド時に API へ繋ぎにいく**: 動的な値を使わないページは `next build` 時に事前描画される。Step 16 の本番イメージのビルド中には `api` がいないので、取得を実行時に回す設定が別途要る
- 追加・更新・削除はどのみちブラウザから呼ぶので、画面の状態をブラウザ側に一本化した方が単純

一覧が大きい・SEO が要る・初回表示を速くしたい、となれば Server Component での取得を検討する。

## `async` を付ける関数・付けない関数

`request()` は `async` で、`listTodos()` などは `async` を付けずに `request()` の戻り値をそのまま `return` している。

- `async` が必要なのは、**関数の中で `await` して結果を使う**とき。`request()` は応答を待って `res.ok` やステータスを調べるので要る
- `listTodos()` は結果を使わず、`request()` が返した Promise（「あとで値が入る箱」）を呼び出し元へ渡すだけ。待つのは箱を開ける人、つまり呼び出し元の仕事
- `async` 関数は必ず Promise を返すので、付けても付けなくても呼び出し元から見た型（`Promise<TodoListResponse>`）は同じ。付けると箱を一度開けて詰め直す手間が増えるだけ
- `useEffect` の中で `await` ではなく `.then()` を使ったのは、`useEffect` に渡す関数は「何も返さない」か「後片付けの関数を返す」決まりだから。`async` にすると Promise を返してしまう

Python でも同じで、`async def` の関数を `return` で渡すだけなら中継役は `async` でなくてよい（Python と JS の実行タイミングの違い → [topic-async-await.md](topic-async-await.md)）。

## エラーの扱い

ステータスコードの意味 → [topic-http-status-codes.md](topic-http-status-codes.md)

`lib/api.ts` で、失敗を3種類に分けて全部 `ApiError` にしている。

| 状況 | 見分け方 | `ApiError` |
|---|---|---|
| 応答が得られない（ネットワーク断など） | `fetch` が reject する | `status: 0`, `code: "network_error"` |
| FastAPI のエラー | 本文が `{"error": {...}}` | `status` と `code` / `message` / `request_id` / `details` をそのまま |
| それ以外（`api` 停止中に Next.js が返す 500 など） | 本文が JSON として読めない | `code: "unknown_error"` |

- **`fetch` は 4xx/5xx では reject しない**: `fetch` が失敗とみなすのは「HTTP の応答を受け取れなかった」ときだけで、404 も 500 も「応答は受け取れた」ので成功として resolve する。`res.ok`（200〜299 なら true）を自分で見る必要がある。HTTP のステータスをどう解釈するかはアプリの都合なので、`fetch` は決めつけない、という設計。たとえば「この名前はもう使われているか」を調べる画面なら、404 は「空いている」という正常な答えになる。resolve されるので、ステータス・ヘッダ・本文（エラーの詳細）を読んで次の対応（直して送り直す・時間をおいて再試行するなど）を決められる
- **422 は `details` を並べる**: FastAPI（Pydantic）の検証エラーは `details` に `loc`（`["body", "title"]` のような位置）と `msg`（理由）が項目ごとに入る。`title: String should have at least 1 character` のように表示する
- **404 は画面からも消す**: 別のタブや `curl` で先に消されていた TODO を操作すると 404 になる。サーバーに無いものを画面に残しても操作できないので、ステータスで分岐して一覧から取り除く。エラーを「文言を出す」だけでなく「状態を直す」きっかけに使う例
- **`request_id` を保持している**: 画面には出していないが、`ApiError.requestId` に入る。問い合わせを受けたとき、api のログ（Step 5 の構造化ログ）と突き合わせるための値

## 更新後の state

更新・作成では、ローカルで `is_completed` を反転させるのではなく、**API が返した `Todo` で置き換える**。どちらの書き方でも PATCH は送る。違うのは「画面に何を出すか」で、正しい状態を持っているのはサーバー（DB）なので、その答えをそのまま使う。

- **サーバーでしか決まらない値がある**: `updated_at` は DB が更新した時刻で、ブラウザで反転させただけでは分からない
- **失敗したときに画面が嘘をつく**: 先に画面だけ反転させて PATCH が 404 や 500 で失敗すると、画面は完了・DB は未完了という食い違いが残る

代わりに応答を待つぶん反映がわずかに遅れる。先に画面だけ変える「楽観的更新」という手もあるが、失敗したときに元へ戻す処理が別に要る。

## 症状と対処

### 開発中は一覧の GET が2回飛ぶ

`docker compose logs api` を見ると、ページを開くたびに `GET /api/v1/todos` が2回出る。App Router の開発モードでは React の Strict Mode が有効で、`useEffect` を「実行 → 後片付け → もう一度実行」する。後片付けを書き忘れた `useEffect`（二重登録・古い応答による上書き）を開発中に表に出すための仕様で、本番ビルドでは1回になる。

`todo-app.tsx` の `ignore` フラグがその後片付け。1回目の応答が後から届いても state を書き換えないようにしている。

## 確認したこと

- 画面から追加・完了切り替え・削除を行うと、`curl localhost:8000/api/v1/todos` と `psql` の `SELECT` に同じ内容が見える
- `curl -X DELETE` で先に消した TODO を画面で切り替えると、api のログに `PATCH /api/v1/todos/3` の 404 が出る
- ページを開くと、api のログに `GET /api/v1/todos?limit=100` が同じ秒に2回出る（Strict Mode）
- api のログの送信元が、画面からの操作は `172.18.0.5`（web コンテナ）、ホストの `curl` は `192.168.65.1`（Docker Desktop 経由のホスト）になっている。画面のリクエストが rewrites を通って web から届いていることが分かる
- `docker compose stop api` の状態で追加すると 500 になる。api が応答したのではなく、api に繋がらなかった web（Next.js）が代わりに 500 を返している。応答自体は届くので `fetch` は reject せず、`ApiError` の `unknown_error` になる。意味としては「中継先が応答しない」を表す 502 Bad Gateway の方が正確だが、Next.js の開発サーバーは 500 を返す
