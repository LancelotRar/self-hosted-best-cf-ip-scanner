<script setup lang="ts">
import {
  Lock,
  Right,
} from "@element-plus/icons-vue";
import { ref } from "vue";
import { useRouter } from "vue-router";

import TopActions from "../components/TopActions.vue";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const password = ref("");
const error = ref("");

async function submit() {
  error.value = "";
  if (!password.value) {
    error.value = "请输入管理员密码";
    return;
  }
  try {
    await auth.login(password.value);
    await router.push({ name: "overview" });
  } catch (exception) {
    error.value = (exception as Error).message || "登录失败";
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

      <h1 class="auth__title">登录</h1>
      <p class="auth__sub muted">使用首次设置的管理员密码登录。</p>

      <form class="auth__form" @submit.prevent="submit">
        <label class="auth__label" for="login-password">管理员密码</label>
        <el-input
          id="login-password"
          v-model="password"
          type="password"
          show-password
          autocomplete="current-password"
          :prefix-icon="Lock"
          placeholder="输入密码"
          @keyup.enter="submit"
        />

        <p v-if="error" class="auth__error" role="alert">{{ error }}</p>

        <el-button type="primary" class="auth__submit" :loading="auth.loading" @click="submit">
          登录
          <el-icon class="el-icon--right"><Right /></el-icon>
        </el-button>
      </form>

      <p class="auth__foot muted">忘记密码请联系部署管理员。</p>
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
  width: min(400px, 100%);
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
  font-size: var(--fs-meta);
  color: var(--text-muted);
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
