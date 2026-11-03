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
    <el-card class="auth__card" shadow="always">
      <h1>登录运维面板</h1>
      <p class="panel-muted">使用首次设置的管理员密码登录。</p>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="密码">
          <el-input
            v-model="password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="管理员密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <el-button type="primary" :loading="auth.loading" class="auth__submit" @click="submit">
          登录
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
  width: min(420px, 100%);
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
