<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

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
    <el-card class="auth__card" shadow="always">
      <h1>首次设置</h1>
      <p class="panel-muted">为运维面板设置管理员密码；之后可在「系统 → 账号」修改。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="管理员密码" :error="tooShort ? '至少 8 个字符' : ''">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="至少 8 个字符"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="confirm"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="再输入一次"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <el-button type="primary" :loading="auth.loading" class="auth__submit" @click="submit">
          设置并登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.auth {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
}

.auth__card {
  width: min(460px, 100%);
}

.auth__card h1 {
  font-size: 20px;
  margin: 0 0 8px;
}

.auth__submit {
  width: 100%;
  margin-top: 12px;
}
</style>
