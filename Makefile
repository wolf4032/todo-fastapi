# 開発コマンドの単一窓口。将来 CI からも同じターゲットを呼ぶ。
# → docs/notes/step-05-app-foundation.md

.PHONY: debug migrate test lint format

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

# python -m pytest で実行するのは、bare の pytest コマンドだと sys.path に
# カレントディレクトリ（/app）が入らず、テストから `import app` できないため。
# → docs/notes/step-09-tests.md
test:
	docker compose exec api python -m pytest

# 静的解析。api コンテナ（dev ステージ）で走らせるのは test と同じ理由で、
# ツールのバージョンが uv.lock 由来に固定され、手元と CI で結果がずれないため。
# CI からもこのターゲットを呼べば、実行内容は1箇所の定義で済む。
# make はレシピの各行を別々のシェルで順に実行し、どれか1行が失敗した時点で止める。
# そのため && で繋がなくても「1つでも落ちれば make lint は失敗」になる。
# → docs/notes/step-10-lint-format-editor.md
lint:
	docker compose exec api ruff check .
	docker compose exec api ruff format --check .
	docker compose exec api mypy

# 自動修正と整形をまとめて適用する。lint との違いは「直すか、報告だけか」。
#
# --exit-zero が要るのは、ruff check が「自動修正できない指摘が残った」ときに
# 終了コード 1 を返すため。make は失敗した行で止まるので、これが無いと
# 後続の ruff format に到達しない。ここは修正を当てるのが目的であり、
# 残った指摘の報告は make lint の役目なので、終了コードは握り潰してよい。
# 順番が check → format なのは、整形を最後に通して見た目を確定させるため。
format:
	docker compose exec api ruff check --fix --exit-zero .
	docker compose exec api ruff format .
