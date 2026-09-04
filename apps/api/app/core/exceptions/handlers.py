"""把业务、校验和 HTTP 异常转换为统一 API 错误响应。"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    """
    表示可安全返回给客户端的业务异常。

    输入：
        status_code: int，HTTP 状态码。
        code: str，稳定的机器可读错误码。
        message: str，面向客户端的错误说明。
        details: Any | None，可选的结构化错误上下文。

    输出：AppException，由全局处理器转换为 JSON。
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> JSONResponse:
    """
    创建符合统一约定的错误响应。

    输入：
        status_code: int，HTTP 状态码。
        code: str，机器可读错误码。
        message: str，安全的错误说明。
        details: Any | None，可选错误详情。

    输出：JSONResponse，统一错误 envelope。
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": code, "message": message, "details": details},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    注册应用级异常处理器。

    输入：
        app: FastAPI，需要配置异常处理的应用实例。

    输出：None；处理器被原地注册到应用。
    """

    @app.exception_handler(AppException)
    async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        """处理已知业务异常。"""
        return _error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """处理 Pydantic/FastAPI 请求校验错误。"""
        return _error_response(422, "validation_error", "请求参数校验失败", exc.errors())

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        """处理框架级 HTTP 异常并稳定错误码。"""
        code = "not_found" if exc.status_code == 404 else "http_error"
        return _error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unknown_error(_request: Request, _exc: Exception) -> JSONResponse:
        """处理未知异常且不向客户端泄露内部堆栈。"""
        return _error_response(500, "internal_error", "服务器内部错误")
