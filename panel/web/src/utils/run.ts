import type { RunRecord } from "../types";

export type RunTone = "success" | "warning" | "info" | "neutral";
export type RunFilter = "all" | "done" | "failed" | "interrupted" | "running";

/** 轮次状态：页面只依赖这一个函数，避免总览与运行页各写一套判断。 */
export function runLabel(record: RunRecord): string {
  if (record.status === "running") return "运行中";
  if (record.status === "interrupted") return "中断";
  if (record.status === "done" || (!record.status && record.finished_at)) {
    if (typeof record.scan_exit === "number" && record.scan_exit !== 0) return "失败";
    if (typeof record.publish_exit === "number" && record.publish_exit !== 0) return "发布失败";
    return "完成";
  }
  return "—";
}

export function runTone(record: RunRecord): RunTone {
  if (record.status === "running") return "info";
  if (record.status === "interrupted") return "warning";
  if (record.status === "done" || (!record.status && record.finished_at)) {
    const scanFailed = typeof record.scan_exit === "number" && record.scan_exit !== 0;
    const publishFailed =
      typeof record.publish_exit === "number" && record.publish_exit !== 0;
    return scanFailed || publishFailed ? "warning" : "success";
  }
  return "neutral";
}

export function runMatchesFilter(record: RunRecord, filter: RunFilter): boolean {
  if (filter === "all") return true;
  if (filter === "running") return record.status === "running";
  if (filter === "interrupted") return record.status === "interrupted";
  const scanFailed = typeof record.scan_exit === "number" && record.scan_exit !== 0;
  const publishFailed =
    typeof record.publish_exit === "number" && record.publish_exit !== 0;
  if (filter === "failed") {
    return record.status === "done" && (scanFailed || publishFailed);
  }
  return record.status === "done" && !scanFailed && !publishFailed;
}

/** 合格候选数：优先用本轮结构化指标，缺失时退回明细表行数。 */
export function runQualified(record: RunRecord | null | undefined): number | null {
  if (!record) return null;
  const qualified = record.metrics?.stages?.endpoint?.qualified;
  return typeof qualified === "number" ? qualified : null;
}

/** 本轮候选数，用于「合格 / 候选」比例。 */
export function runCandidates(record: RunRecord | null | undefined): number | null {
  const candidates = record?.metrics?.candidates;
  return typeof candidates === "number" ? candidates : null;
}

/** 人读的轮次摘要：没有指标时退回扫描器写入的 summary。 */
export function runSummary(record: RunRecord | null | undefined): string {
  if (!record) return "—";
  const qualified = runQualified(record);
  const candidates = runCandidates(record);
  if (qualified !== null && candidates !== null) {
    return `合格 ${qualified.toLocaleString("zh-CN")} / ${candidates.toLocaleString("zh-CN")}`;
  }
  return record.summary || "—";
}
