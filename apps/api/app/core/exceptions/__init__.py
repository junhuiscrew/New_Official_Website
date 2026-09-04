"""统一异常类型与 FastAPI 异常处理器。"""

from app.core.exceptions.handlers import AppException, register_exception_handlers

__all__ = ["AppException", "register_exception_handlers"]
