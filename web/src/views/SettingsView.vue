<script setup lang="ts">
import { computed } from "vue";
import { Operation, RefreshLeft } from "@element-plus/icons-vue";

import PageHeader from "../components/PageHeader.vue";
import { PROJECT_URL } from "../config";
import { useTheme, type Theme } from "../composables/useTheme";
import { useUiSettings, type FontSize } from "../composables/useUiSettings";

const { theme, set } = useTheme();
const { fontSize, setFontSize, reset } = useUiSettings();

const themeValue = computed<Theme>({
  get: () => theme.value,
  set: (value) => set(value),
});

const fontValue = computed<FontSize>({
  get: () => fontSize.value,
  set: (value) => setFontSize(value),
});
</script>

<template>
  <section class="page">
    <PageHeader title="设置" subtitle="本浏览器内的外观偏好，立即生效" :icon="Operation">
      <el-button @click="reset">
        <el-icon><RefreshLeft /></el-icon>
        恢复默认
      </el-button>
    </PageHeader>

    <section class="panel settings-panel">
      <header class="panel__head">外观</header>
      <div class="panel__body stack">
        <div class="setting-row">
          <div class="setting-label">
            <strong>主题模式</strong>
            <p class="muted">深色适合长时间盯屏；浅色适合明亮环境。</p>
          </div>
          <el-radio-group v-model="themeValue">
            <el-radio-button value="dark">深色</el-radio-button>
            <el-radio-button value="light">浅色</el-radio-button>
          </el-radio-group>
        </div>

        <div class="setting-row">
          <div class="setting-label">
            <strong>字号</strong>
            <p class="muted">影响正文、表格、按钮与表单标签，仅保存在本浏览器。</p>
          </div>
          <el-radio-group v-model="fontValue">
            <el-radio-button value="sm">小</el-radio-button>
            <el-radio-button value="md">标准</el-radio-button>
            <el-radio-button value="lg">大</el-radio-button>
          </el-radio-group>
        </div>

        <div class="preview">
          <span class="preview__eyebrow muted">预览</span>
          <h2 class="preview__title">扫描器在线 · 核对通过</h2>
          <p class="preview__text">
            每轮扫描会重新读取 .env；保存后下一轮生效，调度变更立即热重载。
          </p>
          <p class="preview__meta mono">2026/11/03 15:20:00 · MAX_CANDIDATES=200</p>
        </div>
      </div>
    </section>

    <section class="panel settings-panel">
      <header class="panel__head">项目</header>
      <div class="panel__body stack">
        <p class="muted">
          面板与扫描器同源；问题反馈、版本说明与部署文档都在项目主页。
        </p>
        <div>
          <a :href="PROJECT_URL" target="_blank" rel="noopener noreferrer">
            <el-button>
              <el-icon>
                <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                  <path
                    d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8Z"
                  />
                </svg>
              </el-icon>
              GitHub 项目主页
            </el-button>
          </a>
        </div>
        <p class="muted mono repo-url">github.com/LancelotRar/self-hosted-best-cf-ip-scanner</p>
      </div>
    </section>
  </section>
</template>

<style scoped>
.settings-panel {
  margin-bottom: var(--space-4);
}

.settings-panel:last-child {
  margin-bottom: 0;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border);
}

.setting-label strong {
  font-size: 13px;
}

.setting-label p {
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 18px;
}

.preview {
  padding: var(--space-4);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-2);
}

.preview__eyebrow {
  font-size: 11px;
  letter-spacing: 0.08em;
}

.preview__title {
  margin: 4px 0 0;
  font-size: 18px;
  line-height: 26px;
}

.preview__text {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 20px;
}

.preview__meta {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.repo-url {
  font-size: 12px;
  overflow-wrap: anywhere;
}
</style>
