# Step 19: Caddy による HTTPS 化

作成物: `caddy/Caddyfile`、DuckDNS のサブドメイン `todo-fastapi.duckdns.org`
変更: `compose.prod.yaml`、`.env.example`、`.editorconfig`、`Makefile`、`README.md`

公開 URL: <https://todo-fastapi.duckdns.org>

---

## 構成

```
ブラウザ ──https:443──► caddy ──http──► web:3000 ──中継──► api:8000 ──► db
            ↑ 暗号化はここまで   ↑ compose ネットワークの中は平文
```

## ドメインと証明書は別物

| | 何か | 例え | 入手先 |
|---|---|---|---|
| ドメイン | `todo-fastapi.duckdns.org` のような名前。DNS で IP アドレスと対応づける | 住所 | DuckDNS（無料） |
| 証明書 | 「この名前のサーバーは本物」と第三者（認証局）が保証するもの | その住所の住人だと示す身分証 | Let's Encrypt（無料） |

証明書は IP アドレスではなく名前に対して発行されるので、名前が先に要る。「Let's Encrypt で無料で取れる」のは証明書で、ドメインではない。

### DuckDNS

- GitHub などのアカウントでサインインし、名前を選ぶだけ。無料で5つまで持てる
- **名前を作った瞬間、画面を開いている人の IP（自宅の回線）が自動で入る**。サーバーの IP に書き換える必要があった。`dig +short <名前>` で何を指しているか確かめられる
- IPv6 の欄は空にした。登録すると IPv6 が使える相手（Let's Encrypt を含む）はそちらの経路を優先し、経路に不具合があると原因を追いにくい
- token は、IP をプログラムから書き換えるための鍵。IP が変わる回線で自動追従させる用途で、静的 IP なので使わない
- ドメイン名は公開情報。Let's Encrypt が発行した証明書はすべて公開の記録（Certificate Transparency ログ）に載る

## HTTPS の仕組み

- **HTTPS** は HTTP の通信を TLS で暗号化したもの。暗号化だけでは相手が偽物でも気付けないので、**認証局**が発行した**証明書**で相手が本物かを確かめる。ブラウザは信頼する認証局の一覧を持っていて、それと照らし合わせる
- **Let's Encrypt は ACME という手順で持ち主を自動確認する**。今回の方式（HTTP-01）では、Let's Encrypt が `http://<名前>/.well-known/acme-challenge/<ランダムな文字列>` に外からアクセスし、Caddy が決められた合言葉を返せたら「その名前のサーバーを操作できる人＝持ち主」とみなす。DNS がサーバーを指していて、80 番が外から開いている必要がある
- 証明書の有効期限は 90 日。Caddy が期限の 30 日ほど前に自動で更新する

## 書いたもの

- **Caddy をリバースプロキシとして足した**: 受けたリクエストを奥の web へ転送する中継役。暗号化・証明書・HTTP から HTTPS への転送は Caddy が引き受け、web は Step 16 のまま変えていない
- **`{$SITE_ADDRESS}` で名乗るアドレスを切り替える**: ドメイン名なら自動で HTTPS（証明書の取得と転送つき）、`http://` で始めればその名前の HTTP だけ。サーバーの `.env` でだけ `SITE_ADDRESS=todo-fastapi.duckdns.org` にし、ローカルは既定の `http://localhost`。ローカルは Let's Encrypt が外から届かないので証明書を取れない
- **web の公開ポートを外した**: 外からの入口は Caddy の 80・443 だけ。これでローカルの本番相当が開発の web（3000 番）とぶつからなくなり、止めるのは開発の api だけになった。不要になった `WEB_PORT` は削除
- **証明書は名前付きボリューム `caddy-data` に保存する**: Let's Encrypt は同じ名前の証明書の発行回数に上限を設けているので、作り直すたびに取り直さない
- **`caddy:2.11-alpine`**: 2.11 系の修正版だけが自動で上がる
- **Caddyfile はタブでインデントする**: Caddy の整形コマンドの流儀で、スペースだと起動時に警告が出る。`.editorconfig` に Caddyfile 用の設定を足した

### `configs:`

```yaml
services:
  caddy:
    configs:
      - source: caddyfile              # 下で定義した名前で呼ぶ
        target: /etc/caddy/Caddyfile   # コンテナの中のこの場所に置く

configs:
  caddyfile:                           # compose の中の名前（自由に付ける。小文字は慣習）
    file: ./caddy/Caddyfile
```

- `caddyfile` は compose.prod.yaml の中で付けた名前で、Caddy の仕様ではない。`volumes:` と同じく、最後で名前を付けて定義し、サービスから `source:` で呼ぶ
- ファイルは加工されずにそのまま置かれる。`{$SITE_ADDRESS}` を置き換えるのは Caddy 自身で、起動して設定を読むときに自分の環境変数（compose の `environment:` で渡したもの）から取る
- `/etc/caddy/Caddyfile` は公式イメージが既定で読む場所（起動コマンドが `caddy run --config /etc/caddy/Caddyfile`）。ここに置けば `command:` が要らない
- Swarm を使わない普通の compose では、`configs:` は読み取り専用のバインドマウントとして実装される。Step 11 の「本番にバインドマウントを使わない」はコードをイメージに焼くための方針で、設定ファイル1つを読み取り専用で渡すのとは別に扱った。設定を変えたら `git pull` の後にコンテナを作り直せば反映され、ビルドは要らない

## サーバーでやったこと

- Lightsail のファイアウォールに HTTPS（443）を追加した。Source IP は Preset で「すべての IPv4 と IPv6」を選ぶ（CIDR で書くと `0.0.0.0/0` と `::/0`。`/0` は固定するビットが無い＝すべてのアドレス）
- `.env` から `WEB_PORT` の行を消し（`sed -i '/^WEB_PORT=/d' .env`）、`SITE_ADDRESS` を追記した（`echo ... >> .env`）。`>>` は追記で、`>` だと中身が消えて上書きになる
- `git pull` → `make prod-up`

### Caddy のログ

1行が1つの JSON で量が多い。取得できたかだけを見るなら絞り込む。

```bash
docker compose -p todo-fastapi-prod -f compose.yaml -f compose.prod.yaml logs caddy | grep -E "certificate obtained|error"
```

## 理解確認: HTTPS にした後も 80 番を閉じないのはなぜか

回答: Let's Encrypt が合言葉のやり取りのためにアクセスする URL の接続先だから。→ 正解。

1. **証明書の取得と更新**: HTTP-01 の確認は 80 番に来る。期限が 90 日で更新のたびに確認されるので、最初の取得の後も要る。Caddy は 443 番だけで確認する方式（TLS-ALPN-01）も使えるので、閉じても即座に取れなくなるとは限らないが、両方開けておけばどちらかが失敗しても取れる
2. **HTTP で来た人を HTTPS に案内する**: アドレス欄に名前だけ打ったり古い `http://` のリンクを踏んだりすると、ブラウザは 80 番に繋ぐ。閉じていると「繋がらない」で終わる。開いていれば Caddy が `308 Permanent Redirect` で `https://` に転送する。308 は 301 と違い、POST などのリクエストの種類を変えずに送り直させる

## 気付いたこと: IP アドレスで開くとエラーになる

Caddy は 80 番に来たリクエストを、宛先の名前を問わず HTTPS に転送する。`http://18.177.74.102/` は `https://18.177.74.102/` に転送され、IP アドレス宛ての証明書は無いので接続エラーになる。古い IP の URL が残っているのは過去のコミットだけなので、対応しない。

## 過去のコミットに IP アドレスが残っていること

問題にならない。名前で公開した時点で DNS を調べれば誰でも IP が分かり、IPv4 は自動のプログラムに端から調べられている。IP を隠すのではなく、ファイアウォールで守るのが基本。DuckDNS に入っていた自宅の IP を急いで直したのは、それがサーバーではなく個人の回線のアドレスだったため（コミットにも入っていない）。

## 確認したこと

- `https://todo-fastapi.duckdns.org/` が 200（HTTP/2）
- 証明書の発行者は Let's Encrypt、対象は `todo-fastapi.duckdns.org`、有効期限は 2026年12月26日
- `http://todo-fastapi.duckdns.org/` は 308 で `https://` に転送される
- `/api/v1/todos` の応答に `via: 1.1 Caddy` と `server: uvicorn` が付いている（Caddy → web → api）
- 外から 3000・8000・5432 番に繋がらない
- ローカルの `make prod-up` で <http://localhost> が開く
