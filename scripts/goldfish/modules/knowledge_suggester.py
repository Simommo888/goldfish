"""Generate knowledge-deposition reports and optional draft notes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .storage import save_markdown
from .utils import kb_root, safe_filename, truncate


def knowledge_report_path(date_text: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    return root / "04_Resources" / "AI-News" / "Reports" / f"AI情报沉淀建议-{date_text}.md"


def _frontmatter(kind: str, date_text: str, title: str) -> str:
    return f"""---
type: {kind}
status: draft
area: AI-News
tags: [ai-news, intelligence-agent, knowledge-deposition]
created: {date_text}
updated: {date_text}
source: goldfish
---
"""


def generate_knowledge_report(date_text: str, insights: List[Dict[str, Any]]) -> str:
    if not insights:
        body = "今日暂无适合自动沉淀的高分情报。可以人工查看日报里的待检查来源。"
    else:
        blocks = []
        for index, insight in enumerate(insights, start=1):
            blocks.append(
                f"""### {index}. {insight['title']}

**建议类型：** {insight['target_label']}  
**建议目录：** `{insight['target_folder']}`  
**来源：** {insight['source']}  
**链接：** {insight['url'] or '无'}  
**分类：** {insight['category']}  
**评分：** {insight['score']}  
**沉淀理由：** {insight['reason']}  
**一句话总结：** {insight['summary']}  
**为什么重要：** {insight['why_important']}  
**对我有什么用：** {insight['value_for_me']}  
**建议行动：** {insight['suggested_action']}

- [ ] 已阅读原文
- [ ] 已沉淀为永久笔记
- [ ] 已沉淀为 Prompt
- [ ] 已沉淀为商业想法
- [ ] 已沉淀为项目灵感
"""
            )
        body = "\n---\n\n".join(blocks)
    return f"""# AI 情报沉淀建议 - {date_text}

> 这份报告是 Agent 从今日 AI 情报中挑出的知识资产候选。先验证来源，再沉淀；不要把未确认内容写成确定结论。

## 今日建议沉淀

{body}

## 今日处理清单

- [ ] 选择最值得沉淀的 1 条
- [ ] 改写成自己的长期观点
- [ ] 如果有商业价值，补充目标用户和付费场景
- [ ] 如果能做项目，补充 MVP 功能和技术路线
- [ ] 更新相关 MOC
"""


def generate_draft_note(date_text: str, insight: Dict[str, Any]) -> str:
    title = insight["title"]
    kind = insight["target_type"]
    source = insight["source_item"]
    return f"""{_frontmatter(kind, date_text, title)}
# {title}

## 来源

- 来源：{insight['source']}
- 链接：{insight['url'] or '无'}
- 日期：{date_text}

## 核心信息

{insight['summary']}

## 为什么值得沉淀

{insight['why_important']}

## 对我的价值

{insight['value_for_me']}

## 可复用结论

- 

## 下一步行动

- [ ] 阅读原文
- [ ] 验证事实
- [ ] 提炼自己的判断
- [ ] 链接到相关 MOC

## 原始摘要

{truncate(source.get('summary') or source.get('raw_content') or '', 800)}
"""


def write_knowledge_report(date_text: str, insights: List[Dict[str, Any]], root: Path | None = None) -> Path:
    root = root or kb_root()
    return save_markdown(knowledge_report_path(date_text, root), generate_knowledge_report(date_text, insights))


def write_draft_notes(date_text: str, insights: List[Dict[str, Any]], root: Path | None = None) -> List[Path]:
    root = root or kb_root()
    written: List[Path] = []
    for insight in insights:
        folder = root / insight["target_folder"]
        filename = safe_filename(f"{date_text}-{insight['target_label']}-{insight['title']}", 100) + ".md"
        path = folder / filename
        if path.exists():
            continue
        written.append(save_markdown(path, generate_draft_note(date_text, insight)))
    return written
