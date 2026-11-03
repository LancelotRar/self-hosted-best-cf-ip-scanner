"""审计路由：分页查看操作记录（已脱敏）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..security import require_user

router = APIRouter(prefix="/api/audit", tags=["audit"])

PAGE_SIZE = 50


@router.get("", dependencies=[Depends(require_user)])
def list_audit(request: Request, page: int = 1) -> dict[str, object]:
    current = max(1, page)
    conn = request.app.state.conn
    total = conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    rows = conn.execute(
        "SELECT id, at, actor, action, target, detail, ip FROM audit"
        " ORDER BY id DESC LIMIT ? OFFSET ?",
        (PAGE_SIZE, (current - 1) * PAGE_SIZE),
    ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "page": current,
        "page_size": PAGE_SIZE,
        "total": total,
    }
