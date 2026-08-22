# コンテナ間ネットワークとDNS

Step 5 で `debugpy` へのアタッチが繋がらず、原因の切り分けに使った一般知識。ツールボックス方式（→ [step-02-devcontainer.md](step-02-devcontainer.md)）を採用している以上、「VS Codeがどこに接続しているか」と「実際にネットワーク的に繋がる場所」がズレることがある、という教訓。

## VS Codeの拡張機能は devtools コンテナの中で動く

Dev Containerに接続している間、VS Code拡張機能（デバッガも含む）のロジックは、Mac本体ではなく **`devtools` コンテナの中**で実行される。そのため、デバッガが `localhost` に接続しようとすると、それは `devtools` **自身の**ループバックアドレスを指す。`api` コンテナがホストにポートを公開していても、`devtools` から見た `localhost` とは無関係で、`ECONNREFUSED` になる。

`api` コンテナに繋ぐには、Dockerのcompose ネットワーク上の名前（サービス名）で指定する必要がある。

## `docker compose run` は「サービス名」のDNS別名を持たない

`docker compose up` で管理されるコンテナ（`db`、`devtools` など）は、同じネットワーク上の他のコンテナから **コンテナのフルネームと、短いサービス名の両方**で名前解決できる（`docker inspect` の `NetworkSettings.Networks.<net>.Aliases` に両方が入っている）。

一方 `docker compose run` で作る使い捨てコンテナ（`make debug` で使っている）は、**自動生成された名前**（`api-run-xxxxxxxxxxxx` のような）しか持たず、サービス名 `api` としては解決できない。これは `docker compose run` の一般的な仕様で、実行中の「本物」のサービスインスタンスのDNS名を、一時的な使い捨てコンテナが奪わないようにする設計だと考えられる。

対策は `docker compose run --name api ...` のように、コンテナ名を明示的に指定すること。Dockerのユーザー定義ブリッジネットワークでは、コンテナは自分自身の `--name` でも名前解決できるため、これで `api` という名前が使えるようになる。

## `docker compose run --rm` の自動削除は正常終了時のみ

`--rm` はコンテナが**正常に終了した時だけ**自動的に削除する。デバッガのアタッチ待ち（`--wait-for-client`）の途中で `Ctrl+C` したり、VS Code側の接続が失敗して中断されたりすると、コンテナ自体は削除されずに残り続けることがある。

残ったコンテナはポート（今回は5678/8000）を掴んだままになるため、次に `make debug` を実行しても、新しいコンテナと古いコンテナでポートが競合し、意図しない方（古いゾンビ）に接続してしまうことがある。

`docker compose stop/rm <service>` は、こうした使い捨てコンテナには効かない（`up` で管理される「本来の」コンテナだけが対象になる）。掃除するには、コンテナ名を直接指定して `docker stop`/`docker rm -f` する必要がある。

## 切り分けに使った診断コマンド

DNSに依存せず、生のTCP到達性だけを確認したい場合、`bash` の `/dev/tcp` 擬似デバイスが追加のツールなしで使える。

```bash
timeout 2 bash -c "</dev/tcp/<host>/<port>" && echo OK || echo FAIL
```

コンテナが実際にどのネットワークに乗っていて、どういう別名を持っているかは `docker inspect` で確認できる（ネットワーク名にハイフンが含まれる場合、Goテンプレートの `.` 記法では参照できないため `index` を使う）。

```bash
docker inspect <container> --format '{{(index .NetworkSettings.Networks "todo-fastapi_default").Aliases}}'
```

`getent hosts <name>` は、その名前が今の場所からDNSで解決できるかどうかだけを確認する、副作用のない読み取り専用コマンド。
