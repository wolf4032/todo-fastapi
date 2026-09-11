# SQLAlchemy: クエリの組み立てと `scalar` / `scalars`

## `select()` はSQL文字列ではなく、文を表現するオブジェクト

```python
stmt = select(Todo).where(Todo.is_completed == True).order_by(Todo.id).limit(10).offset(0)
```

`select(Todo)` はその場でDBに問い合わせるわけではない。SQLの「文（statement）」を表す**Pythonオブジェクト**を作るだけで、`.where()` / `.order_by()` / `.limit()` / `.offset()` は元のオブジェクトを書き換えるのではなく、条件が積み増された**新しいオブジェクト**を返す（文字列の `.replace()` が新しい文字列を返すのと同じ発想）。実際にDBへ送信・実行されるのは、`AsyncSession` の `execute()` / `scalar()` / `scalars()` を呼んだ時点。

変数名の `stmt` はこの「statement（文）」の略で、SQLAlchemyのドキュメント・コミュニティで定着した慣習的な命名。

## `scalar` の意味は線形代数とは別物

線形代数の「スカラー」（大きさのみで向きを持たない量、ベクトルとの対比）とは異なる文脈の用語。SQL/DBでの「スカラー」は、**「行（複数列のタプル）」や「結果セット（複数行）」に対する、単一の値**という意味で使われる。

| メソッド | 返す形 | 使いどころ |
|---|---|---|
| `db.execute(stmt)` | 各行を `Row`（列のタプル）として返す | `select(Todo.id, Todo.title)` のように複数列を選ぶとき |
| `db.scalar(stmt)` | 最初の行・最初の列だけを取り出した**単一の値** | `select(func.count()).select_from(Todo)` のように結果が1行1列に定まるとき |
| `db.scalars(stmt)` | 各行の**最初の列だけ**を取り出した値の並び（`Row` の入れ物を剥がす） | `select(Todo)` のように「1列 = エンティティ1つ」の形で複数行を受け取るとき |

`select(Todo)` は「1行につき列が `Todo` エンティティ1つだけ」という特殊な形のSELECTなので、`scalars()` で `Row(Todo,)` という入れ物を剥がし、`Todo` オブジェクトを直接受け取れる。`select(Todo.id, Todo.title)` のように複数列を選んだ場合は `scalars()` は先頭列（`id`）しか返さないため使えず、`execute()` で `Row` のまま受け取ることになる。

→ 使用例: [step-08-todo-crud-remainder.md](step-08-todo-crud-remainder.md)
