import { defineStore } from "pinia";

import * as api from "../api";
import type { AuthStatus } from "../types";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    initialized: false,
    authenticated: false,
    username: null as string | null,
    setupTokenRequired: false,
    ready: false,
    loading: false,
  }),
  getters: {
    needsSetup: (state) => !state.initialized,
  },
  actions: {
    apply(status: AuthStatus) {
      this.initialized = status.initialized;
      this.authenticated = status.authenticated;
      this.username = status.username;
      this.setupTokenRequired = Boolean(status.setup_token_required);
      this.ready = true;
    },
    async refresh() {
      this.apply(await api.get<AuthStatus>("/api/auth/status"));
    },
    async setup(password: string, token?: string) {
      this.loading = true;
      try {
        await api.post(
          "/api/auth/setup",
          { password },
          token ? { "X-Setup-Token": token } : undefined,
        );
        await this.refresh();
      } finally {
        this.loading = false;
      }
    },
    async login(password: string) {
      this.loading = true;
      try {
        await api.post("/api/auth/login", { password });
        await this.refresh();
      } finally {
        this.loading = false;
      }
    },
    async logout() {
      await api.post("/api/auth/logout");
      this.authenticated = false;
      this.username = null;
    },
    markLoggedOut() {
      this.authenticated = false;
    },
  },
});
