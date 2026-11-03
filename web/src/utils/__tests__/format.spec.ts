import { describe, expect, it } from "vitest";

import { formatLogLine, formatMinute } from "../format";

const CASE = /^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]\[(信息|警告|错误)\]：/;

describe("formatLogLine", () => {
  it("把 docker 的 UTC 时间戳换成本地时间，并补日志等级", () => {
    const text = formatLogLine("2026-11-03T09:34:44.123456789Z [entrypoint] 启动完成");
    expect(text).toMatch(CASE);
    expect(text.endsWith("[信息]：[entrypoint] 启动完成")).toBe(true);
  });

  it("识别错误与警告标记", () => {
    expect(formatLogLine("2026-11-03T09:34:44Z [错误] 读取 .env 失败")).toContain("[错误]：");
    expect(formatLogLine("2026-11-03T09:34:44Z [警告] 未找到监听脚本")).toContain("[警告]：");
    expect(formatLogLine("2026-11-03T09:34:44Z Traceback (most recent call last):")).toContain("[错误]：");
  });

  it("正文里的「失败」不算错误等级", () => {
    expect(formatLogLine("2026-11-03T09:34:44Z 未达标原因：失败 3 个")).toContain("[信息]：");
  });

  it("supercronic 的 logfmt 行用其 level，并去掉重复时间", () => {
    const text = formatLogLine(
      '2026-11-03T11:37:27Z time="2026-11-03T19:37:27+08:00" level=info msg="read crontab: /tmp/supercronic.crontab"',
    );
    expect(text.endsWith("[信息]：read crontab: /tmp/supercronic.crontab")).toBe(true);
    expect(
      formatLogLine('2026-11-03T11:37:27Z time="2026-11-03T19:37:27+08:00" level=error msg="boom"'),
    ).toContain("[错误]：boom");
  });

  it("没有时间戳前缀的行原样返回", () => {
    expect(formatLogLine("plain line")).toBe("plain line");
  });
});

describe("formatMinute", () => {
  it("固定输出 YYYY-MM-DD HH:MM，不随 locale 变成斜杠", () => {
    expect(formatMinute("2026-11-03T09:34:44Z")).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  });

  it("空值与非法值不报错", () => {
    expect(formatMinute(null)).toBe("—");
    expect(formatMinute("not-a-time")).toBe("not-a-time");
  });
});
