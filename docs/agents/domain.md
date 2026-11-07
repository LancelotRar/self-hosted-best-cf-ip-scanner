# Domain Docs

工程类 skill 在探索本仓库时，如何消费这里的领域文档。

## 探索之前先读这些

- 仓库根目录的 **`GLOSSARY.md`**，或
- 若根目录存在 **`GLOSSARY-MAP.md`**：它指向每个上下文各自的 `GLOSSARY.md`，读取与当前主题相关的每一份。
- **`docs/adr/`**：读取涉及你即将改动的区域的 ADR。

如果这些文件不存在，**静默继续**。不要提示缺失，也不要在开工前建议创建它们。`/domain-modeling` skill（经由 `/grill-with-docs` 和 `/improve-codebase-architecture` 触达）只在术语或决策真正确定时才懒创建。

## 文件结构

本仓库为单上下文：

```
/
├── GLOSSARY.md
├── docs/adr/
│   ├── 0001-....md
│   └── 0002-....md
├── panel/          ← 面板后端（FastAPI）
├── scanner/        ← 扫描核心库（参数 schema 唯一真源）
└── web/            ← 面板前端（Vue 3 + TS）
```

多上下文仓库（根目录存在 `GLOSSARY-MAP.md` 时）才使用根 `GLOSSARY-MAP.md` + 各上下文自己的 `GLOSSARY.md` 与 `docs/adr/`；本仓库不适用。

## 使用 glossary 的词汇

当你的产出（issue 标题、重构提案、假设、测试名）提到某个领域概念时，使用 `GLOSSARY.md` 定义的术语。不要漂移到 glossary 明确避开的同义词。

如果你需要的概念还不在 glossary 里，这是一个信号：要么你在发明本仓库不用的说法（重新考虑），要么确实存在缺口（记下来交给 `/domain-modeling`）。

## 标注 ADR 冲突

如果你的产出与已有 ADR 矛盾，明确地摊开说，而不是悄悄覆盖：

> _与 ADR-0007（事件溯源的订单）矛盾，但值得重开因为……_
