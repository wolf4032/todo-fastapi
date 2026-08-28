# Alembic の基本的な仕組み

## なぜ `Base.metadata.create_all()` ではなく Alembic か

`create_all()` は「今のモデル定義を見て、まだ存在しないテーブルを `CREATE TABLE`（DDLの一種。テーブル構造を定義するSQL。データを操作する `INSERT`/`UPDATE`/`SELECT` などのDML＝Data Manipulation Languageとは別物）する」だけの機能。**既に存在するテーブルには何もしない。** 運用中のテーブルにカラムを追加しても、`create_all()` は「もうテーブルはある」と判断して何も反映しない。空のDBを初めて作るときにしか使えない。

Alembicは `ALTER TABLE` を使ったマイグレーションを生成・適用できるので、**データが入った既存のテーブルを安全に少しずつ変更していける**のが決定的な違い。これが無いと、本番のデータを消さずにスキーマを進化させる手段が無くなる。

副次的な利点として、各変更が `revision`・メッセージ・日時付きのファイルとして残るため変更履歴を追え、`downgrade()` で特定の変更を打ち消せる（ただし構造のみ、データは戻らない）。

## `alembic_version` テーブルと履歴の持ち方

`alembic upgrade head` を初めて実行すると、DBに `alembic_version` テーブルが自動で作られる。ここには**「今どのリビジョンにいるか」を指す1行だけ**が入る（例: `"9181c9c00bed"`）。

履歴（どのリビジョンがどの順で適用されてきたか）はDBには無い。**各 `migrations/versions/*.py` の `down_revision`（1つ前のリビジョンID）による連結リストとして、コードの側に存在する。** `alembic history` でこの連結リストを辿って一覧表示できる。

Djangoの `django_migrations` テーブル（適用済みマイグレーション1件につき1行、全件をDB側に記録）とは記録の仕方が違う。Alembicは「現在地の1点」だけをDBに持ち、経路はコードで管理する設計。

## `downgrade()` は「巻き戻し」ではなく「逆方向のDDLを新たに実行する処理」

DBに「過去の状態に戻す」機能があるわけではない。`downgrade()` は `upgrade()` が行った操作の**逆操作を新たに実行するコード**（`op.create_table` の逆は `op.drop_table` など）。`--autogenerate` はこの逆操作を検出した変更から自動生成する。

**構造は復元できてもデータは復元できない**点に注意。例えば `upgrade()` が `op.drop_column` でカラムを消していた場合、`downgrade()` の `op.add_column` で列自体は復活しても、そこに入っていた値は失われたまま。

## `alembic downgrade -N` の動作

1. `alembic_version` から現在地のリビジョンを取得
2. `down_revision` の連結リストをN個分遡り、目標リビジョンを決定
3. 現在地から目標まで、各リビジョンの `downgrade()` を新しい方から古い方へ順に実行
4. 完了後、`alembic_version` を目標リビジョンで更新

今回のリポジトリはまだリビジョンが1本（`down_revision: None`）だけなので、`downgrade -1` は「何も無い状態」まで戻り、そのファイルの `downgrade()` が1回実行されるだけ。

## `autogenerate` は実際のDBとの差分を見る

`alembic revision --autogenerate` は、`env.py` が実際にDBに接続し、SQLAlchemyの `Inspector` で**今のDBに存在するテーブル・カラムをそのまま読み取り**（リフレクション）、それと `target_metadata`（`Base.metadata`）を比較して差分を検出する。

Djangoの `makemigrations` とは比較対象が逆で、こちらはDBに接続せず、**過去のマイグレーションファイル群を再生して仮想的な期待スキーマを再構築**し、それを `models.py` と比較する。

### だから `--autogenerate` は必ず DB が `head` の状態で実行する

`autogenerate` は「今のDBの実物」と `target_metadata` しか見ておらず、**マイグレーションファイルが何本あるか・過去に何をしたかという「意図の履歴」は一切考慮しない。** そのため、DBを過去のリビジョンまで `downgrade` した状態（例: 最初まで戻してテーブルが1つも無い状態）で `--autogenerate` を実行すると、「モデルにはあるがDBに無い」という差分がまた検出され、既存のマイグレーションと同じ内容（例: `op.create_table('todos', ...)`）を含む**新しいファイルが重複して生成されてしまう**。

しかもこの新しいファイルの `down_revision` は、DBの現在地ではなく `migrations/versions/` 内のファイル群のheadを見て決まるため、既存のファイルの直後に繋がる形で生成される。結果として、最初から `upgrade head` すると1本目でテーブルが作られた直後に2本目が同じテーブルをまた作ろうとして `relation "todos" already exists` のようなエラーで失敗する。

教訓: **`downgrade` は動作確認やロールバック用の操作であり、「マイグレーションを作り直す前のリセット」として使ってはいけない。`--autogenerate` は常にDBが `head`（それまでの全マイグレーション適用済み）の状態で実行する。**

### 変更を取り消したいときの正しい手順

「取り消したい変更が既に共有されているか」で手順が変わる。Gitの「pushして共有した後のコミットは書き換えず、revertで打ち消す」という考え方と同じ構造。

- **まだ誰にも共有していない場合**（コミット前、pushもしていない、他の環境で `upgrade` もされていない）: 単純に `downgrade` → **そのマイグレーションファイル自体を削除** → モデルを修正 → 改めて `--autogenerate` で1本だけ作り直せば良い。「追加してすぐ取り消す」という無意味な2本の履歴を残す必要が無い
- **既に共有された後の場合**（コミットしてpushした、他の人の環境やCI・本番で既に `upgrade` 済み）: そのマイグレーションを削除・書き換えしてはいけない。他の環境は既にそのリビジョンIDを `alembic_version` に記録済みのため、ファイルを消すと整合性が壊れる。この場合は前述の「`--autogenerate` は `head` で」の原則に従い、**`upgrade head` で一旦最新に戻す → モデルを修正 → `--autogenerate`（新しい「取り消す」マイグレーションが生成される）→ `upgrade head`** という、前に進む形でしか取り消せない

## `env.py`（async版）が `NullPool` と `run_sync` を使う理由

`alembic init -t async migrations` が生成する `env.py` には、アプリ本体（`db/session.py`）とは違う工夫が2つ入っている。

- **`poolclass=pool.NullPool`**: アプリ用のエンジン（`db/session.py`）はリクエストのたびに繋ぎ直すコストを避けるためコネクションプールを保持するが、マイグレーションは一連の処理が終わったらプロセスごと終了する使い捨て実行。繋ぎっぱなしにする理由が無いので、プールせず毎回素の接続だけ使う `NullPool` にしている
- **`await connection.run_sync(do_run_migrations)`**: Alembic本体（`context.run_migrations()` など）は同期API前提で作られている。非同期エンジンで得た接続（`AsyncConnection`）をAlembicの同期コードに渡すため、`run_sync()` で「この接続を使って、この同期関数を実行して」という橋渡しをしている

## `alembic init` はマイグレーションファイルを作らない

`alembic init -t async migrations` が作るのは `alembic.ini` / `migrations/env.py` / `migrations/script.py.mako` / 空の `migrations/versions/` という**土台（ハーネス）だけ**。最初のマイグレーションファイルも、土台ができた後に改めて `alembic revision --autogenerate` を実行して作る。「土台作り」と「マイグレーション生成」は常に別コマンド。
