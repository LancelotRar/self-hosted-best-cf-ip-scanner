from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from panel.cron import CronInvalid, next_runs, validate


def test_five_field_preview():
    tz = ZoneInfo("Asia/Shanghai")
    runs = next_runs(
        "30 */6 * * *",
        "Asia/Shanghai",
        count=3,
        now=datetime(2026, 11, 3, 0, 0, tzinfo=tz),
    )
    assert [run.strftime("%H:%M") for run in runs] == ["00:30", "06:30", "12:30"]


def test_seven_field_preview_supports_seconds():
    runs = next_runs(
        "*/30 * * * * * *",
        "UTC",
        count=2,
        now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    )
    assert [run.strftime("%H:%M:%S") for run in runs] == ["00:00:30", "00:01:00"]


def test_six_field_sixth_field_is_year_not_seconds():
    # supercronic：6 段 = 分 时 日 月 周 年；第 6 位当秒会静默变成另一种调度。
    runs = next_runs(
        "*/30 * * * * *",
        "UTC",
        count=2,
        now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("UTC")),
    )
    assert [run.strftime("%H:%M:%S") for run in runs] == ["00:30:00", "01:00:00"]


def test_year_field_restricts_next_run():
    runs = next_runs(
        "0 9 * * * 2027",
        "UTC",
        count=1,
        now=datetime(2026, 11, 3, 0, 0, tzinfo=ZoneInfo("UTC")),
    )
    assert runs[0].strftime("%Y-%m-%d %H:%M") == "2027-01-01 09:00"


@pytest.mark.parametrize("expr", ["@daily", "61 * * * *", "* * *"])
def test_invalid_cron(expr):
    with pytest.raises(CronInvalid):
        validate(expr)


def test_weekday_and_step_lists_are_supported():
    runs = next_runs(
        "0 9 * * 1-5",
        "UTC",
        count=1,
        now=datetime(2026, 11, 7, 12, 0, tzinfo=ZoneInfo("UTC")),  # 周六
    )
    assert runs[0].weekday() == 0  # 下周一
    assert runs[0].strftime("%H:%M") == "09:00"


def test_unknown_timezone_is_rejected():
    with pytest.raises(CronInvalid):
        next_runs("0 * * * *", "Mars/Olympus")


def test_preview_endpoint_returns_five_runs(client):
    body = client.get(
        "/api/schedule/preview", params={"cron": "30 */6 * * *"}
    ).json()
    assert len(body["runs"]) == 5
    assert body["tz"]


def test_preview_rejects_invalid_cron(client):
    response = client.get("/api/schedule/preview", params={"cron": "@daily"})
    assert response.status_code == 422
    assert response.json()["code"] == "cron_invalid"


def test_apply_reports_unavailable(client, fake_controller):
    fake_controller.raise_unavailable = True
    response = client.post("/api/schedule/apply")
    assert response.status_code == 503


def test_apply_failure_surfaces_error(client, fake_controller):
    fake_controller.apply_exit = 1
    response = client.post("/api/schedule/apply")
    assert response.status_code == 500
    assert response.json()["code"] == "schedule_apply_failed"
