# SQLAlchemy: 宣言的マッピングの型ヒント、ORM/Core、`default`/`server_default`

## `Mapped[...]` の型ヒントが NOT NULL / nullable を兼ねる（2.0の書き方）

1.x系の記事でよく見る `Column(String(255), nullable=False)` という書き方は非推奨ではないが、型ヒントと二重管理になる。SQLAlchemy 2.0の宣言的マッピング（`Mapped[...]` + `mapped_column()`）では、**型ヒントそのものがNOT NULL制約を兼ねる**。

```python
title: Mapped[str] = mapped_column(String(255))       # NOT NULL
description: Mapped[str | None] = mapped_column(Text)  # nullable
```

`Mapped[str]`（Optionalでない）なら NOT NULL、`Mapped[str | None]` なら nullable、という対応。長さ・インデックス・デフォルトなど型ヒントで表現できない部分だけ `mapped_column()` の引数で補う。

## ORM と Core は別の層

- **Core**: `insert()` / `select()` / `Table` / `Column` を使い、Pythonのコードでクエリを組み立て、SQLに変換して実行する層。「SQLをPythonで組み立てて実行する」実務そのものはここが担う
- **ORM**: Coreの上に乗る層。**Pythonのクラス・インスタンスとDBのテーブル・行を対応付ける**のが仕事（`Todo` クラス ↔ `todos` テーブル）。`Session` が「どのオブジェクトが新規追加/変更されたか」を追跡し、`commit()` 時にまとめて Core 経由で `INSERT`/`UPDATE`/`DELETE` を発行する

`mapped_column(default=...)` の `default` は Column（テーブル定義）に紐づく Core レベルの機能で、ORM独自の仕組みではない。そのため `Session.add()` → `commit()` 経由でも、Core の `insert()` を直接呼ぶ経路でも、同じように効く。

## `default` と `server_default` の違い

名前が紛らわしいが、値を計算する場所が違う。

| 指定 | 値を計算する場所 | 実際にDBへ送られるSQL |
|---|---|---|
| `mapped_column(default=False)` | **SQLAlchemy（Python側）**。ORM/Core問わず、INSERT文を組み立てる段階で値を確定させる | `INSERT INTO todos (..., is_completed) VALUES (..., false)` のように、値そのものがSQL文に含まれる |
| `mapped_column(server_default=sa.text("false"))` | **DBサーバー自身**。DDLの `DEFAULT` 句に刻まれる | `INSERT INTO todos (title) VALUES ('x')` のように、その列ごと省略して送られる。DBが自分のDDLを見て埋める |

`server_default` を使うと、SQLAlchemyを経由しない書き込み経路（生SQL、他言語のクライアントなど）でも同じデフォルトが効く。`default` はSQLAlchemy経由の書き込みでしか効かない。

## 使い分けの基準：「唯一の権威」が要るかどうか

`created_at`/`updated_at` を `server_default=func.now()` にしたのは、**複数のアプリサーバーがそれぞれ自分のPythonの時計で「今」を計算すると、サーバー間で微妙にズレうる**ため。DBという単一の時計に権威を一本化する必要がある。

`is_completed=False` にはこの種のズレが原理的に存在しない。どこで計算しても `False` は `False`。なので「複数の書き込み元の間で値が食い違いうるか」で切り分けるとブレない（「SQLAlchemy経由でしか書き込まないから」という理由付けだと、将来書き込み元が増えたときに崩れる）。

## 権威が不要なら `server_default` をわざわざ使わない理由

必要ないから使わない、というだけでなく、積極的に避けたい実務上のコストもある。

1. **変更のたびにマイグレーションが要る**: `default=` はモデルの1行を書き換えるだけで完結する（マイグレーション不要）。`server_default` は `ALTER TABLE ... ALTER COLUMN ... SET DEFAULT ...` というマイグレーションを毎回起票する必要がある。単なる業務ルールの調整なのに、スキーマ変更と同じ手続きになる
2. **Alembicのautogenerateは`server_default`の変更を標準では検知しない**: DBが実際に持つデフォルト値を読み返すと、モデルの表現とバイト単位で一致しないことが多く（例: PostgreSQLは `false` を `'false'::boolean` のような形で保持・返却することがある）、そのまま比較すると誤検知しやすい。そのためAlembicは既定でこの比較を無効化しており、有効にするには `env.py` の `context.configure()` に `compare_server_default=True` を明示的に渡す必要がある（本リポジトリでは渡していない＝無効のまま）。つまり `server_default` を後から変更しても、**autogenerateは気づかず、手でマイグレーションを書く必要がある**
3. **DB方言依存のリテラル構文に縛られる**: `sa.text("false")` はPostgreSQL向けの書き方。DBが変わればリテラルの書き方も変わりうる

`default=` はDDLの一部ではないため、上記のどのコストも発生しない。
