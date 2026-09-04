"""供未来列表 API 复用的基础分页参数。"""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, computed_field


class PaginationParams(BaseModel):
    """
    表示受边界约束的页码分页参数。

    输入：
        page: int，从 1 开始的页码。
        page_size: int，每页数量，最大 100。

    输出：PaginationParams，含可计算 offset 的校验后参数。
    """

    page: Annotated[int, Query(ge=1)] = 1
    page_size: Annotated[int, Query(ge=1, le=100)] = 20

    @computed_field
    @property
    def offset(self) -> int:
        """返回数据库查询所需的零基偏移量。"""
        return (self.page - 1) * self.page_size
