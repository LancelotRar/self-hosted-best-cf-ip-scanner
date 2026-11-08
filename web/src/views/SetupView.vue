<script setup lang="ts">
import {
  Key,
  Lock,
} from "@element-plus/icons-vue";
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import TopActions from "../components/TopActions.vue";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const password = ref("");
const confirm = ref("");
const setupToken = ref("");
const error = ref("");

const tooShort = computed(() => password.value.length > 0 && password.value.length < 8);

async function submit() {
  error.value = "";
  if (password.value.length < 8) {
    error.value = "密码至少 8 个字符";
    return;
  }
  if (password.value !== confirm.value) {
    error.value = "两次输入的密码不一致";
    return;
  }
  if (auth.setupTokenRequired && !setupToken.value.trim()) {
    error.value = "请输入部署时设置的 setup token";
    return;
  }
  try {
    await auth.setup(password.value, setupToken.value.trim() || undefined);
    await router.push({ name: "overview" });
  } catch (exception) {
    error.value = (exception as Error).message || "设置失败";
  }
}
</script>

<template>
  <div class="auth">
    <TopActions class="auth-actions" />
    <div class="auth__panel">
      <div class="auth__brand">
        <span class="auth__mark" aria-hidden="true">CF</span>
        <div>
          <strong>Cloudflare 优选 IP 扫描器</strong>
          <p class="muted">项目专属运维面板</p>
        </div>
      </div>

      <h1 class="auth__title">首次设置</h1>
      <p class="auth__sub muted">设置管理员密码；之后可在「设置 · 账号」修改。</p>

      <form class="auth__form" @submit.prevent="submit">
        <template v-if="auth.setupTokenRequired">
          <label class="auth__label" for="setup-token">设置口令</label>
          <el-input
            id="setup-token"
            v-model="setupToken"
            autocomplete="off"
            placeholder="部署时设置的口令"
            :prefix-icon="Key"
          />
          <p class="auth__hint">该部署启用了首次设置口令，请从部署环境获取。</p>
        </template>

        <label class="auth__label" for="setup-password">管理员密码</label>
        <el-input
          id="setup-password"
          v-model="password"
          type="password"
          show-password
          autocomplete="new-password"
          placeholder="至少 8 个字符"
          :prefix-icon="Lock"
        />
        <p v-if="tooShort" class="auth__hint">至少 8 个字符</p>

        <label class="auth__label" for="setup-confirm">确认密码</label>
        <el-input
          id="setup-confirm"
          v-model="confirm"
          type="password"
          show-password
          autocomplete="new-password"
          placeholder="再输入一次"
          :prefix-icon="Lock"
          @keyup.enter="submit"
        />

        <p v-if="error" class="auth__error" role="alert">{{ error }}</p>

        <el-button type="primary" class="auth__submit" :loading="auth.loading" @click="submit">
          设置并登录
        </el-button>
      </form>

      <p class="auth__foot muted">凭据只保存在本机；密码使用 Argon2id 哈希存储。</p>
    </div>
  </div>
</template>

<style scoped>
.auth-actions {
  position: fixed;
  top: var(--space-4);
  right: var(--space-4);
  z-index: 20;
}

.auth {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--space-5);
  background:
    radial-gradient(720px 360px at 50% -8%, color-mix(in srgb, var(--primary) 8%, transparent), transparent 72%),
    var(--bg);
}

.auth__panel {
  width: min(420px, 100%);
  padding: 28px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-overlay);
}

.auth__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-6);
}

.auth__brand strong {
  display: block;
  font-size: var(--fs-body);
  font-weight: 600;
  letter-spacing: -0.01em;
}

.auth__brand p {
  margin: 1px 0 0;
  font-size: var(--fs-micro);
}

.auth__mark {
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  font-size: 11.5px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.auth__title {
  margin: 0;
  font-size: 22px;
  line-height: 30px;
  font-weight: 650;
  letter-spacing: -0.02em;
}

.auth__sub {
  margin: 4px 0 var(--space-5);
  font-size: var(--fs-meta);
}

.auth__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.auth__label {
  margin-top: 8px;
  font-size: var(--fs-meta);
  color: var(--text-muted);
}

.auth__label:first-child {
  margin-top: 0;
}

.auth__hint {
  margin: 0;
  color: var(--warning);
  font-size: var(--fs-micro);
  line-height: 16px;
}

.auth__error {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  color: var(--text);
  font-size: var(--fs-meta);
}

.auth__submit {
  margin-top: var(--space-3);
  width: 100%;
}

.auth__foot {
  margin: var(--space-5) 0 0;
  font-size: var(--fs-micro);
  line-height: 18px;
}
</style>
