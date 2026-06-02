# Answer Synthesis Skill

## Purpose

Turn retrieved evidence into a concise, useful answer with clear citations, uncertainty, and next actions.

## When To Use

Use this skill after public web research, local search, source evaluation, or evidence capture.

## Synthesis Rules

1. Answer the user's actual question first.
2. Use source-backed facts only.
3. Separate facts from analysis.
4. Name important uncertainty.
5. Keep the answer structured but not bloated.
6. Recommend concrete next actions.
7. Suggest where knowledge should be saved in Obsidian.

## Output Shape

Use the Goldfish fixed response frame. Keep the section order stable so the
user can scan answers like a terminal dashboard:

```markdown
╭─ goldfish · research ─╮
│ status: ready · answer: grounded │
╰──────────────────────────────────╯

## 结论

## 关键依据

## 判断

## 不确定性

## 对你的价值

## 下一步

## 建议沉淀位置
```

For non-research chat, use the shorter default frame:

- 结论
- 关键依据
- 我的判断
- 下一步

For business ideas, use:

- 目标用户
- 痛点
- 产品形态
- MVP
- 收费方式
- 验证方法
- 风险
- 建议沉淀位置

## Style

- Prefer Chinese for the user's current workflow unless configured otherwise.
- Keep citations as Markdown links.
- Avoid hype words unless the evidence supports them.
- Do not use emoji as structural markers; the CLI layout already carries the visual identity.
