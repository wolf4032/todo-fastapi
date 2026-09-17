# Step 9: テスト

作成物: `backend/tests/conftest.py`（テスト用DBの準備、トランザクションロールバック、`dependency_overrides`、`AsyncClient`）、`backend/tests/unit/test_schemas.py`、`backend/tests/integration/test_todos_api.py`、`Makefile`（`test` ターゲット）

テストを書くにあたって初出だった一般知識は、ステップをまたいで参照するものとして切り出した。

- ソケット / HTTP / WSGI・ASGI / httpx・`ASGITransport` → [topic-web-protocol-basics.md](topic-web-protocol-basics.md)
- `python -m` と `sys.path` → [topic-python-module-execution.md](topic-python-module-execution.md)

ここでは backend 固有の判断とつまずきを扱う。

---

## テストピラミッドと unit / integration の分離

- **単体テスト（unit）**: 外部（DB・ネットワーク）に依存せず、1つの部品の入出力だけを見る。数が多く、速い
- **結合テスト（integration）**: 実際のDBを介して、部品同士が繋がった状態のふるまいを見る。数は少なく、遅い

「数の多い単体テストを土台に、遅い結合テストを少数だけ上に積む」という比率のイメージがテストピラミッド。

ディレクトリで分けておくと、**呼び出し分けができる**ことが最大の実益になる。CI では「速い `unit/` は全ジョブ・全プッシュで回し、DBサービスの起動が要る `integration/` は必要なジョブでだけ回す」といった使い分けができる。1つのディレクトリに混ぜていると、この切り分けに毎回テスト名の指定が必要になる。

今回の分類は次のとおり。

- `tests/unit/test_schemas.py` … Pydantic スキーマの検証ロジックだけを見る。DB接続なし
- `tests/integration/test_todos_api.py` … API のふるまい（ステータスコード、ページネーション、絞り込み、404変換）を実DB越しに見る

## テスト用DBを分ける

`conftest.py` の**冒頭**で、`app` 配下より先に接続先を上書きしている。

```python
os.environ["POSTGRES_DB"] = "todo_test"
```

`app.core.config.settings` は**モジュール import 時に一度だけ生成されるシングルトン**なので、この行が後続の import より前にあることが必須。順番が逆だと開発用DB（`todo`）を向いたまま固まり、テストが開発中のデータを壊す。

テスト用DBの準備はセッション全体で1回だけ（`scope="session", autouse=True`）行う。

1. `todo_test` が無ければ作成する。まだそのDBには繋げないので、管理用DB（`postgres`）に接続して `CREATE DATABASE` を発行する。`CREATE DATABASE` はトランザクション内で実行できないため `isolation_level="AUTOCOMMIT"` が要る
2. Alembic を**Pythonから直接呼んで**（`command.upgrade(Config("alembic.ini"), "head")`）スキーマを適用する。本番と同じマイグレーションを通すので、「テストは通るが本番のスキーマと違う」が起きない

`Base.metadata.create_all()` で作らないのは Step 6 と同じ理由。→ [topic-alembic-basics.md](topic-alembic-basics.md)

## トランザクションロールバックでテストを汚さない

テストごとにデータを消す（`DELETE FROM`）方式ではなく、**そもそもコミットを確定させない**方式をとっている。

```python
async with test_engine.connect() as connection:
    await connection.begin()                       # 外側のトランザクション
    async with AsyncSession(
        bind=connection, join_transaction_mode="create_savepoint"
    ) as session:
        yield session
    await connection.rollback()                    # まとめて巻き戻す
```

`join_transaction_mode="create_savepoint"` により、CRUD層の `db.commit()` は**外側のトランザクションの確定ではなく、内側の SAVEPOINT の解放**として扱われる。そのため

- テスト中は `commit()` 済みのデータが普通に読める（APIは本番と同じコードのまま動く）
- テスト終了時に外側を `rollback()` すれば、commit 済みの変更ごと消える

という両立ができる。後片付けのコードを1行も書かずに、テスト間の独立が保たれる。

## `dependency_overrides` でテスト用セッションを注入

`client` フィクスチャが `app.dependency_overrides[get_db]` を差し替えることで、エンドポイントは上記のトランザクション内セッションを受け取る。Step 5 で `get_db` を `Depends` 経由にしていたからこそ、テスト側だけこの1行で差し替えられる。仕組みは → [topic-fastapi-dependency-injection.md](topic-fastapi-dependency-injection.md)

## テストは `api` コンテナで実行する

`make test` は `docker compose exec api python -m pytest`。ツールボックス（`devtools`）ではなく `api` コンテナ（dev ステージ）で走らせることで、開発・テスト・CI の実行環境が同一になる。`python -m` である理由は → [topic-python-module-execution.md](topic-python-module-execution.md)

---

## 症状と対処: イベントループをまたいだDB接続の再利用

最初の実行で、**DBに触る結合テストが最初の1つを除いて全部落ちた**。

```
tests/integration/test_todos_api.py .F.FF
```

| # | テスト | 結果 | DBに触るか |
|---|---|---|---|
| 1 | `create_and_get_todo` | 成功 | ○（最初にDBを使う） |
| 2 | `get_missing_todo_returns_404` | 失敗 | ○ |
| 3 | `create_with_empty_title_returns_422` | 成功 | **✗**（バリデーションで弾かれDBに到達しない） |
| 4 | `list_todos_with_pagination_and_filter` | 失敗 | ○ |
| 5 | `update_and_delete_todo` | 失敗 | ○ |

単体テストは全て成功。「**DBに触るテストが、最初の1つを除いて全部落ちる**」というパターンが手がかりになった。

```
RuntimeError: ... got Future <Future pending ...> attached to a different loop
asyncpg ...: cannot perform operation: another operation is in progress
[SQL: SAVEPOINT sa_savepoint_1]
```

**原因**: pytest-asyncio は**テストごとに新しいイベントループ**を作る（実行時の出力に `asyncio_default_test_loop_scope=function` と表示される）。一方 `app/db/session.py` の `engine` は import 時に1つだけ作られ、**コネクションプールに接続を保持して使い回す**。1つ目のテストで開かれた接続はそのテストのイベントループに紐づいているため、2つ目以降のテストが別のループからそれを使おうとした瞬間に asyncpg が拒否する。`another operation is in progress` は「asyncpg の接続1本につき同時に実行できる操作は1つ」という制約に引っかかったもの。

**対処**: テスト専用エンジンを `NullPool` で作る。

```python
test_engine = create_async_engine(settings.database_url, poolclass=NullPool)
```

`NullPool` は接続を保持せず毎回開いて閉じるプールなので、ループをまたいだ再利用が原理的に起きない。`migrations/env.py` が使っているものと同じ（→ [topic-alembic-basics.md](topic-alembic-basics.md)）。テスト中のDBアクセスは `dependency_overrides` でこのエンジン由来のセッションに寄せているため、アプリ側の `engine` はテストでは使われない。

## 残った警告

```
StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated.
Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
```

`core/exceptions.py` が使っている定数名が非推奨になったもの。動作に影響はないが、警告の整理は静的解析をまとめて入れる Step 10 で扱う。

---

## 確認して分かったこと

- `pytest` を直接叩くと `ModuleNotFoundError: No module named 'app'` になり、`python -m pytest` なら通る（`sys.path` の先頭の違いを実測で確認）
- 初回実行でDBに触るテストが3つ失敗 → イベントループとコネクションプールの噛み合わせが原因と特定 → `NullPool` で解消
- 理解確認の問い「`unit/` と `integration/` を分けておくと CI でどう活きるか」への回答: 数が多く実行が速い unit と、DB接続を必要とし数が少なく実行の遅い integration を切り分けられるので、CI で適宜呼び出し分けができる
