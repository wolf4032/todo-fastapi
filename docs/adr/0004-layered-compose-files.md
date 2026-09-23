# 0004. compose を共通＋環境ごとの差分の3ファイルに分ける

- ステータス: 採用
- 日付: 2026-08-17（Step 2。`compose.prod.yaml` は Step 11 で追加）

## 背景

開発と本番相当とで、同じサービス（`db` / `api`）の定義の大部分は共通だが、次の点だけが違う。

| | 開発 | 本番相当 |
|---|---|---|
| ビルドするステージ | `dev` | `prod` |
| コード | バインドマウント | イメージに焼いたもの |
| 起動コマンド | `--reload` あり | Dockerfile の `CMD` のまま |
| `devtools` | 要る | 存在してはいけない |

共通部分を重複させず、しかも開発専用のもの（特に `devtools`）が本番の定義に混ざらない形にしたい。

## 決定

Compose の複数ファイルのマージ機能を使い、3ファイルに分ける。

| ファイル | 役割 | 読まれ方 |
|---|---|---|
| `compose.yaml` | 共通の定義（`db` / `api`） | 常に |
| `compose.override.yaml` | 開発の差分（`target: dev`、バインドマウント、`--reload`、デバッガのポート、`devtools`） | `-f` を付けなければ自動で |
| `compose.prod.yaml` | 本番相当の差分（`target: prod`） | `-f compose.yaml -f compose.prod.yaml` と明示したときだけ |

- `devcontainer.json` の `dockerComposeFile` には `compose.yaml` と `compose.override.yaml` を列挙する
- ローカルで本番相当を動かすときは `-p todo-fastapi-prod` でプロジェクト名を分ける（Makefile の `PROD_COMPOSE`）

## 却下した案

- **1ファイルにまとめ、`profiles` で出し分ける**: `devtools` を profile で隠すことはできるが、定義そのものは本番用のファイルに残る。また `profiles` はサービス単位の出し入れであり、同じ `api` の `target` やマウントを環境ごとに変える用途には向かない
- **環境ごとに完全なファイルを別々に書く**（`compose.dev.yaml` と `compose.prod.yaml` に全部を書く）: 共通部分が重複し、片方だけ直してずれていく
- **開発用も `compose.dev.yaml` という名前にして毎回 `-f` で指定する**: 最も頻繁に使う開発時に毎回 `-f` を2つ書くことになる。`compose.override.yaml` という名前なら素の `docker compose` がそのまま開発構成になる

## 結果

- `docker compose ...` が開発、`docker compose -f compose.yaml -f compose.prod.yaml ...` が本番相当、と入口が分かれる
- `compose.prod.yaml` に `volumes:` と `command:` を**書かない**ことで、「焼かれたコードが `CMD` どおりに動く」状態が表現できる
- 引き受けたこと:
  - `-f` を1つでも書くと `compose.override.yaml` の自動読み込みが止まる。本番相当のつもりで `-f compose.prod.yaml` だけを書くと共通定義が読まれない、といった指定ミスが起こりうる。Makefile の `prod-*` ターゲットに閉じ込めて防いでいる
  - 同じマシンで両方を動かすとイメージ名・ボリュームが衝突するため、`-p` での分離が必要（本物の本番は別マシンなので、ローカル特有の事情）

詳細: [step-02-devcontainer.md](../notes/step-02-devcontainer.md)、[step-11-prod-image.md](../notes/step-11-prod-image.md)
