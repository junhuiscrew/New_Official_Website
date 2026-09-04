"""使用 Argon2id 处理管理员密码。"""

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_PASSWORD_HASHER = PasswordHasher()
# 未命中用户时仍执行一次真实 Argon2id 校验，降低邮箱枚举的计时差异。
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash("DummyAuthentication!2026")


def hash_password(password: str) -> str:
    """
    使用 Argon2id 对明文密码进行带随机盐的单向哈希。

    输入：
        password: str，需要保存的明文密码。

    输出：str，Argon2id 编码密码哈希。
    """
    validate_password_strength(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    以恒定实现路径校验明文密码和 Argon2id 哈希。

    输入：
        password: str，登录提交的明文密码。
        password_hash: str，数据库保存的编码哈希。

    输出：bool，密码匹配返回 true，否则返回 false。
    """
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def verify_password_or_dummy(password: str, password_hash: str | None) -> bool:
    """
    使用真实哈希或固定哑元哈希执行一致的 Argon2id 校验路径。

    输入：
        password: str，登录提交的明文密码。
        password_hash: str | None，用户存在时的密码哈希，否则为空。

    输出：bool，仅真实哈希匹配时返回 true；哑元校验始终返回 false。
    """
    verified = verify_password(password, password_hash or _DUMMY_PASSWORD_HASH)
    return verified if password_hash is not None else False


def validate_password_strength(password: str) -> None:
    """
    校验 bootstrap 和用户创建密码的最低强度。

    输入：
        password: str，待校验明文密码。

    输出：None；不合格时抛出 ValueError。
    """
    checks = (
        len(password) >= 12,
        re.search(r"[A-Z]", password) is not None,
        re.search(r"[a-z]", password) is not None,
        re.search(r"\d", password) is not None,
        re.search(r"[^A-Za-z0-9]", password) is not None,
    )
    if not all(checks):
        raise ValueError("密码至少12位，并包含大小写字母、数字和特殊字符")
