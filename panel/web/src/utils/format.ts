/** 展示层格式化：所有页面共用，避免各写一套。 */

const pad = (part: number) => String(part).padStart(2, "0");

interface ZonedParts {
  year: string;
  month: string;
  day: string;
  hour: string;
  minute: string;
  second: string;
}

function zonedParts(date: Date, timeZone?: string): ZonedParts | null {
  if (!timeZone) return null;
  try {
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    const parts = Object.fromEntries(
      formatter
        .formatToParts(date)
        .filter((part) => part.type !== "literal")
        .map((part) => [part.type, part.value]),
    ) as Record<string, string>;
    return {
      year: parts.year,
      month: parts.month,
      day: parts.day,
      hour: parts.hour === "24" ? "00" : parts.hour,
      minute: parts.minute,
      second: parts.second,
    };
  } catch {
    // 非法 IANA 时区：退回浏览器本地时间，页面不应因此报错
    return null;
  }
}

/**
 * `YYYY-MM-DD HH:MM:SS`。传入面板时区时按该时区显示，避免容器时区与浏览器
 * 时区不同导致“下一次运行”看起来错位。
 */
export function formatTime(
  value: string | null | undefined,
  timeZone?: string,
  withDate = true,
): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const zoned = zonedParts(date, timeZone);
  const datePart = `${zoned?.year ?? date.getFullYear()}-${zoned?.month ?? pad(date.getMonth() + 1)}-${
    zoned?.day ?? pad(date.getDate())
  }`;
  const timePart = `${zoned?.hour ?? pad(date.getHours())}:${zoned?.minute ?? pad(date.getMinutes())}:${
    zoned?.second ?? pad(date.getSeconds())
  }`;
  return withDate ? `${datePart} ${timePart}` : timePart;
}

/** 分钟精度，固定 `YYYY-MM-DD HH:MM`（不随浏览器 locale 变成斜杠格式）。 */
export function formatMinute(
  value: string | null | undefined,
  timeZone?: string,
): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const zoned = zonedParts(date, timeZone);
  const year = zoned?.year ?? String(date.getFullYear());
  const month = zoned?.month ?? pad(date.getMonth() + 1);
  const day = zoned?.day ?? pad(date.getDate());
  const hour = zoned?.hour ?? pad(date.getHours());
  const minute = zoned?.minute ?? pad(date.getMinutes());
  return `${year}-${month}-${day} ${hour}:${minute}`;
}

/** 从消息文本推断日志等级：只有明确的标记才算警告/错误，避免把正文里的"失败"误判。 */
function logLevel(message: string, hint?: string): "错误" | "警告" | "信息" {
  const level = (hint ?? "").toLowerCase();
  if (level === "error" || level === "fatal" || level === "critical") return "错误";
  if (level === "warn" || level === "warning") return "警告";
  if (/\[错误\]|\[error\]|\btraceback\b|\bcritical\b|\bfatal\b/i.test(message)) return "错误";
  if (/\[警告\]|\[warn\]|\bwarning\b/i.test(message)) return "警告";
  return "信息";
}

const LOG_TIMESTAMP = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z ?/;

/** 只读日志行首的 UTC 时间戳，返回毫秒；没有时间戳时返回 null。 */
function logTimestamp(line: string): number | null {
  const match = LOG_TIMESTAMP.exec(line);
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match;
  const value = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    Number(second),
  );
  return Number.isNaN(value) ? null : value;
}

/** 日志等级；供筛选器统计与过滤，不改变原始行。 */
export function logLevelOf(line: string): "错误" | "警告" | "信息" {
  if (logTimestamp(line) === null) return "信息";
  const message = line.replace(LOG_TIMESTAMP, "");
  const { message: body, level } = normalizeLogfmt(message);
  return logLevel(body, level);
}

/** supercronic 等进程输出 `time="…" level=info msg="…"`：用它的 level，并去掉重复的时间字段。 */
function normalizeLogfmt(message: string): { message: string; level?: string } {
  const match = /^time="[^"]*"\s+level=(\w+)(?:\s+msg="([^"]*)")?\s*/.exec(message);
  if (!match) return { message };
  return { message: (match[2] ?? "") + message.slice(match[0].length), level: match[1] };
}

/** supercronic 会在每行末尾追加调度元数据；面板已单独展示计划与命令，这里只留正文。 */
function stripJobMetadata(message: string): string {
  // 元数据可能以 `channel=stdout`、`iteration=0` 或 `job.command=` 开头，
  // 且与正文之间不一定有空格（超长日志被拼接时）。
  const match = / ?(?:channel=(?:stdout|stderr)|iteration=\d+ job\.)/.exec(message);
  if (!match) return message;
  const tail = message.slice(match.index);
  if (!/job\.(command|schedule|position)=/.test(tail)) return message;
  return message.slice(0, match.index).replace(/^msg=/, "").trimEnd();
}

/**
 * docker 日志行首的 RFC3339（UTC）时间戳 → `[YYYY-MM-DD HH:MM:SS][等级]：消息`。
 * 传入面板时区时按该时区显示；无时间戳前缀的行原样返回。
 */
export function formatLogLine(line: string, timeZone?: string): string {
  const match = LOG_TIMESTAMP.exec(line);
  if (!match) return line;
  const stampMs = logTimestamp(line);
  if (stampMs === null) return line;
  const date = new Date(stampMs);
  const zoned = zonedParts(date, timeZone);
  const stamp = `${zoned?.year ?? date.getFullYear()}-${zoned?.month ?? pad(date.getMonth() + 1)}-${
    zoned?.day ?? pad(date.getDate())
  } ${zoned?.hour ?? pad(date.getHours())}:${zoned?.minute ?? pad(date.getMinutes())}:${
    zoned?.second ?? pad(date.getSeconds())
  }`;
  const { message, level } = normalizeLogfmt(line.slice(match[0].length));
  return `[${stamp}][${logLevel(message, level)}]：${stripJobMetadata(message)}`;
}

export function formatClock(value: Date | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleTimeString("zh-CN", { hour12: false });
}

/** 千位分隔：IP 数量可能上百万，不分隔读不出量级。 */
export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("zh-CN");
}

export function formatSize(size: number | null | undefined): string {
  if (size === null || size === undefined) return "—";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return rest ? `${minutes}m ${rest}s` : `${minutes}m`;
}

export function exitLabel(code: number | null | undefined): string {
  if (code === null || code === undefined) return "—";
  return code === 0 ? "成功" : `失败（${code}）`;
}

/** 运行触发方式：对用户只暴露「计划任务 / 手动触发」，不出现内部标识。 */
export function triggerLabel(trigger: string | null | undefined): string {
  if (!trigger) return "—";
  if (trigger === "cron" || trigger === "schedule" || trigger === "scheduler") return "计划任务";
  if (trigger === "panel" || trigger === "manual") return "手动触发";
  return trigger;
}

export function effectLabel(effect: string): string {
  if (effect === "restart_required") return "重启后生效";
  if (effect === "schedule_reload") return "立即生效";
  return "下一轮生效";
}
