---
name: language-translation
description: 语言翻译技能 — 将中文提示翻译为英文（供 Codex 等工具使用），以及处理用户对翻译输出的偏好
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [translation, english, chinese, codex]
    related_skills: []
---

# Language Translation

语言翻译相关规则和工作流，尤其涉及将中文提示转换为英文以供下游工具使用。

## 输出纯度规则（关键）

- **输出纯度：** 当执行翻译时，输出 **仅** 包含翻译后的文本。
- 不得包含任何前言、解释、评论、引号或周围对话上下文。
- 用户已明确拒绝任何附带元内容的翻译。
- 这条规则同样适用于在调用 Codex 等外部工具前所需的中文→英文翻译中间步骤。

## 使用场景

当用户给出中文提示且需要调用 Codex 或类似需要英文输入的工 Read时，先将提示翻译成英文，然后 *仅输出翻译结果* —— 不附加其他语言或评论。
