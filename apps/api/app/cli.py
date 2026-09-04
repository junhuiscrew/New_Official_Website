"""本地开发与容器初始化命令入口。"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from app.core.database import async_session_factory
from app.seed import seed_database


def build_parser() -> argparse.ArgumentParser:
    """
    创建 API 管理命令解析器。

    输入：无。

    输出：argparse.ArgumentParser，当前支持 `seed` 命令。
    """
    parser = argparse.ArgumentParser(description="Junhui Global Website API 管理命令")
    parser.add_argument("command", choices=("seed",), help="需要执行的管理命令")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """
    解析并执行管理命令。

    输入：
        arguments: Sequence[str] | None，可选命令参数，None 时读取系统参数。

    输出：int，进程退出码，成功为 0。
    """
    parsed = build_parser().parse_args(arguments)
    if parsed.command == "seed":
        asyncio.run(seed_database(async_session_factory))
        print("Phase 3.1 seed completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
