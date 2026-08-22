import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger("app")

# logging.LogRecord が標準で持つ属性名の一覧。JSON 化する際にこれ以外を「extra」とみなす。
_STANDARD_RECORD_KEYS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", (), None)))


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # logger.info(..., extra={...}) で渡した独自フィールドをそのまま展開する。
        for key, value in vars(record).items():
            if key not in _STANDARD_RECORD_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    # コンテナの流儀は「標準出力にログを流すだけ」。ファイル出力やログローテーションは
    # コンテナ側の責務にせず、docker のログドライバに任せる。
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # クライアントが X-Request-ID を送ってくればそれを引き継ぎ、無ければ新規発行する。
    # 複数サービスをまたぐ場合に、同じリクエストのログを ID で串刺しに追跡できる。
    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
    request.state.request_id = request_id

    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # ここで拾えるのは「まだレスポンスに変換されていない」例外だけ。
        # HTTPException や RequestValidationError は call_next の中で既に
        # レスポンスへ変換済みなので、この except には来ない。
        duration_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round(duration_ms, 2),
            },
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )
    return response
