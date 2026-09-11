# Step 8: 残りの CRUD（一覧・更新・削除）

作成物: `backend/app/schemas/todo.py`（`TodoUpdate` / `TodoListResponse`）、`backend/app/crud/todo.py`（`list_todos` / `update` / `delete`）、`backend/app/api/v1/endpoints/todos.py`（`GET /api/v1/todos`（一覧・ページネーション・`is_completed` 絞り込み）、`PATCH /api/v1/todos/{todo_id}`、`DELETE /api/v1/todos/{todo_id}`、共通ヘルパー `_get_todo_or_404`）

`select()` の組み立て方（`where`/`order_by`/`limit`/`offset` の連鎖）と `scalar`/`scalars` の用語は、ステップをまたいで参照する一般知識として切り出した。

- → [topic-sqlalchemy-querying.md](topic-sqlalchemy-querying.md)

ここでは backend 固有の設計判断を扱う。

---

## `TodoUpdate` を `TodoBase` から独立させた理由

`TodoUpdate` は全フィールドが省略可（PATCH の部分更新）。一見 `TodoBase` を継承して `title` だけオーバーライドすれば足りるように見えるが、そうしなかった。

理由は「将来 `TodoBase` に必須フィールド（例: `priority: str`）が増えたとき」を考えるとわかる。継承していると、`TodoCreate`/`TodoRead` は新フィールドをそのまま必須として受け継ぐ（これは望ましい）が、`TodoUpdate` も継承したままだと**オーバーライドし忘れて新フィールドまで必須になり**、PATCH で他のフィールドだけ送るとエラーになるという壊れ方をする。しかも継承元を見ないと気づきにくい。

`TodoUpdate` は「必須項目が弱くなった `Todo`」ではなく「`Todo` に対する差分・パッチ」という別概念であり、`TodoBase` の変更に巻き込まれないよう独立させた。

## 一覧の `total` は絞り込み後の件数

`list_todos()` は一覧取得用の `SELECT ... LIMIT/OFFSET` と、件数取得用の `SELECT count(*)` を別クエリで発行し、`is_completed` の `WHERE` 句は両方に同じ条件で適用する。`total` が「絞り込み後」の件数でないと、クライアントがページ数を正しく計算できない。

## PATCH と `exclude_unset=True`

- **PUT**: リソース全体を置き換える。送らなかったフィールドは削除された扱いになるのが原則
- **PATCH**: 差分だけを送る。送らなかったフィールドは変更しない

`todo_in.model_dump(exclude_unset=True)` は「リクエストJSONに実際にキーが存在したか」をPydanticが記録している情報を使って絞り込む。これを外すと、送らなかったフィールドもモデルのデフォルト値（`None`）で埋まってしまう。今回のモデルでは影響が2通りに分かれる。

- `title`（DB側でNOT NULL）: `None` を `setattr` した後の `commit()` で **DBがエラーを返して弾く**
- `description` / `due_date`（DB側でnullable）: エラーにならず**サイレントに `None` へ上書きされる**（呼び出し側が送っていないのに消える）

`exclude_unset=True` はこの両方の事故を防いでいる。

## DELETE が 204 を返す理由

204 No Content は「処理は成功したが返すボディが無い」ことを表す標準ステータス。削除後のリソースはもう存在しないので、返すべき表現が無い。`delete_todo` に `response_model` を指定していないのもそのため。

## `_get_todo_or_404` で404変換を集約

Step 7 では `read_todo` の中だけにあった「`None` → HTTP 404」変換が、`update_todo`/`delete_todo` にも必要になったため、エンドポイント層内のプライベート関数 `_get_todo_or_404` に集約した。404への変換をエンドポイント層に置くという設計判断自体はStep 7から変わらない。

---

## 確認して分かったこと

- `POST` を3件 → `GET /api/v1/todos?limit=2&offset=1` で2件目・3件目が返り、`total=4`
- `GET /api/v1/todos?is_completed=true` → 該当なしで `items: []`
- `PATCH` で `{"is_completed": true}` だけ送信 → `title`/`description` は元の値のまま維持され、`is_completed` だけ変わる（`exclude_unset=True` が効いている証拠）
- `DELETE` → `204 No Content`、ボディなし
- 削除後に同じ `id` を `GET` → `404`、統一エラー形式（`error.code`/`message`/`request_id`）で返る
- `/docs`（Swagger UI）の `todos` タグに `POST`/`GET`（一覧）/`GET`（単体）/`PATCH`/`DELETE` が並んだ
- 理解確認の問い「`exclude_unset=True` を外すと `{"is_completed": true}` だけ送ったとき何が起きるか」への回答: `title` はNOT NULL制約違反でDBがエラーを返して弾く。`description`/`due_date` はnullableなのでエラーにならず、送っていないのに `None` へ上書きされてしまう
