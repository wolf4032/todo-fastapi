import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: object = None,
) -> JSONResponse:
    # クライアントはこの形さえ知っていれば、どのエラーでも機械的に処理できる。
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return JSONResponse(
        status_code=status_code, content=jsonable_encoder({"error": error})
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return _error_response(request, exc.status_code, "http_error", str(exc.detail))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "validation_error",
        "リクエストの内容が不正です",
        details=exc.errors(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # DB 接続エラーなど、想定していない例外がここに来る。
    # クライアントには詳細を返さず、サーバ側のログにだけスタックトレースを残す。
    logger.exception(
        "unhandled exception",
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "サーバー内部でエラーが発生しました",
    )


def register_exception_handlers(app: FastAPI) -> None:
    # 行末の ignore コメントは「この行の arg-type エラーだけ黙らせる」指示。
    # 行頭に書くと mypy が別の意味（型コメント）に解釈するので、必ず行末に置く。
    # Starlette の型定義はハンドラの第2引数を Exception と宣言しており、
    # StarletteHTTPException のような部分型を受ける関数は型上は渡せない。
    # だが実行時は「登録した例外クラスのときだけ呼ぶ」ディスパッチなので正しい。
    # 型チェッカが表現しきれない箇所として、行単位に限定して逃がす。
    # → docs/notes/step-10-lint-format-editor.md
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    # Exception への登録は、他のどのハンドラにも捕まらなかった 500 系専用
    # （Starlette が ServerErrorMiddleware 側で別扱いする）。
    app.add_exception_handler(Exception, unhandled_exception_handler)
