/** 展示层格式化：所有页面共用，避免各写一套。 */

export function formatTime(value: string | null | undefined, withDate = true): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    hour12: false,
    ...(withDate ? { year: "numeric", month: "2-digit", day: "2-digit" } : {}),
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** 分钟精度，固定 `YYYY-MM-DD HH:MM`（不随浏览器 locale 变成斜杠格式）。 */
export function formatMinute(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
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

/** supercronic 等进程输出 `time="…" level=info msg="…"`：用它的 level，并去掉重复的时间字段。 */
function normalizeLogfmt(message: string): { message: string; level?: string } {
  const match = /^time="[^"]*"\s+level=(\w+)(?:\s+msg="([^"]*)")?\s*/.exec(message);
  if (!match) return { message };
  return { message: (match[2] ?? "") + message.slice(match[0].length), level: match[1] };
}

/** docker 日志行首的 RFC3339（UTC）时间戳 → `[YYYY-MM-DD HH:MM:SS][等级]：消息`。无时间戳前缀的行原样返回。 */
export function formatLogLine(line: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z ?/.exec(line);
  if (!match) return line;
  const [, year, month, day, hour, minute, second] = match;
  const date = new Date(
    Date.UTC(Number(year), Number(month) - 1, Number(day), Number(hour), Number(minute), Number(second)),
  );
  if (Number.isNaN(date.getTime())) return line;
  const pad = (part: number) => String(part).padStart(2, "0");
  const stamp = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  const { message, level } = normalizeLogfmt(line.slice(match[0].length));
  return `[${stamp}][${logLevel(message, level)}]：${message}`;
}

export function formatClock(value: Date | null | undefined): string {
  if (!value) return "—";
  return value.toLocaleTimeString("zh-CN", { hour12: false });
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

export function effectLabel(effect: string): string {
  if (effect === "restart_required") return "重启后生效";
  if (effect === "schedule_reload") return "已热重载";
  return "下一轮生效";
}
