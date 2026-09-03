# FastAPI の `Depends()` と DI（依存性注入）の基礎

Step 7 で `api/deps.py` と `Depends(get_db)` を初めて意識的に扱った際に整理した基礎知識。

## HTTP リクエストとエンドポイント関数の対応

FastAPI は「メソッド（GET/POST など）＋パス」の組み合わせごとに Python 関数を1つ対応させる。リクエストが来ると、その組み合わせに一致する関数を実行し、返り値を JSON に変換してレスポンスにする。この対応付けは `@router.get(...)` / `@router.post(...)` のようなデコレータで宣言する。

## DI（Dependency Injection、依存性注入）とは

一般的な定義は「ある処理が必要とする外部の物（依存先）を、その処理自身が用意するのではなく、外から与えられるようにする」設計。これによりテスト時に依存先を本物ではない代替品に差し替えられる。Java の Spring などでは、クラスの `__init__`（コンストラクタ）で依存先を受け取り、オブジェクトが生きている間ずっと持ち回る形が多い。

FastAPI の `Depends()` も同じ核となる考え方だが、単位が違う。クラスではなく**関数呼び出し1回（＝1リクエスト）ごと**に依存先を作り、その場で引数として渡すだけの、より軽量な実装になっている。

```python
async def health_db(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
```

`health_db` は「`AsyncSession` が欲しい、どう作るかは知らない」とだけ言っている。実際に `get_db()` を呼んで `db` を用意するのは FastAPI 側の仕事。

## `yield` を使う理由（後片付けの保証）

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

`get_db` が `return` ではなく `yield` を使っているのは、エンドポイント関数の実行が終わった後（例外が起きた場合も含めて）、`yield` の続き（`async with` を抜ける処理＝セッションのクローズ）に自動的に戻ってくるため。「後片付けまで含めて FastAPI に任せられる」仕組みになっている。

## 具体的なメリット：テストでの差し替え（`dependency_overrides`）

DI の一番の実利は、依存先を丸ごと差し替えられること。

```python
app.dependency_overrides[get_db] = get_test_db
```

この1行で「`get_db` が要求されたら `get_test_db`（テスト用 DB に繋ぐ版）を使う」と指示できる。`health_db` や `create_todo` のコードは一切書き換えない。Step 9 のテストで実際に使う予定。

## `api/deps.py` を挟む理由

`deps.py` が集約しているのは「**`Depends()` に渡す関数（DI 対象）**」だけ。エンドポイント側は `app.db.session` のような実装の詳細を直接 import せず、`app.api.deps` という窓口だけを知っていればよい。将来 `get_current_user`（認証）を足すときも、この窓口に追加するだけで済み、既存エンドポイントの import 文は変更不要になる。

一方 `crud/todo.py` のような普通の関数呼び出しは対象外。**差し替えたいのは「セッションの作り方」であって「CRUD のロジック」ではない**（ロジックは本番でもテストでも同じであってほしい）ので、CRUD 関数自体を `Depends` にする必要はない。`db` はエンドポイントが `Depends(get_db)` で受け取ったものを、そのまま引数として CRUD 関数に渡すだけ。差し替えの起点は「セッションを作る場所（`get_db`）」1箇所に絞られる。

## URL はディレクトリ構造では決まらない

FastAPI はファイル名やディレクトリ構造を見ない。URL は次の「文字列の足し算」だけで決まる。

```
main.py:            app.include_router(api_v1_router, prefix="/api/v1")
v1/router.py:        router.include_router(todos_router)          # 追加のprefixなし
endpoints/todos.py:  APIRouter(prefix="/todos")
endpoints/todos.py:  @router.post("") / @router.get("/{todo_id}")
```

`endpoints/todos.py` というファイル名と `/todos` という URL が一致しているのは、あくまで人間が読みやすいように揃えている慣習であって、ファイル名を変えても `prefix="/todos"` が生きていれば URL は変わらない。

パスの `{todo_id}` のような部分は「パスパラメータ」で、実際に来た URL からその部分を抜き出し、型ヒント（`todo_id: int`）に従って変換したうえで関数の引数に渡す。変換できない値（例: `/todos/abc`）が来ると自動的に 422 になる。

## 同じ method + path を複数定義するとどうなるか

エラーにはならない。FastAPI（内部の Starlette）は登録順にルートを見て、最初に一致したものだけを実行する。後から定義した同じ組み合わせのハンドラは、登録はされるが一生呼ばれない「死んだコード」になる。起動時・実行時とも警告は出ないので、テスト（Step 9）で実際に叩いて確認することが唯一の安全網になる。

## `/api/v1` の意図

`/api` は「画面用ではなく API 用のパス」という慣習的な目印（将来同じサーバーでフロントを配信するとき区別しやすい）。`/v1` は API バージョニングで、既存クライアントを壊す変更をしたくなったとき `/api/v2` を新設して並走させ、`/api/v1` を使う既存クライアントを壊さずに済ませるための保険。`/v1` を付けない選択をしている現場もあるが、それは「クライアントを自社で完全に把握していて同時に更新できる」等の別のトレードオフを取っている、というだけで優劣の問題ではない。
