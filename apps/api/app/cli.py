"""本地开发与容器初始化命令入口。"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
from collections.abc import Sequence

from app.core.database import async_session_factory
from app.modules.users.bootstrap import create_super_admin
from app.phase36_qa import cleanup_phase36_qa, prepare_phase36_qa, verify_phase36_qa
from app.seed import seed_database


def build_parser() -> argparse.ArgumentParser:
    """
    创建 API 管理命令解析器。

    输入：无。

    输出：argparse.ArgumentParser，支持 `seed` 与 `create-super-admin` 命令。
    """
    parser = argparse.ArgumentParser(description="Junhui Global Website API 管理命令")
    parser.add_argument(
        "command",
        choices=(
            "seed",
            "create-super-admin",
            "phase36-qa-setup",
            "phase36-qa-cleanup",
            "phase36-qa-verify",
        ),
        help="需要执行的管理命令",
    )
    parser.add_argument("--email", help="Bootstrap 管理员邮箱；也可用 BOOTSTRAP_ADMIN_EMAIL")
    parser.add_argument("--password", help="Bootstrap 管理员密码；推荐使用环境变量或交互输入")
    parser.add_argument("--display-name", help="Bootstrap 管理员显示名称")
    parser.add_argument("--run-id", help="Phase 3.6 隔离 QA 运行标识")
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
    elif parsed.command == "phase36-qa-setup":
        # QA 数据命令带双重环境门禁，绝不允许在生产环境或无确认时运行。
        manifest = asyncio.run(
            prepare_phase36_qa(
                async_session_factory,
                run_id=parsed.run_id or os.getenv("PHASE36_QA_RUN_ID", ""),
            )
        )
        print(manifest.model_dump_json(indent=2))
    elif parsed.command == "phase36-qa-cleanup":
        # 清理复用同一双重门禁与 run-id，输出严格限于脱敏计数。
        result = asyncio.run(
            cleanup_phase36_qa(
                async_session_factory,
                run_id=parsed.run_id or os.getenv("PHASE36_QA_RUN_ID", ""),
            )
        )
        print(result.model_dump_json(indent=2))
    elif parsed.command == "phase36-qa-verify":
        # 验证命令仅输出布尔断言和计数，不把 RFQ 标识或私有 URL 写入证据。
        result = asyncio.run(
            verify_phase36_qa(
                async_session_factory,
                run_id=parsed.run_id or os.getenv("PHASE36_QA_RUN_ID", ""),
            )
        )
        print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
