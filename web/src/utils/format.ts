/** 展示层格式化：所有页面共用，避免各写一套。 */

export function formatTime(value: string | null | undefined, withDate = true): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", {
    hour12: false,
    ...(withDate
      ? { year: "numeric", month: "2-digit", day: "2-digit" }
      : { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  });
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
