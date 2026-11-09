export type Effect = "next_round" | "schedule_reload" | "restart_required";

export interface Param {
  name: string;
  group: string;
  kind: string;
  label: string;
  help: string;
  default: unknown;
  value: unknown;
  source: "custom" | "default";
  configured: boolean;
  secret: boolean;
  read_only: boolean;
  restart: boolean;
  consumer: string;
  effect: Effect;
  hidden: boolean;
}

export interface ConfigResponse {
  hash: string;
  revision: number;
  updated_at: string | null;
  params: Param[];
}

export interface VerificationDetail {
  name: string;
  expected?: unknown;
  actual?: unknown;
  line?: number;
  raw?: string;
  message?: string;
}

export interface Verification {
  status: "verified" | "mismatch" | "unavailable" | "restart_required";
  checked_at: string;
  details: VerificationDetail[];
}

export interface ChangedItem {
  name: string;
  old: unknown;
  new: unknown;
  effect: Effect;
}

export interface SaveResult {
  written: boolean;
  hash: string;
  changed: ChangedItem[];
  effects: {
    next_round: string[];
    schedule_reloaded: boolean;
    restart_required: string[];
  };
  verification: Verification;
  next_run: string | null;
  warnings: string[];
}

export interface AuthStatus {
  initialized: boolean;
  authenticated: boolean;
  username: string | null;
  setup_token_required?: boolean;
}

export interface ScannerStatus {
  state: string;
  name?: string;
  health?: string | null;
  started_at?: string | null;
  image?: string | null;
  reason?: string;
}

export interface RunStageMetrics {
  qualified?: number;
  rejected?: number;
  seconds?: number;
}

export interface RunMetrics {
  schema?: number;
  ok?: boolean;
  started_at?: string;
  finished_at?: string;
  total_seconds?: number;
  candidates?: number;
  networks?: number;
  excluded_addresses?: number;
  sample_stride?: number;
  stage?: string;
  message?: string;
  stages?: {
    tcp?: RunStageMetrics;
    endpoint?: RunStageMetrics;
    output?: RunStageMetrics;
  };
  failure_reasons?: {
    tcp?: Record<string, number>;
    endpoint?: Record<string, number>;
  };
  outputs?: {
    detail?: { name?: string; rows?: number };
    subscriptions?: Array<{ name?: string; count?: number }>;
    pinned?: boolean;
  };
}

export interface RunRecord {
  run_id: string;
  trigger: string | null;
  started_at: string | null;
  finished_at: string | null;
  scan_exit: number | null;
  publish_exit: number | null;
  duration_s: number | null;
  summary: string | null;
  interrupted: boolean;
  status?: "done" | "running" | "interrupted";
  metrics?: RunMetrics | null;
}

export interface OverviewSchedule {
  cron: string;
  tz: string;
  enabled: boolean;
  next_runs: string[];
}

export interface OverviewPublish {
  enabled: boolean;
  repo_url: string | null;
  branch: string | null;
  subdir: string | null;
  last: RunRecord | null;
}

export interface OverviewArtifacts {
  count: number;
  files: OutputFile[];
  detail: OutputFile | null;
  qualified: number | null;
  updated_at: string | null;
}

export interface Overview {
  scanner: ScannerStatus;
  running: boolean;
  last_run: RunRecord | null;
  next_runs: string[];
  timezone: string;
  schedule: OverviewSchedule;
  publish: OverviewPublish;
  recent_runs: RunRecord[];
  artifacts: OverviewArtifacts;
  config_summary: Record<string, unknown>;
}

export interface SchedulePreview {
  cron: string;
  tz: string;
  runs: string[];
}

export interface OutputFile {
  name: string;
  size: number;
  mtime: string;
  /** 文本列表的条目数；CSV 为数据行数，二进制为 null。 */
  count: number | null;
  /** `text` / `csv` / `binary`，由后端按扩展名判定。 */
  kind?: "text" | "csv" | "binary";
}

export interface LibraryStats {
  /** 展开网段、按采样步长抽取后真正参与探测的 IP 数。 */
  probe: number;
  /** 被 `#` 注释跳过的 IP 数（注释行按网段展开、合并去重后求和）。 */
  skipped: number;
  networks: number;
  /** 合并去重后的地址总数（不采样）。 */
  total: number;
}

/** 固定保留：不做探测、不做机房映射，单独生成一个产物文件。 */
export interface PinnedList {
  content: string;
  hash: string;
  count: number;
  mtime: string | null;
  /** 产物文件名（不含扩展名），由参数 `PINNED_OUTPUT_NAME` 决定。 */
  output_name: string;
}

export interface LibraryDocument {
  content: string;
  line_count: number;
  hash: string;
  mtime: string | null;
  read_at: string;
  stats: LibraryStats;
  pinned: PinnedList;
}

export interface LocationEntry {
  /** Cloudflare 三字机房代码，如 `HKG`。 */
  code: string;
  /** ISO 3166-1 两位国家代码，如 `HK`。 */
  country: string;
}

export interface LocationsDocument {
  hash: string;
  mtime: string | null;
  count: number;
  entries: LocationEntry[];
  read_at: string;
}

export interface VersionRecord {
  id: number;
  created_at: string;
  actor: string;
  sha256: string;
  diff: string;
}
