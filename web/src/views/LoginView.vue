<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

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
          placeholder="输入密码"
          @keyup.enter="submit"
        />

        <p v-if="error" class="auth__error" role="alert">{{ error }}</p>

        <el-button type="primary" class="auth__submit" :loading="auth.loading" @click="submit">
          登录
        </el-button>
      </form>

      <p class="auth__foot muted">
        忘记密码：在宿主机执行
        <code class="mono">docker compose exec panel python -m panel.cli reset-password</code>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--space-5);
  background:
    radial-gradient(900px 420px at 50% -10%, color-mix(in srgb, var(--primary) 14%, transparent), transparent 70%),
    var(--bg);
}

.auth__panel {
  width: min(420px, 100%);
  padding: var(--space-5);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-overlay);
}

.auth__brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}

.auth__brand strong {
  display: block;
  font-size: 13px;
}

.auth__brand p {
  margin: 0;
  font-size: 11px;
}

.auth__mark {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--primary);
  color: var(--on-primary);
  font-size: 12px;
  font-weight: 700;
}

.auth__title {
  margin: 0;
  font-size: 20px;
  line-height: 28px;
}

.auth__sub {
  margin: 4px 0 var(--space-5);
  font-size: 12px;
}

.auth__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.auth__label {
  font-size: 12px;
  color: var(--text-muted);
}

.auth__error {
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--danger) 45%, var(--border));
  background: color-mix(in srgb, var(--danger) 8%, var(--surface));
  color: var(--text);
  font-size: 12px;
}

.auth__submit {
  margin-top: var(--space-2);
  width: 100%;
}

.auth__foot {
  margin: var(--space-5) 0 0;
  font-size: 11px;
  line-height: 18px;
}

.auth__foot code {
  font-size: 11px;
  overflow-wrap: anywhere;
}
</style>
