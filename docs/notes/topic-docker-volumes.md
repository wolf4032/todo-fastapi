# トピック: Docker のボリュームと権限

Step 2 で `/home/vscode/.claude` の所有者問題にぶつかったのをきっかけにまとめたもの。
ステップ横断の一般知識なので独立したノートにしている。

---

## マウントの3種類

| 種類 | 実体 | 用途 |
|---|---|---|
| **bind mount** | ホストの任意のパスをそのまま見せる | ソースコード。編集が即反映されてほしいもの |
| **名前付きボリューム** | Docker が管理する領域（`/var/lib/docker/volumes/<名前>/_data`） | DB のデータ、認証情報など「ホストから直接触る必要はないが消えては困る」もの |
| **tmpfs** | メモリ上。コンテナ停止で消える | 一時ファイル、秘密情報 |

このリポジトリでの使い分け:

```yaml
volumes:
  - .:/workspaces/todo-fastapi          # bind mount: ソースコード
  - claude-config:/home/vscode/.claude  # 名前付きボリューム: 認証情報
```

後で追加する PostgreSQL のデータも名前付きボリュームに載せる。

---

## 永続性

**名前付きボリュームはコンテナのライフサイクルから独立している。**

| 操作 | ボリュームは？ |
|---|---|
| `docker compose stop` / `restart` | 残る |
| `docker compose down` | **残る** |
| コンテナの削除・再作成 | 残る |
| イメージの再ビルド（Rebuild Container） | 残る |
| `docker compose down -v` | **消える**（`-v` = volumes） |
| `docker volume rm <名前>` | 消える |

`down -v` は開発中に「DB を初期状態に戻したい」ときに使うが、**意図せず打つとデータが飛ぶ**ので注意。

現在のボリュームを見るには:

```
docker volume ls
```

Compose が作るボリュームには `<プロジェクト名>_<ボリューム名>` という接頭辞が付く。このリポジトリなら `todo-fastapi_claude-config`。

---

## 初回作成時のコピー（Step 2 でハマった点）

ここが直感に反する部分。

**Docker が名前付きボリュームを初めて作るとき**、マウント先のパスがイメージ内に

- **存在する** → そのディレクトリの**中身を、所有者と権限ごと**ボリュームへコピーする
- **存在しない** → `root:root` の `0755` で新規作成する

### 何が起きたか

`.devcontainer/Dockerfile` は最後に `USER vscode` と書いており、コンテナは UID 1000 で動く。
一方 `/home/vscode/.claude` はイメージ内に存在しなかったため、ボリュームは **root 所有** で作られた。

root 所有の `0755` ディレクトリは、vscode から**読めるが書けない**。
その結果、Claude Code が認証情報や履歴を保存しようとした瞬間に権限エラーになる。

> **よくある誤解**: 「リビルドのたびに設定がリセットされる」ではない。
> 名前付きボリュームは所有者に関係なく残る。**永続性の問題ではなく権限の問題**。

### 対策

イメージ側に、正しい所有者でディレクトリを先に作っておく。そうすればボリューム作成時に所有者ごとコピーされる。

```dockerfile
RUN mkdir -p /home/$USERNAME/.claude \
    && chown -R $USER_UID:$USER_GID /home/$USERNAME/.claude

USER $USERNAME
```

### 重要な注意点

**このコピーはボリュームの初回作成時にしか起こらない。**

すでに root 所有で作られたボリュームが残っている状態で Dockerfile を直しても、**何も変わらない**。「直したのに直らない」と延々悩むポイント。

その場合はボリュームを作り直す。

```
docker volume rm todo-fastapi_claude-config
```

または、コンテナ内から所有者を直す。

```
docker exec -u root todo-fastapi-devtools-1 chown -R vscode:vscode /home/vscode/.claude
```

### bind mount には無い挙動

コピーの仕組みは**名前付きボリューム固有**。bind mount はホスト側のディレクトリをそのまま見せるだけで、イメージ側の中身は隠される（コピーもされない）。

---

## 権限の考え方

### UID は名前ではなく番号で照合される

コンテナ内の `vscode` とホストの Mac のログインユーザーは、名前が違っても **UID が同じなら同一人物として扱われる**。逆に名前が同じでも UID が違えば別人。ファイルの所有者情報として記録されているのは番号だけだから。

これが `updateRemoteUserUID` や `--build-arg USER_UID=...` で UID を合わせる理由。

### bind mount で所有者ズレが問題になる

bind mount はホストのファイルをそのまま見せるので、**ホスト側の UID がコンテナ内でもそのまま見える**。ホストが 501、コンテナ内のユーザーが 1000 なら、所有者が一致せず書き込めない。

Linux ではこれが頻繁に問題になる。一方 **macOS / Windows の Docker Desktop はファイル共有層が所有者を調整する**ため、表面化しにくい（今回 UID 1000 のままでも git が動いたのはこのため）。ただし挙動が環境依存なので、UID を合わせておく方が安全。

### root で動かせば解決するが、やるべきではない

権限問題は root 実行で全部消えるが、

- コンテナ内で作ったファイルがホスト側で root 所有になり、ホストから消せなくなる
- コンテナ脱出の脆弱性があった場合の被害が大きくなる
- Claude Code のように root 実行を拒否するツールがある

ので、非 root で動かして UID を合わせるのが定石。

---

## 中身を確認する方法

名前付きボリュームはホストから直接見えない（macOS では Docker の VM の中にある）。中身を見るには、使い捨てコンテナからマウントする。

```
docker run --rm -v todo-fastapi_claude-config:/data alpine ls -la /data
```

ボリュームのメタ情報:

```
docker volume inspect todo-fastapi_claude-config
```

---

## トラブルシュート早見表

| 症状 | 疑うべきこと |
|---|---|
| `Permission denied` でファイルが書けない | ボリューム／bind mount の所有者と、実行ユーザーの UID が一致しているか |
| Dockerfile で `chown` したのに直らない | ボリュームがすでに存在している（初回作成時しかコピーされない）。`docker volume rm` する |
| データが消えた | `docker compose down -v` を打っていないか |
| ホスト側で消せないファイルができた | コンテナを root で動かしていないか |
| イメージ内のファイルが見えない | そのパスに bind mount を被せていないか（イメージ側の中身は隠される） |
