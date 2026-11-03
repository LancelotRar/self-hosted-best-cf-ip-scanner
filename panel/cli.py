"""命令行入口：`python -m panel.cli reset-password [--password]`。

只重置管理员密码，保留配置版本、审计与轮次索引——不把「删库重建」当恢复手段。
"""

from __future__ import annotations

import argparse
import getpass
from datetime import datetime, timezone

from . import db
from .audit import record
from .security import MIN_PASSWORD_LENGTH, hash_password
from .settings import Settings


def reset_password(settings: Settings, password: str, actor: str = "cli") -> None:
    """写入新密码哈希；用户不存在时创建管理员。"""
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    with conn:
        if row is None:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)",
                ("admin", hash_password(password), now, now),
            )
        else:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (hash_password(password), now, row["id"]),
            )
    record(conn, actor, "auth.reset_password", "users", "命令行重置管理员密码", "cli")
    conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="panel", description="面板运维命令")
    subparsers = parser.add_subparsers(dest="command", required=True)
    reset = subparsers.add_parser("reset-password", help="重置管理员密码")
    reset.add_argument("--password", help="新密码；省略则交互输入")
    args = parser.parse_args(argv)

    if args.command == "reset-password":
        password = args.password or getpass.getpass("新密码: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"密码至少 {MIN_PASSWORD_LENGTH} 个字符")
            return 1
        reset_password(Settings.from_env(), password)
        print("已重置管理员密码；配置版本与审计记录保留")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
