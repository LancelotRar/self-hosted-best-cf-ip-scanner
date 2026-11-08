import { defineStore } from "pinia";

import * as api from "../api";
import type { ConfigResponse, Param, SaveResult, VersionRecord } from "../types";

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function sameValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

/** 把界面上的值编码成配置字符串（后端仍会按 schema 再校验一次）。 */
export function formatForEnv(param: Param, value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(",");
  }
  if (param.kind === "bool") {
    return value ? "true" : "false";
  }
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

export const useConfigStore = defineStore("config", {
  state: () => ({
    hash: "",
    revision: 0,
    params: [] as Param[],
    serverValues: {} as Record<string, unknown>,
    values: {} as Record<string, unknown>,
    versions: [] as VersionRecord[],
    lastResult: null as SaveResult | null,
    lastError: null as { message: string; status?: number; details?: unknown } | null,
    loading: false,
    saving: false,
  }),
  getters: {
    changedParams: (state): Param[] =>
      state.params.filter((param) => !sameValue(state.values[param.name], state.serverValues[param.name])),
    dirtyCount: (state): number =>
      state.params.filter((param) => !sameValue(state.values[param.name], state.serverValues[param.name])).length,
    dirty: (state): boolean =>
      state.params.some((param) => !sameValue(state.values[param.name], state.serverValues[param.name])),
    diff: (state) =>
      state.params
        .filter((param) => !sameValue(state.values[param.name], state.serverValues[param.name]))
        .map((param) => ({
          name: param.name,
          label: param.label,
          old: state.serverValues[param.name],
          new: state.values[param.name],
          effect: param.effect,
        })),
  },
  actions: {
    async load() {
      this.loading = true;
      try {
        const data = await api.get<ConfigResponse>("/api/config");
        this.hash = data.hash;
        this.revision = data.revision;
        this.params = data.params;
        const snapshot: Record<string, unknown> = {};
        for (const param of data.params) {
          snapshot[param.name] = clone(param.value);
        }
        this.serverValues = snapshot;
        this.values = clone(snapshot);
        this.lastError = null;
      } finally {
        this.loading = false;
      }
    },
    applyLocal(changes: Record<string, unknown>) {
      this.values = { ...this.values, ...changes };
    },
    cancel() {
      this.values = clone(this.serverValues);
      this.lastError = null;
    },
    async save(): Promise<SaveResult | null> {
      const changed = this.changedParams;
      if (!changed.length) return this.lastResult;
      const values: Record<string, string> = {};
      for (const param of changed) {
        values[param.name] = formatForEnv(param, this.values[param.name]);
      }
      this.saving = true;
      this.lastError = null;
      try {
        const result = await api.put<SaveResult>("/api/config", {
          hash: this.hash,
          values,
        });
        this.lastResult = result;
        await this.load();
        return result;
      } catch (error) {
        const failure = error as Error & { status?: number; details?: unknown };
        this.lastResult = null; // 失败时不能继续展示上一次的“已写入/已核对”
        this.lastError = {
          message: failure.message,
          status: failure.status,
          details: failure.details,
        };
        throw error;
      } finally {
        this.saving = false;
      }
    },
    async verify() {
      const data = await api.post<{ verification: SaveResult["verification"] }>(
        "/api/config/verify",
      );
      if (this.lastResult) {
        this.lastResult = { ...this.lastResult, verification: data.verification };
      }
      return data.verification;
    },
    async loadVersions() {
      const data = await api.get<{ versions: VersionRecord[] }>("/api/config/versions");
      this.versions = data.versions;
    },
    async rollback(versionId: number) {
      const result = await api.post<SaveResult>(`/api/config/versions/${versionId}/rollback`, {
        hash: this.hash,
      });
      this.lastResult = result;
      await this.load();
      return result;
    },
  },
});
