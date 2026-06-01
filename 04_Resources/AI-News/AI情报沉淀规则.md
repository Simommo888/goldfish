# AI 情报沉淀规则

AI 日报不是看完就结束，而是要沉淀成知识资产。

## 沉淀方向

1. 对我长期有启发的观点 → 05_Permanent-Notes
2. 可以变成产品的机会 → 11_Business-Ideas
3. 可以提升开发效率的方法 → 09_Prompts
4. AI 应用开发知识 → 03_Areas/AI-Development
5. Agent 相关技术 → 03_Areas/Agent
6. RAG 相关技术 → 03_Areas/RAG
7. 可用于项目的内容 → 02_Projects
8. 暂时不知道放哪里 → 00_Inbox

## 每日处理流程

- [ ] 阅读今日 AI 情报日报
- [ ] 标记最重要的 3 条
- [ ] 提炼 1 条永久笔记
- [ ] 记录 1 个商业想法或项目灵感
- [ ] 把有用 Prompt 放入 Prompt 库
- [ ] 更新相关 MOC

## 每周处理流程

- [ ] 阅读 AI 趋势周报
- [ ] 总结本周最重要趋势
- [ ] 判断哪些方向值得学习
- [ ] 判断哪些方向值得做项目
- [ ] 判断哪些方向有变现机会

## Agent 反馈流程

- [ ] 打开 `04_Resources/AI-News/Reports/AI情报沉淀建议-YYYY-MM-DD.md`
- [ ] 选择 1-3 条真正值得沉淀的内容
- [ ] 打开 `04_Resources/AI-News/Reports/AI情报反馈-YYYY-MM-DD.md`
- [ ] 勾选“值得沉淀 / 可做项目 / 有商业价值 / 多推荐 / 少推荐”
- [ ] 每周根据反馈调整 `keywords.json` 和 `people.json`

## 自动草稿规则

默认只生成沉淀建议，不自动创建永久笔记。只有当你确认要批量生成候选草稿时，才运行：

```powershell
goldfish run --write-drafts
```

草稿仍然需要人工验证来源、改写观点、补充自己的判断，再进入长期知识库。
