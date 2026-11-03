<script setup lang="ts">
import {
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
  try {
    await auth.setup(password.value);
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
      <p class="auth__sub muted">设置管理员密码；之后可在「系统 → 账号」修改。</p>

      <form class="auth__form" @submit.prevent="submit">
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
  top: var(--space-3);
  right: var(--space-3);
  z-index: 20;
}

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
  width: min(460px, 100%);
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
  margin-top: var(--space-2);
  font-size: 12px;
  color: var(--text-muted);
}

.auth__hint {
  margin: 0;
  color: var(--warning);
  font-size: 12px;
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
  margin-top: var(--space-3);
  width: 100%;
}

.auth__foot {
  margin: var(--space-5) 0 0;
  font-size: 11px;
}
</style>
