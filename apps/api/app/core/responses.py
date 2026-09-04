"""统一 API 响应模型与成功响应构造函数。"""

from typing import Any

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """统一错误内容。"""

    code: str
    message: str
    details: Any | None = None


class ApiResponse[ResponseData](BaseModel):
    """统一 API envelope。"""

    success: bool
    data: ResponseData | None
    error: ErrorDetail | None


def success_response[ResponseData](data: ResponseData) -> ApiResponse[ResponseData]:
    """
    构造统一成功响应。

    输入：
        data: ResponseData，需要返回给客户端的业务数据。

    输出：ApiResponse[ResponseData]，error 为 None 的成功响应。
    """
    return ApiResponse(success=True, data=data, error=None)
