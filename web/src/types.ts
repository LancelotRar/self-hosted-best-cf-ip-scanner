export type Effect = "next_round" | "schedule_reload" | "restart_required";

export interface Param {
  name: string;
  group: string;
  kind: string;
  label: string;
  help: string;
  default: unknown;
  value: unknown;
  source: "dotenv" | "default";
  configured: boolean;
  secret: boolean;
  read_only: boolean;
  restart: boolean;
  consumer: string;
  effect: Effect;
}

export interface ConfigResponse {
  hash: string;
  mtime: string | null;
  file_size: number;
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
}

export interface ScannerStatus {
  state: string;
  name?: string;
  health?: string | null;
  started_at?: string | null;
  image?: string | null;
  reason?: string;
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
}

export interface Overview {
  scanner: ScannerStatus;
  running: boolean;
  last_run: RunRecord | null;
  next_runs: string[];
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
}

export interface LibraryDocument {
  content: string;
  line_count: number;
  hash: string;
  mtime: string | null;
  read_at: string;
  stats: { networks: number; fixed: number; skipped: number };
}

export interface VersionRecord {
  id: number;
  created_at: string;
  actor: string;
  sha256: string;
  diff: string;
}
