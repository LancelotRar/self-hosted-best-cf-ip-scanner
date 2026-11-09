import { describe, expect, it } from "vitest";

import type { RunRecord } from "../../types";
import {
  runCandidates,
  runLabel,
  runMatchesFilter,
  runQualified,
  runSummary,
  runTone,
} from "../run";

function record(overrides: Partial<RunRecord> = {}): RunRecord {
  return {
    run_id: "r1",
    trigger: "panel",
    started_at: "2026-11-03T00:00:00Z",
    finished_at: "2026-11-03T00:02:00Z",
    scan_exit: 0,
    publish_exit: 0,
    duration_s: 120,
    summary: "完成",
    interrupted: false,
    status: "done",
    ...overrides,
  };
}

describe("run helpers", () => {
  it("完成/失败/发布失败/中断/运行中映射到一致的状态与语气", () => {
    expect(runLabel(record())).toBe("完成");
    expect(runTone(record())).toBe("success");
    expect(runLabel(record({ scan_exit: 2 }))).toBe("失败");
    expect(runTone(record({ scan_exit: 2 }))).toBe("warning");
    expect(runLabel(record({ publish_exit: 1 }))).toBe("发布失败");
    expect(runTone(record({ publish_exit: 1 }))).toBe("warning");
    expect(runLabel(record({ status: "interrupted", finished_at: null }))).toBe("中断");
    expect(runLabel(record({ status: "running", finished_at: null }))).toBe("运行中");
  });

  it("优先读取结构化指标，缺失时退回 summary", () => {
    const withMetrics = record({
      metrics: { candidates: 100, stages: { endpoint: { qualified: 12 } } },
    });
    expect(runQualified(withMetrics)).toBe(12);
    expect(runCandidates(withMetrics)).toBe(100);
    expect(runSummary(withMetrics)).toBe("合格 12 / 100");
    expect(runSummary(record())).toBe("完成");
    expect(runQualified(record())).toBeNull();
  });

  it("筛选覆盖完成、失败、中断与运行中", () => {
    expect(runMatchesFilter(record(), "done")).toBe(true);
    expect(runMatchesFilter(record({ scan_exit: 1 }), "failed")).toBe(true);
    expect(runMatchesFilter(record({ publish_exit: 1 }), "failed")).toBe(true);
    expect(runMatchesFilter(record({ publish_exit: 1 }), "done")).toBe(false);
    expect(runMatchesFilter(record({ status: "interrupted" }), "interrupted")).toBe(true);
    expect(runMatchesFilter(record({ status: "running" }), "running")).toBe(true);
    expect(runMatchesFilter(record(), "failed")).toBe(false);
  });
});
