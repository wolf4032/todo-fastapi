# 0005. ブラウザから API へは web が中継し、同一オリジンにする

- ステータス: 採用
- 日付: 2026-09-23（Step 14）

## 背景

Next.js の画面（`web`、ブラウザからは `localhost:3000`）から FastAPI（`api`、`:8000`）を呼ぶ。ポートが違うのでオリジンも違い、ブラウザから直接呼ぶと同一オリジンポリシーに阻まれる（→ [topic-same-origin-and-cors.md](../notes/topic-same-origin-and-cors.md)）。

満たしたい要件は次の3つ。

- 開発と本番で、ブラウザから見た API の URL の形を同じにする
- API 側に「どのフロントから呼ばれるか」を持ち込まない
- web は API の中身（エンドポイントごとの仕様）を知らずに済むようにする

## 決定

`frontend/next.config.ts` の rewrites で `/api/:path*` を `http://api:8000/api/:path*` へ転送する。

- ブラウザは常に `localhost:3000/api/...` にだけリクエストを送る。API クライアント（`frontend/lib/api.ts`）の基準 URL は相対パス `/api/v1`
- 転送は compose ネットワークの中で `web` コンテナが行うので、転送先にはサービス名 `api` を書ける
- API 側に CORS の設定は入れない

## 却下した案

- **CORS を有効にしてブラウザから `localhost:8000` を直接呼ぶ**: API が許可するオリジンの一覧を持つことになり、環境ごとに設定が増える。更新系のリクエストにはプリフライト（事前確認）の往復も加わる。本番で前段のリバースプロキシがパスで振り分ける構成とも URL の形が変わる
- **Route Handler（`app/api/[...path]/route.ts`）で中継する**: 同一オリジンにはなるが、メソッド・ヘッダ・本文・ステータスを自分で詰め直すことになり、漏れがあると挙動が変わる。応答の加工や集約（BFF）が要るまでは、そのまま転送する rewrites で足りる

## 結果

- CORS が発生しないので、API 側の設定は増えなかった。Step 5 で用意していた CORS 用の設定枠は、使わないので削除した
- 引き受けたこと:
  - **転送先は `next build` の時点でビルド結果に書き込まれる**。本番イメージの起動時に環境変数で変えることはできない。環境ごとに転送先を変えるなら、ビルド時に値を渡す（`ARG`）必要がある（→ [topic-docker-build-and-run.md](../notes/topic-docker-build-and-run.md)）。今は開発も本番相当もサービス名が `api` なので、固定で書いている
  - API への全リクエストが web を通るので、web が止まると API も画面からは使えない。`curl localhost:8000` で直接叩く経路は開発用として残っている

詳細: [step-14-web-container.md](../notes/step-14-web-container.md)、[step-16-prod-web.md](../notes/step-16-prod-web.md)
