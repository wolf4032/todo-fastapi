# 0003. アプリは `devtools` ではなく `api` コンテナで走らせる

- ステータス: 採用
- 日付: 2026-08-19（Step 4）

## 背景

[0001](0001-devtools-toolbox.md) で VS Code の接続先を `devtools` にした。`devtools` にも Python と `backend/.venv` があるので、uvicorn や pytest をそこで直接動かすこともできる。

しかし `devtools` のイメージは本番イメージとは別系統であり、OS パッケージ・環境変数・ユーザー・ネットワーク上の名前が本番とは違う。そこでアプリを動かすと、開発時に確かめた挙動が本番の挙動の証拠にならない。

## 決定

開発中の uvicorn も、テストも、静的解析も、**`backend/Dockerfile` の dev ステージから作った `api` コンテナ**で実行する。

- `make test` / `make lint` / `make migrate` はすべて `docker compose exec api ...`
- デバッグは `debugpy` のポートアタッチで行う。`devtools` の VS Code から `api:5678` に接続する
- `--reload` のリローダはアプリを子プロセスで動かすため、デバッガがブレークポイントを拾い損ねることがある。そこで通常起動（`--reload` あり・デバッガなし）と `make debug`（`--reload` なし・デバッガ待受）を分ける
- VS Code のテストエクスプローラは無効にする。そこから走らせると `devtools` の Python で動いてしまうため

## 却下した案

- **`devtools` で uvicorn / pytest を直接動かす**: 手軽で、デバッガもポートアタッチ不要でそのまま使える。ただし実行環境が本番と別系統になり、CI とも一致しない。DB の接続情報も `devtools` には渡していない
- **テストだけ `devtools` で動かす**: 「テストが通った環境」と「アプリが動く環境」が別物になり、テストの価値が下がる

## 結果

- 開発・テスト・CI が同じイメージで動き、本番とは `base` ステージと `uv.lock` を共有する
- 引き受けたこと:
  - デバッグに一手間かかる（`docker compose stop api` → `make debug` → VS Code でアタッチ）
  - `make debug` は `docker compose run` を使うので、`--name api` を付けないとサービス名 `api` で名前解決できない（→ [step-05-app-foundation.md](../notes/step-05-app-foundation.md)）
  - エディタ（`devtools` の `backend/.venv`）と実行環境（`api` の `/opt/venv`）で venv が別になる。エディタ上の型チェックと `make lint` の結果がずれたときは、`make lint` を正とする

詳細: [step-05-app-foundation.md](../notes/step-05-app-foundation.md)、[step-09-tests.md](../notes/step-09-tests.md)
