// 在首屏渲染前恢复主题，避免深色模式闪白。
// 独立成文件是为了满足后端 CSP 的 `script-src 'self'`（禁止内联脚本）。
try {
  document.documentElement.dataset.theme =
    localStorage.getItem("panel-theme") === "dark" ? "dark" : "light";
} catch {
  document.documentElement.dataset.theme = "light";
}
