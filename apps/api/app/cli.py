"""本地开发与容器初始化命令入口。"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
from collections.abc import Sequence

from app.core.database import async_session_factory
from app.modules.users.bootstrap import create_super_admin
from app.seed import seed_database


def build_parser() -> argparse.ArgumentParser:
    """
    创建 API 管理命令解析器。

    输入：无。

    输出：argparse.ArgumentParser，支持 `seed` 与 `create-super-admin` 命令。
    """
    parser = argparse.ArgumentParser(description="Junhui Global Website API 管理命令")
    parser.add_argument(
        "command", choices=("seed", "create-super-admin"), help="需要执行的管理命令"
    )
    parser.add_argument("--email", help="Bootstrap 管理员邮箱；也可用 BOOTSTRAP_ADMIN_EMAIL")
    parser.add_argument("--password", help="Bootstrap 管理员密码；推荐使用环境变量或交互输入")
    parser.add_argument("--display-name", help="Bootstrap 管理员显示名称")
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
        print("Phase 3.2 system seed completed.")
    elif parsed.command == "create-super-admin":
        email = parsed.email or os.getenv("BOOTSTRAP_ADMIN_EMAIL") or input("Admin email: ")
        password = (
            parsed.password
            or os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
            or getpass.getpass("Admin password: ")
        )
        display_name = (
            parsed.display_name
            or os.getenv("BOOTSTRAP_ADMIN_DISPLAY_NAME")
            or input("Display name: ")
        )
        user = asyncio.run(
            create_super_admin(
                async_session_factory,
                email=email,
                password=password,
                display_name=display_name,
            )
        )
        print(f"Super admin created: {user.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
