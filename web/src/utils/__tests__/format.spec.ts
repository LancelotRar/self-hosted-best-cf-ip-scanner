import { describe, expect, it } from "vitest";

import { formatLogLine, formatMinute } from "../format";

describe("formatLogLine", () => {
  it("把 docker 的 UTC 时间戳换成本地 MM-DD HH:MM:SS", () => {
    const line = "2026-11-03T09:34:44.123456789Z [entrypoint] 启动完成";
    const text = formatLogLine(line);
    expect(text).toMatch(/^\d{2}-\d{2} \d{2}:\d{2}:\d{2}  \[entrypoint\] 启动完成$/);
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
