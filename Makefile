# 開発コマンドの単一窓口。将来 CI からも同じターゲットを呼ぶ。
# → docs/notes/step-05-app-foundation.md

.PHONY: debug migrate

# --reload はリローダが子プロセスでアプリを動かす都合上、デバッガがブレークポイントを
# 拾い損ねることがある。デバッグ時は --reload を切り、debugpy でポート待受に切り替える。
# 通常起動中の api（--reload 版）とポートが競合するため、先に止めてから使う。
#   docker compose stop api
debug:
# --name api を付けないと自動生成名(api-run-xxxx)になり、devtools から
# サービス名 api で名前解決できない。→ docs/notes/step-05-app-foundation.md
	docker compose run --rm --service-ports --name api api \
		python -m debugpy --listen 0.0.0.0:5678 --wait-for-client \
		-m uvicorn app.main:app --host 0.0.0.0 --port 8000

# マイグレーションの「適用」だけをここに置く。「生成」（alembic revision
# --autogenerate）は生成結果を毎回目視確認すべきなので、あえて Makefile
# に隠さず直接コマンドを叩く運用にする。→ docs/notes/step-06-alembic.md
migrate:
	docker compose exec api alembic upgrade head
